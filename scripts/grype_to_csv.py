#!/usr/bin/env python3
"""
grype_to_csv.py

Converts Grype vulnerability scan JSON outputs to a single CSV file.
Filename is used to derive the container name (e.g. "book_server_vulns.json" -> "book_server").

Usage:
    python grype_to_csv.py <input1.json> [input2.json ...] -o output.csv
    python grype_to_csv.py *.json -o output.csv
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def container_name_from_filename(filepath: str) -> str:
    """Derive container name from filename by stripping suffix and extension."""
    stem = Path(filepath).stem  # e.g. "book_server_vulns"
    # Strip common suffixes like _vulns, _vulnerabilities, _scan, _report
    stem = re.sub(r'[_-]?(vulns?|vulnerabilit(?:y|ies)|scan|report)$', '', stem, flags=re.IGNORECASE)
    return stem.strip('_-')


def extract_vulnerabilities(data: dict) -> list[dict]:
    """Extract vulnerability dicts from a Grype JSON structure."""
    matches = data.get("matches", [])
    vulns = []
    for match in matches:
        vuln = match.get("vulnerability", {})
        if vuln:
            vulns.append(vuln)
    return vulns


def flatten_vulnerability(vuln: dict) -> dict:
    """
    Return a flat dict with only the top-level keys of a vulnerability.
    Nested values (dicts/lists) are stored as raw JSON strings.
    """
    flat = {}
    for key, value in vuln.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value)
        else:
            flat[key] = value
    return flat


def process_files(input_files: list[str]) -> tuple[list[str], list[dict]]:
    """
    Process all input JSON files and return (fieldnames, rows).
    Fieldnames are ordered: container first, then all discovered vuln keys.
    """
    all_rows = []
    all_vuln_keys: list[str] = []
    seen_keys: set[str] = set()

    for filepath in input_files:
        container = container_name_from_filename(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: Skipping {filepath}: {e}", file=sys.stderr)
            continue

        vulns = extract_vulnerabilities(data)
        if not vulns:
            print(f"WARNING: No vulnerabilities found in {filepath}", file=sys.stderr)

        for vuln in vulns:
            flat = flatten_vulnerability(vuln)
            # Track key order of first appearance
            for key in flat:
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_vuln_keys.append(key)
            flat["container"] = container
            all_rows.append(flat)

    fieldnames = ["container"] + all_vuln_keys
    return fieldnames, all_rows


def write_csv(fieldnames: list[str], rows: list[dict], output_path: str) -> None:
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', restval='')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Grype vulnerability scan JSON files to a single CSV."
    )
    parser.add_argument(
        "input_files",
        nargs='+',
        help="One or more Grype JSON scan output files."
    )
    parser.add_argument(
        "-o", "--output",
        default="vulnerabilities.csv",
        help="Output CSV filename (default: vulnerabilities.csv)."
    )
    args = parser.parse_args()

    fieldnames, rows = process_files(args.input_files)

    if not rows:
        print("ERROR: No vulnerability data found in any input file.", file=sys.stderr)
        sys.exit(1)

    write_csv(fieldnames, rows, args.output)
    print(f"Written {len(rows)} vulnerabilities from {len(args.input_files)} file(s) to '{args.output}'.")


if __name__ == "__main__":
    main()
