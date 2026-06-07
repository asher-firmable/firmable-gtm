"""
Sync enrichment results from master_companies back into us_founding_100.

Run this after Trigger.dev enrich-batch has completed. It finds rows in
us_founding_100 that are still 'pending' and copies their enrichment data
from master_companies (if now 'done' or 'error').

Usage:
    PYTHONPATH=. python3 campaigns/us/msp-it-services/founding-100/scripts/sync.py

Run repeatedly until "Pending remaining: 0" — or once if you know enrichment is done.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
from dotenv import load_dotenv

load_dotenv()


def main():
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

    client = create_client(url, key)

    # Count current state
    all_rows = client.table("us_founding_100").select("status").execute().data
    counts = {}
    for r in all_rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("Current us_founding_100 status:")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")

    pending_count = counts.get("pending", 0)
    if pending_count == 0:
        print("\nNothing to sync — no pending rows.")
        return

    # Fetch pending domains from us_founding_100
    pending_domains_res = client.table("us_founding_100").select("domain").eq("status", "pending").execute()
    pending_domains = [r["domain"] for r in pending_domains_res.data]
    print(f"\nChecking master_companies for {len(pending_domains)} pending domains...")

    # Look up their current status in master_companies
    synced = 0
    batch_size = 500
    for i in range(0, len(pending_domains), batch_size):
        batch = pending_domains[i : i + batch_size]
        res = client.table("master_companies").select(
            "domain, company_type, company_type_reasoning, target_persona, "
            "persona_reasoning, website_summary, description, status, error_msg"
        ).in_("domain", batch).in_("status", ["done", "error"]).execute()

        if not res.data:
            continue

        for row in res.data:
            domain = row["domain"]
            update = {
                "company_type":           row.get("company_type"),
                "company_type_reasoning": row.get("company_type_reasoning"),
                "target_persona":         row.get("target_persona"),
                "persona_reasoning":      row.get("persona_reasoning"),
                "website_summary":        row.get("website_summary"),
                "description":            row.get("description"),
                "status":                 row["status"],
                "error_msg":              row.get("error_msg"),
            }
            # Remove None values so we don't overwrite existing data with nulls
            update = {k: v for k, v in update.items() if v is not None}
            update["status"] = row["status"]  # always write status

            client.table("us_founding_100").update(update).eq("domain", domain).execute()
            synced += 1

    # Final count
    remaining = client.table("us_founding_100").select("status").eq("status", "pending").execute()
    still_pending = len(remaining.data)

    print(f"\nSynced: {synced} rows")
    print(f"Pending remaining: {still_pending}")
    if still_pending > 0:
        print(f"  {still_pending} domains still being enriched in Trigger.dev — re-run sync.py when done.")
    else:
        print("  All rows enriched.")


if __name__ == "__main__":
    main()
