#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --- PDF text extraction (prefer PyMuPDF; fallback to pdfplumber) ---
def extract_pdf_pages_text(pdf_path: str) -> List[str]:
    """
    Returns a list of page texts (one string per page).
    Prefers PyMuPDF (fitz). Falls back to pdfplumber if available.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        pages = []
        for i in range(len(doc)):
            pages.append(doc.load_page(i).get_text("text"))
        doc.close()
        return pages
    except Exception as e_fitz:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return pages
        except Exception as e_plumber:
            raise RuntimeError(
                f"Failed to read PDF as text.\n"
                f"PyMuPDF error: {e_fitz}\n"
                f"pdfplumber error: {e_plumber}\n"
                f"Tip: ensure the PDF is text-based (not scanned), or add OCR."
            )

# --- Data model ---
@dataclass
class Requirement:
    id: str
    name: str
    description: str
    section: Optional[str] = None
    audit_info: Optional[str] = None

# --- CSV reading / correlation ---
def normalize_name(s: str) -> str:
    # Aggressive normalization for matching names between CSVs
    s = (s or "").strip().casefold()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_description_for_search(desc: str) -> str:
    """
    Implements step 4a:
    Replace "The software shall ensure" with "Ensure"
    (case-insensitive, only for that phrase).
    """
    if not desc:
        return ""
    # Replace only the phrase, regardless of case, preserving the rest.
    return re.sub(r"(?i)\bthe software shall ensure\b", "Ensure", desc).strip()

def read_doc1(csv_path: str) -> Dict[str, Dict[str, str]]:
    """
    Returns dict keyed by normalized Name -> {name, description, essential}
    """
    out: Dict[str, Dict[str, str]] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"Name", "Description", "Essential"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"doc1 CSV must contain columns: {sorted(required)}. Found: {reader.fieldnames}")
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            key = normalize_name(name)
            out[key] = {
                "name": name,
                "description": (row.get("Description") or "").strip(),
                "essential": (row.get("Essential") or "").strip(),
            }
    return out

def read_doc2(csv_path: str) -> Dict[str, Dict[str, str]]:
    """
    Returns dict keyed by normalized Name -> {id, name, essential_requirement, item_type, locked}
    """
    out: Dict[str, Dict[str, str]] = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"ID", "Item Type", "Locked", "Name", "Essential Requirement"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"doc2 CSV must contain columns: {sorted(required)}. Found: {reader.fieldnames}")
        for row in reader:
            name = (row.get("Name") or "").strip()
            req_id = (row.get("ID") or "").strip()
            if not name or not req_id:
                continue
            key = normalize_name(name)
            out[key] = {
                "id": req_id,
                "name": name,
                "essential_requirement": (row.get("Essential Requirement") or "").strip(),
                "item_type": (row.get("Item Type") or "").strip(),
                "locked": (row.get("Locked") or "").strip(),
            }
    return out

def correlate(doc1: Dict[str, Dict[str, str]], doc2: Dict[str, Dict[str, str]]) -> List[Requirement]:
    reqs: List[Requirement] = []
    for key, d1 in doc1.items():
        if key not in doc2:
            continue
        d2 = doc2[key]
        desc_norm = normalize_description_for_search(d1.get("description", ""))
        reqs.append(
            Requirement(
                id=d2["id"],
                name=d1["name"],  # keep doc1's name as primary
                description=desc_norm,  # store normalized description (per step 4a)
            )
        )
    return reqs

# --- PDF searching / extraction ---
SECTION_RE = re.compile(r"^\s*(\d+(?:\.\d+){3})\b")
def split_lines(page_text: str) -> List[str]:
    # Keep reasonably clean lines
    lines = (page_text or "").splitlines()
    return [re.sub(r"\s+", " ", ln).strip() for ln in lines if ln.strip()]

def find_requirement_line(pages_lines: List[List[str]], search_text: str) -> Optional[Tuple[int, int, str]]:
    """
    Finds first occurrence of a line containing search_text (case-insensitive).
    Returns (page_index, line_index, line_text) or None.
    """
    needle = (search_text or "").strip()
    if not needle:
        return None
    needle_cf = needle.casefold()
    for pi, lines in enumerate(pages_lines):
        for li, ln in enumerate(lines):
            if needle_cf in ln.casefold():
                return (pi, li, ln)
    return None

def extract_section_number(line: str) -> Optional[str]:
    m = SECTION_RE.match(line or "")
    return m.group(1) if m else None

def extract_audit_block(
    pages_lines: List[List[str]],
    start_page: int,
    start_line: int
) -> Optional[str]:
    """
    Starting beneath the matched requirement line, scan forward for:
      - 'Audit:' marker (may appear on same line as other text, but typically below)
      - Capture everything after 'Audit:' until 'Remediation:' (exclusive)
    Spans pages if needed.
    """
    capturing = False
    chunks: List[str] = []

    for pi in range(start_page, len(pages_lines)):
        lines = pages_lines[pi]
        li0 = start_line + 1 if pi == start_page else 0

        for li in range(li0, len(lines)):
            ln = lines[li]

            # If not yet capturing, look for Audit:
            if not capturing:
                m_a = re.search(r"\bAudit:\b", ln, flags=re.IGNORECASE)
                if m_a:
                    capturing = True
                    after = ln[m_a.end():].strip()
                    # If Remediation appears on same line, end immediately
                    m_r = re.search(r"\bRemediation:\b", after, flags=re.IGNORECASE)
                    if m_r:
                        before = after[:m_r.start()].strip()
                        if before:
                            chunks.append(before)
                        return " ".join(chunks).strip() or None
                    if after:
                        chunks.append(after)
                continue

            # If capturing, stop at Remediation:
            m_r = re.search(r"\bRemediation:\b", ln, flags=re.IGNORECASE)
            if m_r:
                before = ln[:m_r.start()].strip()
                if before:
                    chunks.append(before)
                return " ".join(chunks).strip() or None

            chunks.append(ln)

    return " ".join(chunks).strip() or None

def enrich_from_pdf(reqs: List[Requirement], pdf_path: str) -> None:
    pages_text = extract_pdf_pages_text(pdf_path)
    pages_lines = [split_lines(t) for t in pages_text]

    for r in reqs:
        # Step 4b uses the modified description (already “Ensure …”)
        hit = find_requirement_line(pages_lines, r.description)
        if not hit:
            # Not found; leave section/audit_info as None
            continue

        page_i, line_i, line_txt = hit
        r.section = extract_section_number(line_txt)
        r.audit_info = extract_audit_block(pages_lines, page_i, line_i)

# --- Output ---
def write_json(reqs: List[Requirement], out_json: str) -> None:
    data = []
    for r in reqs:
        obj = {
            "id": r.id,
            "name": r.name,
            "description": r.description,
        }
        if r.section is not None:
            obj["section"] = r.section
        if r.audit_info is not None:
            obj["audit_info"] = r.audit_info
        data.append(obj)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_csv(reqs: List[Requirement], out_csv: str) -> None:
    fieldnames = ["id", "name", "description", "section", "audit_info"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in reqs:
            w.writerow({
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "section": r.section or "",
                "audit_info": r.audit_info or "",
            })

def main() -> int:
    ap = argparse.ArgumentParser(description="Correlate requirements across CSVs and enrich with audit info from a PDF.")
    ap.add_argument("--doc1", required=True, help="CSV file with columns: Name, Description, Essential Requirement")
    ap.add_argument("--doc2", required=True, help="CSV file with columns: ID, Item Type, Locked, Name, Essential Requirement")
    ap.add_argument("--pdf", required=True, help="PDF file to search for requirement lines and extract Audit: blocks")
    ap.add_argument("--out-json", default="output.json", help="Output JSON filename (default: output.json)")
    ap.add_argument("--out-csv", default="output.csv", help="Output CSV filename (default: output.csv)")
    args = ap.parse_args()

    doc1 = read_doc1(args.doc1)
    doc2 = read_doc2(args.doc2)
    reqs = correlate(doc1, doc2)

    if not reqs:
        print("No correlated requirements found (no matching Name values).", file=sys.stderr)

    enrich_from_pdf(reqs, args.pdf)
    write_json(reqs, args.out_json)
    write_csv(reqs, args.out_csv)

    print(f"Wrote {len(reqs)} items to {args.out_json} and {args.out_csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

"""
python3 build_requirements.py \
  --doc1 doc1.csv \
  --doc2 doc2.csv \
  --pdf requirements.pdf \
  --out-json requirements.json \
  --out-csv requirements.csv
"""
