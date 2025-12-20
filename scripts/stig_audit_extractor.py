#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import logging
from typing import Iterable

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
# Accept 3-part or 4-part section numbers: 5.2.1 OR 1.3.1.1
AUDIT_RE = re.compile(r"(?i)\bAudit\s*:")          # <-- no trailing \b
REMEDIATION_RE = re.compile(r"(?i)\bRemediation\s*:")  # <-- no trailing \b
SECTION_RE = re.compile(r"^\s*(\d+(?:\.\d+){2,3})\b")

def normalize_for_contains(s: str) -> str:
    """
    Make PDF text matching more tolerant:
    - collapse whitespace
    - casefold
    - replace non-breaking spaces
    """
    if s is None:
        return ""
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()

def split_lines_preserve(page_text: str) -> List[str]:
    """
    Split into lines but preserve the original line text as much as possible.
    Only strip trailing whitespace to avoid mangling code blocks and wraps.
    """
    lines = (page_text or "").splitlines()
    # keep blank lines out, but preserve internal spacing
    return [ln.rstrip("\n\r") for ln in lines if ln.strip()]

def find_requirement_line(
    pages_lines: List[List[str]],
    search_text: str,
    debug_id: str = ""
) -> Optional[Tuple[int, int, str]]:
    """
    More tolerant line search: uses normalized contains.
    """
    needle_raw = (search_text or "").strip()
    if not needle_raw:
        return None

    needle = normalize_for_contains(needle_raw)

    for pi, lines in enumerate(pages_lines):
        for li, ln in enumerate(lines):
            if needle in normalize_for_contains(ln):
                return (pi, li, ln)
    return None

def extract_section_number(line: str) -> Optional[str]:
    m = SECTION_RE.match(line or "")
    return m.group(1) if m else None

def extract_audit_block(
    pages_lines: List[List[str]],
    start_page: int,
    start_line: int,
    debug_label: str = "",
    debug_window_lines: int = 40,
) -> Optional[str]:
    """
    Scan forward (starting below the requirement title line):
      - Find 'Audit:' marker
      - Capture everything until 'Remediation:' marker
    Preserves newlines.
    Adds debug logs to explain WHY it didn't capture.
    """
    capturing = False
    out_lines: List[str] = []
    audit_loc: Optional[Tuple[int, int]] = None

    # Debug: log a small window of lines after the requirement header
    if debug_window_lines > 0:
        preview = []
        remaining = debug_window_lines
        for pi in range(start_page, len(pages_lines)):
            li0 = start_line + 1 if pi == start_page else 0
            for li in range(li0, len(pages_lines[pi])):
                preview.append(f"p{pi+1} l{li+1}: {pages_lines[pi][li]}")
                remaining -= 1
                if remaining <= 0:
                    break
            if remaining <= 0:
                break
        logging.debug("[%s] Preview lines after requirement header:\n%s",
                      debug_label, "\n".join(preview))

    for pi in range(start_page, len(pages_lines)):
        lines = pages_lines[pi]
        li0 = start_line + 1 if pi == start_page else 0

        for li in range(li0, len(lines)):
            ln = lines[li]

            if not capturing:
                m_a = AUDIT_RE.search(ln)
                if not m_a:
                    continue

                capturing = True
                audit_loc = (pi, li)
                # capture anything after "Audit:" on the same line
                after = ln[m_a.end():].strip()

                # If Remediation is on same line (rare), stop immediately
                m_r_same = REMEDIATION_RE.search(after)
                if m_r_same:
                    before = after[:m_r_same.start()].strip()
                    if before:
                        out_lines.append(before)
                    logging.debug("[%s] Audit and Remediation on same line at p%d l%d",
                                  debug_label, pi+1, li+1)
                    return "\n".join(out_lines).rstrip() or None

                if after:
                    out_lines.append(after)
                continue

            # capturing
            m_r = REMEDIATION_RE.search(ln)
            if m_r:
                before = ln[:m_r.start()].rstrip()
                if before.strip():
                    out_lines.append(before)
                logging.debug("[%s] Captured Audit block from p%d l%d to p%d l%d",
                              debug_label, audit_loc[0]+1, audit_loc[1]+1, pi+1, li+1)
                return "\n".join(out_lines).rstrip() or None

            out_lines.append(ln.rstrip())

    # If we found Audit but not Remediation, return what we got (and warn)
    if audit_loc:
        logging.warning("[%s] Found Audit: at p%d l%d but did not find Remediation:. Returning partial audit block.",
                        debug_label, audit_loc[0]+1, audit_loc[1]+1)
        return "\n".join(out_lines).rstrip() or None

    logging.warning("[%s] Did not find Audit: marker after requirement header.", debug_label)
    return None

def debug_context(pages_lines: List[List[str]], page_i: int, line_i: int, radius: int = 6) -> str:
    """
    Return a small snippet around a line for logging.
    """
    lines = pages_lines[page_i]
    start = max(0, line_i - radius)
    end = min(len(lines), line_i + radius + 1)
    out = []
    for idx in range(start, end):
        prefix = ">>" if idx == line_i else "  "
        out.append(f"{prefix} L{idx+1:04d}: {lines[idx]}")
    return "\n".join(out)

def count_marker_after(
    pages_lines: List[List[str]],
    start_page: int,
    start_line: int,
    marker_regex: str,
    max_lines: int = 400
) -> Optional[Tuple[int, int, str]]:
    """
    Scan forward up to max_lines to see if marker occurs at all after the requirement line.
    Useful debug.
    """
    seen = 0
    pat = re.compile(marker_regex, flags=re.IGNORECASE)
    for pi in range(start_page, len(pages_lines)):
        lines = pages_lines[pi]
        li0 = start_line + 1 if pi == start_page else 0
        for li in range(li0, len(lines)):
            if pat.search(lines[li]):
                return (pi, li, lines[li])
            seen += 1
            if seen >= max_lines:
                return None
    return None

def enrich_from_pdf(reqs: List[Requirement], pdf_path: str, debug: bool = False) -> None:
    pages_text = extract_pdf_pages_text(pdf_path)
    pages_lines = [split_lines_preserve(t) for t in pages_text]

    for r in reqs:
        label = f"{r.id} | {r.name}"

        hit = find_requirement_line(pages_lines, r.description, debug_id=r.id)

        if not hit:
            logging.warning("[%s] Requirement line NOT FOUND for search text: %r", label, r.description)
            # Extra debug: try finding just "Ensure ..." first clause
            short = r.description
            # If the description is long, take first ~80 chars for a second attempt
            if len(short) > 80:
                short = short[:80]
            hit2 = find_requirement_line(pages_lines, short, debug_id=r.id)
            if hit2:
                logging.warning("[%s] Found with SHORTENED search (%r). Consider searching by header text instead.",
                                label, short)
                if debug:
                    pi, li, ln = hit2
                    logging.debug("[%s] Context around shortened hit:\n%s", label, debug_context(pages_lines, pi, li))
            continue

        page_i, line_i, line_txt = hit
        r.section = extract_section_number(line_txt)

        if debug:
            logging.debug("[%s] Matched line at p%d l%d: %s", label, page_i + 1, line_i + 1, line_txt)
            logging.debug("[%s] Context around match:\n%s", label, debug_context(pages_lines, page_i, line_i))

            a = count_marker_after(pages_lines, page_i, line_i, r"\bAudit\s*:\b")
            b = count_marker_after(pages_lines, page_i, line_i, r"\bRemediation\s*:\b")
            if a:
                logging.debug("[%s] Found Audit: later at p%d l%d: %s", label, a[0] + 1, a[1] + 1, a[2])
            else:
                logging.debug("[%s] Did NOT find Audit: within scan window after match.", label)
            if b:
                logging.debug("[%s] Found Remediation: later at p%d l%d: %s", label, b[0] + 1, b[1] + 1, b[2])
            else:
                logging.debug("[%s] Did NOT find Remediation: within scan window after match.", label)

        r.audit_info = extract_audit_block(pages_lines, page_i, line_i, debug_label=label)

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
    ap.add_argument("--debug", action="store_true", help="Enable debug logging")
    ap.add_argument("--log-file", default="", help="Optional log file path (default: stderr)")
    args = ap.parse_args()

    doc1 = read_doc1(args.doc1)
    doc2 = read_doc2(args.doc2)
    reqs = correlate(doc1, doc2)

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(message)s",
            filename=(args.log_file or None),
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(message)s",
            filename=(args.log_file or None),
        )
    
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
