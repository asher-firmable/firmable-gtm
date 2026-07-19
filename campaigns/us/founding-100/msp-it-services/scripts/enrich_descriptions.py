"""
Fetch company descriptions from Firmable API by Firmable ID.

Reads a CSV with 'Firmable Company ID' and 'Company Domain', calls the Firmable
API for each row, and writes a new CSV with a 'description' column added.

Usage:
    PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/enrich_descriptions.py \
        --file "campaigns/us/founding-100/msp-it-services/input/Company Firmable ID.csv"

    # Test on first 10 rows
    PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/enrich_descriptions.py \
        --file "campaigns/us/founding-100/msp-it-services/input/Company Firmable ID.csv" \
        --limit 10
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
from dotenv import load_dotenv
from scripts.firmable_api import FirmableClient
from scripts.utils import load_csv, save_csv, ensure_dirs, timestamp

load_dotenv()


def fetch_description(client: FirmableClient, firmable_id: str, domain: str) -> str:
    try:
        company = client.lookup_company_by_id(firmable_id)
        return company.get("description", "") or ""
    except Exception as e:
        print(f"  ERROR {domain} ({firmable_id}): {e}")
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to input CSV")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N rows (for testing)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel API workers (default 5)")
    args = parser.parse_args()

    df = load_csv(args.file)

    # Normalise column names (load_csv lowercases and underscores headers)
    rename = {}
    if "firmable_company_id" in df.columns:
        rename["firmable_company_id"] = "firmable_id"
    if "company_domain" in df.columns:
        rename["company_domain"] = "domain"
    if rename:
        df = df.rename(columns=rename)

    if "firmable_id" not in df.columns:
        print(f"ERROR: expected 'Firmable Company ID' column. Found: {list(df.columns)}")
        sys.exit(1)

    if args.limit:
        df = df.head(args.limit)
        print(f"Limit: processing first {len(df)} rows.")

    total = len(df)
    print(f"Loaded {total} rows. Fetching descriptions with {args.workers} workers...")

    client = FirmableClient()
    descriptions = [""] * total

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_description,
                client,
                str(row["firmable_id"]).strip(),
                str(row.get("domain", "")).strip(),
            ): i
            for i, (_, row) in enumerate(df.iterrows())
        }

        completed = 0
        for future in as_completed(futures):
            i = futures[future]
            descriptions[i] = future.result()
            completed += 1
            if completed % 100 == 0 or completed == total:
                print(f"  {completed}/{total} processed")

    df["description"] = descriptions

    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    ensure_dirs(output_dir)
    output_path = os.path.join(output_dir, f"company_with_descriptions_{timestamp()}.csv")
    save_csv(df, output_path)

    filled = sum(1 for d in descriptions if d)
    print(f"\nDone.")
    print(f"  Descriptions found: {filled}/{total}")
    print(f"  Empty/missing:      {total - filled}")
    print(f"  Output:             {output_path}")


if __name__ == "__main__":
    main()
