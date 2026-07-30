"""
Black Hat US 2026 — per-company contact count overview.

Read-only: prints how many contacts are in the curated CSV per company,
sorted descending, and flags which companies exceed the 15-per-company cap
so they can be reviewed before running 4_trim_contacts.py.

Input: newest CSV/XLSX in input/.

Run:
  PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/3_contact_overview.py
"""

import argparse
import glob
import sys

from scripts.utils import ensure_dirs, load_csv, save_csv, timestamp

CAMPAIGN_DIR = "campaigns/us/events-outbound/blackhat-us-2026"
INPUT_DIR = f"{CAMPAIGN_DIR}/input"
OUTPUT_DIR = f"{CAMPAIGN_DIR}/output"
CAP = 15


def load_input(input_path=None):
    if input_path:
        files = [input_path]
    else:
        patterns = [f"{INPUT_DIR}/*.csv", f"{INPUT_DIR}/*.xlsx", f"{INPUT_DIR}/*.xls"]
        files = []
        for p in patterns:
            files.extend(glob.glob(p))
    if not files:
        print(f"No input file found in {INPUT_DIR}/. Drop your curated CSV there and retry.")
        sys.exit(1)
    path = sorted(files)[-1]
    print(f"Loading {path}")
    df = load_csv(path)
    print(f"  {len(df)} rows, columns: {list(df.columns)}\n")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None, help="Path to input CSV/XLSX (defaults to latest file in input/)")
    args = parser.parse_args()

    ensure_dirs(OUTPUT_DIR)
    df = load_input(args.input)

    if "company_name" not in df.columns:
        print(f"Could not find a company_name column. Available columns: {list(df.columns)}")
        sys.exit(1)

    counts = df.groupby("company_name").size().sort_values(ascending=False)
    over_cap = counts[counts > CAP]

    print(f"Total contacts: {len(df)}")
    print(f"Total companies: {len(counts)}")
    print(f"Companies over the {CAP}-contact cap: {len(over_cap)}")
    print(f"Contacts at those companies: {int(over_cap.sum())}")
    print(f"Contacts that would need trimming: {int(over_cap.sum()) - CAP * len(over_cap)}\n")

    print(f"{'Company':<45} {'Contacts':>8}  {'Over cap?':>9}")
    print("-" * 66)
    for company, n in counts.items():
        flag = f"YES (-{n - CAP})" if n > CAP else ""
        print(f"{company[:45]:<45} {n:>8}  {flag:>9}")

    out_path = f"{OUTPUT_DIR}/3_overview_{timestamp()}.csv"
    save_csv(counts.rename("contact_count").reset_index(), out_path)
    print(f"\nOverview written to: {out_path}")


if __name__ == "__main__":
    main()
