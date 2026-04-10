"""
Create New Companies in HubSpot (Viable — Not in HubSpot)
---------------------------------------------------------
Reads viable_not_in_hubspot.csv (saved by check_company_hubspot_status.py),
creates each company in HubSpot with the specified owner and outreach status,
and saves a Viable Companies output CSV.

ICP Match (SEA) is derived from APAC Sales HC in the input CSV:
  0–4   → SMB        (API value: true)
  5–9   → Medium     (API value: false)
  10–24 → High
  25+   → Very High

Usage:
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/create_new_companies.py \
    --owner-id <ID> --sea-owner-id <ID> --status "<status_value>"
"""

import argparse
import csv
import time
from pathlib import Path

from scripts.hubspot_client import HubSpotClient

INPUT_FILE  = Path("projects/sea-company-upload/output/viable_not_in_hubspot.csv")
OUTPUT_FILE = Path("projects/sea-company-upload/output/viable_companies_new.csv")

ICP_TIERS = [
    (25, "Very High"),
    (10, "High"),
    (5,  "false"),   # Medium
    (0,  "true"),    # SMB
]
ICP_LABELS = {"true": "SMB", "false": "Medium"}

OUTPUT_FIELDS = ["Company Name", "Domain/Website", "Firmable Company ID", "Exists in HubSpot", "Outreach Engagement Status"]


def _icp_value(apac_hc: str):
    try:
        size = int(str(apac_hc).strip())
    except (ValueError, TypeError):
        return None
    for threshold, value in ICP_TIERS:
        if size >= threshold:
            return value
    return "true"


def _icp_label(v):
    return ICP_LABELS.get(v, v) if v else "unknown"


def main():
    parser = argparse.ArgumentParser(description="Create viable companies in HubSpot.")
    parser.add_argument("--owner-id",     required=True, help="HubSpot owner ID for Company Owner (hubspot_owner_id)")
    parser.add_argument("--sea-owner-id", required=True, help="HubSpot owner ID for Company Owner (SEA) (company_owner_sea)")
    parser.add_argument("--status",       required=True, help="Outreach engagement status value (internal HubSpot value)")
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

    hs = HubSpotClient()
    portal_id = hs.get_portal_id()

    print(f"Creating {len(companies)} companies in HubSpot...\n")
    results = []

    for i, row in enumerate(companies, 1):
        name        = row.get("company_name", f"Row {i}")
        domain      = row.get("domain", "")
        firmable_id = row.get("firmable_id", "")
        apac_hc     = row.get("apac_sales_hc", "")

        iv = _icp_value(apac_hc)
        il = _icp_label(iv)

        props = {
            "name":                   name,
            "domain":                 domain,
            "hubspot_owner_id":       args.owner_id,
            "company_owner_sea":      args.sea_owner_id,
            "company_source":         "Outbound Prospecting",
            "company_source_detail":  "List Upload [Allocated accounts]",
            "outreach_engagement_status": args.status,
            "market":                 "SEA",
        }
        if iv:
            props["icp_match_sea"] = iv
        if firmable_id:
            props["firmable_id"] = firmable_id

        print(f"[{i}/{len(companies)}] {name} ({domain}) — ICP: {il}", end=" ... ", flush=True)
        try:
            result  = hs.create_company(props)
            hs_id   = result["id"]
            hs_url  = f"https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{hs_id}"
            print(f"CREATED  {hs_url}")
            results.append({
                "Company Name":              name,
                "Domain/Website":            domain,
                "Firmable Company ID":       firmable_id,
                "Exists in HubSpot":         "True",
                "Outreach Engagement Status": args.status,
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "Company Name":              name,
                "Domain/Website":            domain,
                "Firmable Company ID":       firmable_id,
                "Exists in HubSpot":         "False",
                "Outreach Engagement Status": "",
            })
        time.sleep(0.2)

    created = sum(1 for r in results if r["Exists in HubSpot"] == "True")
    print(f"\n{created}/{len(companies)} companies created successfully.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
