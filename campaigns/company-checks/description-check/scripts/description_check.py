"""
Description Check — data extraction and result writing utility.

No AI logic here. This script either:
  - extract mode: reads the input file and prints a JSON batch for Claude to evaluate
  - write mode: accepts a JSON array of results and writes/appends to the output CSV

Run from repo root:
  PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --start 0 --count 10
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from scripts.utils import load_csv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

NAME_COLS = ["company_name", "name", "company"]
DOMAIN_COLS = ["website", "domain", "company_website", "company_domain", "url"]
DESC_COLS = ["description", "company_description", "about", "overview", "summary"]


def _find_latest_input() -> Path:
    files = list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return max(files, key=lambda f: f.stat().st_mtime)


def _detect_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    lower_cols = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_cols:
            return lower_cols[candidate.lower()]
    return None


def run_extract(args):
    input_path = Path(args.input) if args.input else _find_latest_input()
    df = load_csv(str(input_path))

    name_col = _detect_column(df, NAME_COLS)
    domain_col = _detect_column(df, DOMAIN_COLS)
    desc_col = _detect_column(df, DESC_COLS)

    if desc_col is None:
        available = list(df.columns)
        print(
            json.dumps({
                "error": f"No description column found. Available columns: {available}. "
                         f"Expected one of: {DESC_COLS}"
            })
        )
        sys.exit(1)

    total = len(df)
    batch = df.iloc[args.start : args.start + args.count]

    rows = []
    for i, (_, row) in enumerate(batch.iterrows()):
        desc_val = row.get(desc_col, "") if desc_col else ""
        desc_str = str(desc_val).strip() if pd.notna(desc_val) and str(desc_val).strip() else None

        rows.append({
            "row_num": args.start + i + 1,
            "company_name": str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else "",
            "domain": str(row[domain_col]).strip() if domain_col and pd.notna(row.get(domain_col)) else "",
            "description": desc_str,
        })

    print(json.dumps({"total": total, "start": args.start, "count": len(rows), "rows": rows}, indent=2))


def run_write(args):
    if not args.output:
        print("Error: --output is required in write mode", file=sys.stderr)
        sys.exit(1)

    if args.results_file:
        with open(args.results_file, "r") as f:
            results = json.load(f)
    elif args.results_json:
        results = json.loads(args.results_json)
    else:
        print("Error: either --results-json or --results-file is required in write mode", file=sys.stderr)
        sys.exit(1)

    new_df = pd.DataFrame(results, columns=["row_num", "company_name", "domain", "result"])

    output_path = OUTPUT_DIR / args.output
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.append and output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined.to_csv(output_path, index=False)
        print(f"Appended {len(new_df)} rows → {output_path} ({len(combined)} total rows)")
    else:
        new_df.to_csv(output_path, index=False)
        print(f"Wrote {len(new_df)} rows → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Description check — extract or write mode.")
    parser.add_argument("--mode", choices=["extract", "write"], default="extract")
    parser.add_argument("--input", help="Path to input CSV/Excel (default: latest file in input/)")
    parser.add_argument("--start", type=int, default=0, help="Row index to start from (0-based, extract mode)")
    parser.add_argument("--count", type=int, default=10, help="Number of rows to process (extract mode)")
    parser.add_argument("--output", help="Output filename in description-check/output/ (write mode)")
    parser.add_argument("--results-json", dest="results_json", help="JSON array of result objects (write mode)")
    parser.add_argument("--results-file", dest="results_file", help="Path to JSON file of result objects (write mode, alternative to --results-json)")
    parser.add_argument("--append", action="store_true", help="Append to existing output CSV (write mode)")
    args = parser.parse_args()

    if args.mode == "extract":
        run_extract(args)
    else:
        run_write(args)


if __name__ == "__main__":
    main()
