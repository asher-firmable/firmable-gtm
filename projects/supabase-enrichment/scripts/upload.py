"""
Upload a company CSV into the Supabase companies master table.

Usage:
    PYTHONPATH=. python3 projects/supabase-enrichment/scripts/upload.py --file path/to/companies.csv

Firmable export column mapping (case-insensitive, spaces → underscores):
    company_domain  → domain         (required)
    company         → company_name
    country         → country
    state           → state
    city            → city
    industry        → industry
    technographics  → technographics
    linkedin_url    → linkedin_url
    list_1_segment  → list_segment
    firmable_id     → firmable_id    (URL — raw ID extracted from last path segment)

ON CONFLICT (domain): updates all fields, resets status to 'pending'.
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from scripts.utils import load_csv


def main():
    parser = argparse.ArgumentParser(description="Upload companies CSV to Supabase")
    parser.add_argument("--file", required=True, help="Path to CSV or Excel file")
    parser.add_argument("--limit", type=int, default=None, help="Only upload the first N rows (useful for test runs)")
    args = parser.parse_args()

    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed. Run: pip3 install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    df = load_csv(args.file)

    # Firmable exports use 'company_domain' — treat as alias for 'domain'
    if "company_domain" in df.columns and "domain" not in df.columns:
        df = df.rename(columns={"company_domain": "domain"})

    if "domain" not in df.columns:
        print(f"ERROR: CSV must have a 'domain' or 'company_domain' column. Found: {list(df.columns)}")
        sys.exit(1)

    if args.limit:
        df = df.head(args.limit)
        print(f"Limit set — uploading first {len(df)} rows.")

    client = create_client(url, key)

    # CSV column → Supabase column mapping
    COLUMN_MAP = {
        "company":         "company_name",
        "country":         "country",
        "industry":        "industry",
        "technographics":  "technographics",
        "linkedin_url":    "linkedin_url",
        "list_1_segment":  "list_segment",
        "description":     "description",
        "zoominfo":        "zoominfo",
        "apollo":          "apollo",
        "6sense":          "six_sense",
        "cognism":         "cognism",
        "hubspot":         "hubspot",
        "salesforce":      "salesforce",
    }
    BOOL_COLS = {"zoominfo", "apollo", "six_sense", "cognism", "hubspot", "salesforce"}

    def extract_firmable_id(val: str) -> str:
        val = val.strip()
        if val.startswith("http"):
            return val.rstrip("/").split("/")[-1]
        return val

    rows = []
    for _, row in df.iterrows():
        domain = str(row["domain"]).strip().lstrip("www.").lower()
        if not domain or domain == "nan":
            continue
        record = {"domain": domain, "status": "pending"}

        for csv_col, db_col in COLUMN_MAP.items():
            if csv_col in df.columns:
                raw = row.get(csv_col)
                if db_col in BOOL_COLS:
                    if raw is not None and str(raw).strip().lower() not in ("", "nan"):
                        record[db_col] = bool(raw) if isinstance(raw, (bool,)) else str(raw).strip().lower() == "true"
                else:
                    val = str(raw).strip() if raw is not None else ""
                    if val and val != "nan":
                        record[db_col] = val

        if "firmable_id" in df.columns:
            val = str(row.get("firmable_id", "")).strip()
            if val and val != "nan":
                record["firmable_id"] = extract_firmable_id(val)

        rows.append(record)

    if not rows:
        print("No valid rows found. Check that the 'domain' column is populated.")
        sys.exit(1)

    # Upsert in batches of 500 to stay within Supabase request limits
    batch_size = 500
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table("master_companies").upsert(
            batch,
            on_conflict="domain",
            returning="minimal",
        ).execute()
        inserted += len(batch)
        print(f"  Upserted {inserted}/{len(rows)} rows...")

    print(f"\nDone. {len(rows)} companies upserted into Supabase with status='pending'.")
    print("Trigger the 'enrich-batch' task in Trigger.dev to start enrichment.")


if __name__ == "__main__":
    main()
