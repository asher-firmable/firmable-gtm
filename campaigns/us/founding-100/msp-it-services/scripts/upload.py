"""
US Founding 100 — smart upload with master_companies cache check.

For each domain in the CSV:
  - If already enriched in master_companies (status='done'): copy classification
    directly into us_founding_100 — no Trigger.dev call needed.
  - If unknown: insert into master_companies as pending (for Trigger.dev to enrich)
    and insert into us_founding_100 as pending.

Automatically triggers enrich-batch if there are pending domains.

Usage:
    PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/upload.py \\
        --file campaigns/us/founding-100/msp-it-services/input/<file>.csv

Then run sync.py once Trigger.dev finishes.
"""

import argparse
import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
from dotenv import load_dotenv
from scripts.utils import load_csv

load_dotenv()

ENRICHMENT_COLS = [
    "company_type", "company_type_reasoning",
    "target_persona", "persona_reasoning",
    "website_summary", "description",
]

COLUMN_MAP = {
    "company":        "company_name",
    "country":        "country",
    "industry":       "industry",
    "technographics": "technographics",
    "linkedin_url":   "linkedin_url",
    "list_1_segment": "list_segment",
    "description":    "description",
    "zoominfo":       "zoominfo",
    "apollo":         "apollo",
    "6sense":         "six_sense",
    "cognism":        "cognism",
    "hubspot":        "hubspot",
    "salesforce":     "salesforce",
}
BOOL_COLS = {"zoominfo", "apollo", "six_sense", "cognism", "hubspot", "salesforce"}


def extract_firmable_id(val: str) -> str:
    val = val.strip()
    if val.startswith("http"):
        return val.rstrip("/").split("/")[-1]
    return val


def parse_row(row, df_columns) -> dict:
    domain = str(row["domain"]).strip().lstrip("www.").lower()
    if not domain or domain == "nan":
        return {}
    record = {"domain": domain, "status": "pending"}

    for csv_col, db_col in COLUMN_MAP.items():
        if csv_col in df_columns:
            raw = row.get(csv_col)
            if db_col in BOOL_COLS:
                if raw is not None and str(raw).strip().lower() not in ("", "nan"):
                    record[db_col] = bool(raw) if isinstance(raw, bool) else str(raw).strip().lower() == "true"
            else:
                val = str(raw).strip() if raw is not None else ""
                if val and val != "nan":
                    record[db_col] = val

    if "firmable_id" in df_columns:
        val = str(row.get("firmable_id", "")).strip()
        if val and val != "nan":
            record["firmable_id"] = extract_firmable_id(val)

    return record


def bulk_lookup_master(client, domains: list[str]) -> dict:
    """Return dict of {domain: enrichment_data} for all 'done' rows in master_companies."""
    cached = {}
    batch_size = 500
    for i in range(0, len(domains), batch_size):
        batch = domains[i : i + batch_size]
        res = client.table("master_companies").select(
            "domain, " + ", ".join(ENRICHMENT_COLS)
        ).in_("domain", batch).eq("status", "done").execute()
        for r in res.data:
            cached[r["domain"]] = r
    return cached


def upsert_batched(client, table: str, rows: list[dict], on_conflict: str, label: str):
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i : i + 500]
        client.table(table).upsert(batch, on_conflict=on_conflict, returning="minimal").execute()
        total += len(batch)
        print(f"  {label}: {total}/{len(rows)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: pip3 install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    df = load_csv(args.file)
    if "company_domain" in df.columns and "domain" not in df.columns:
        df = df.rename(columns={"company_domain": "domain"})
    if "domain" not in df.columns:
        print(f"ERROR: CSV must have a 'domain' or 'company_domain' column. Found: {list(df.columns)}")
        sys.exit(1)
    if args.limit:
        df = df.head(args.limit)
        print(f"Limit: using first {len(df)} rows.")

    # Parse all rows
    all_rows = []
    for _, row in df.iterrows():
        r = parse_row(row, df.columns)
        if r:
            all_rows.append(r)

    if not all_rows:
        print("No valid rows found.")
        sys.exit(1)

    print(f"\nLoaded {len(all_rows)} rows from CSV.")

    client = create_client(url, key)

    # Bulk check master_companies for already-enriched domains
    print("Checking master_companies cache...")
    domains = [r["domain"] for r in all_rows]
    cached = bulk_lookup_master(client, domains)
    print(f"  Cache hits (status=done): {len(cached)}")

    # Split into hits and misses
    hits, misses = [], []
    for row in all_rows:
        if row["domain"] in cached:
            enriched = cached[row["domain"]]
            row.update({k: v for k, v in enriched.items() if v is not None})
            row["status"] = "done"
            hits.append(row)
        else:
            misses.append(row)

    print(f"  Pre-filled from cache: {len(hits)}")
    print(f"  Pending enrichment:    {len(misses)}")

    # Insert cache misses into master_companies (DO NOTHING if domain already exists)
    if misses:
        print(f"\nInserting {len(misses)} new domains into master_companies...")
        master_rows = [{k: v for k, v in r.items()} for r in misses]
        for i in range(0, len(master_rows), 500):
            batch = master_rows[i : i + 500]
            # DO NOTHING on conflict — never overwrite existing master_companies rows
            client.table("master_companies").upsert(
                batch,
                on_conflict="domain",
                returning="minimal",
                ignore_duplicates=True,
            ).execute()
        print(f"  Done.")

    # Upsert all rows into us_founding_100
    print(f"\nUpserting {len(all_rows)} rows into us_founding_100...")
    upsert_batched(client, "us_founding_100", all_rows, "domain", "us_founding_100")

    print(f"\n{'='*60}")
    print(f"Upload complete.")
    print(f"  Total rows:           {len(all_rows)}")
    print(f"  Pre-filled (cached):  {len(hits)}")
    print(f"  Pending enrichment:   {len(misses)}")

    if misses:
        trigger_key = os.getenv("TRIGGER_SECRET_KEY")
        if not trigger_key:
            print(f"\nWARNING: TRIGGER_SECRET_KEY not set — trigger enrich-batch manually.")
        else:
            print(f"\nTriggering enrich-batch for {len(misses)} pending domains...")
            r = requests.post(
                "https://api.trigger.dev/api/v1/tasks/enrich-batch/trigger",
                headers={"Authorization": f"Bearer {trigger_key}", "Content-Type": "application/json"},
                json={},
            )
            if r.status_code == 200:
                run_id = r.json().get("id", "unknown")
                print(f"  Enrichment started (run: {run_id})")
                print(f"  Monitor progress in the Trigger.dev dashboard.")
                print(f"  When done, run: PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/sync.py")
            else:
                print(f"  WARNING: Trigger.dev returned {r.status_code}: {r.text}")
                print(f"  Trigger enrich-batch manually from the Trigger.dev dashboard.")
    else:
        print("\nAll rows pre-filled from cache — no enrichment needed!")


if __name__ == "__main__":
    main()
