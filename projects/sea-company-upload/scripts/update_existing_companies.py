"""
Update Existing Companies in HubSpot (Viable — Already in HubSpot)
------------------------------------------------------------------
Reads viable_in_hubspot.csv (saved by check_company_hubspot_status.py),
updates Company Owner (SEA) for all companies, and optionally sets
outreach engagement status only for those with no current status.

Usage:
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/update_existing_companies.py \
    --sea-owner-id <ID> [--status "<status_value>"]

  --status is only applied to companies whose current outreach status is empty.
  Companies that already have a status are not changed.
"""

import argparse
import csv
import time
from pathlib import Path

from scripts.hubspot_client import HubSpotClient

INPUT_FILE  = Path("projects/sea-company-upload/output/viable_in_hubspot.csv")
OUTPUT_FILE = Path("projects/sea-company-upload/output/viable_companies_existing.csv")

OUTPUT_FIELDS = ["Company Name", "Domain/Website", "Firmable Company ID", "Exists in HubSpot", "Outreach Engagement Status"]


def main():
    parser = argparse.ArgumentParser(description="Update viable existing companies in HubSpot.")
    parser.add_argument("--sea-owner-id", required=True, help="HubSpot owner ID to set as Company Owner (SEA)")
    parser.add_argument("--status", required=False, default="", help="Outreach engagement status value to set (only for companies with empty status)")
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found.")
        print("Run /sea-company-upload-check first to generate the input file.")
        return

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    if not companies:
        print("No companies found in input file. Nothing to do.")
        return

    empty_status = [c for c in companies if not c.get("current_outreach_status", "").strip()]
    print(f"Loaded {len(companies)} companies from {INPUT_FILE.name}")
    print(f"  — {len(empty_status)} have empty outreach status")
    if args.status and empty_status:
        print(f"  — Will set status '{args.status}' for those {len(empty_status)} companies\n")
    elif empty_status and not args.status:
        print(f"  — No --status provided; empty-status companies will be left unchanged\n")
    else:
        print()

    hs = HubSpotClient()
    results = []

    for i, row in enumerate(companies, 1):
        name           = row.get("company_name", f"Row {i}")
        domain         = row.get("domain", "")
        firmable_id    = row.get("firmable_id", "")
        current_status = row.get("current_outreach_status", "").strip()
        hubspot_id     = row.get("hubspot_id", "").strip()

        if not hubspot_id:
            print(f"[{i}/{len(companies)}] {name} — SKIP (no HubSpot ID in input)")
            results.append({
                "Company Name":              name,
                "Domain/Website":            domain,
                "Firmable Company ID":       firmable_id,
                "Exists in HubSpot":         "True",
                "Outreach Engagement Status": current_status,
            })
            continue

        update_props   = {"company_owner_sea": args.sea_owner_id}
        final_status   = current_status

        if not current_status and args.status:
            update_props["outreach_engagement_status"] = args.status
            final_status = args.status

        status_note = f"status → {final_status}" if final_status else "status: (kept empty)"
        print(f"[{i}/{len(companies)}] {name} ({domain})", end=" ... ", flush=True)
        try:
            hs.update_company(hubspot_id, update_props)
            print(f"UPDATED  ({status_note})")
        except Exception as e:
            print(f"ERROR: {e}")

        results.append({
            "Company Name":              name,
            "Domain/Website":            domain,
            "Firmable Company ID":       firmable_id,
            "Exists in HubSpot":         "True",
            "Outreach Engagement Status": final_status,
        })
        time.sleep(0.1)

    print(f"\n{len(results)} companies processed.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
