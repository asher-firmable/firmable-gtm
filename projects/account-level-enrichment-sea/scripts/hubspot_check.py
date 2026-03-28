"""
HubSpot Company Existence Check
---------------------------------
Read-only script. For each company in an enriched accounts CSV, checks whether
a matching company already exists in HubSpot by domain.

Check order:
  1. Primary domain  — uses search_companies() (EQ then CONTAINS_TOKEN)
  2. Additional domains — searches hs_additional_domains with CONTAINS_TOKEN

Usage:
  PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/hubspot_check.py \
    --input "projects/account-level-enrichment-sea/output/enriched_<timestamp>.csv"
"""

import argparse
import re

from scripts.hubspot_client import HubSpotClient
from scripts.utils import load_csv


def _normalise_domain(raw: str) -> str:
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _get_company_status(hs: HubSpotClient, company_id: str) -> tuple:
    result = hs._get(
        f"/crm/v3/objects/companies/{company_id}",
        params={"properties": "lifecyclestage,trial_status"}
    )
    props = result.get("properties", {})
    lifecycle = props.get("lifecyclestage") or "unknown"
    trial = props.get("trial_status") or "—"
    return lifecycle, trial


def _search_by_additional_domain(hs: HubSpotClient, domain: str) -> list:
    payload = {
        "filterGroups": [{"filters": [{"propertyName": "hs_additional_domains", "operator": "CONTAINS_TOKEN", "value": domain}]}],
        "properties": ["hs_object_id", "name", "domain", "hs_additional_domains"],
        "limit": 5,
    }
    result = hs._post("/crm/v3/objects/companies/search", payload)
    return result.get("results", [])


def check(input_path: str) -> None:
    hs = HubSpotClient()
    df = load_csv(input_path)

    total = len(df)
    exists_rows = []
    not_found_rows = []

    for i, row in df.iterrows():
        company_name = row.get("company", row.get("name", f"row {i+1}"))
        raw_domain = str(row.get("website", row.get("Website", ""))).strip()

        if not raw_domain or raw_domain.lower() in ("nan", ""):
            print(f"[{i+1}/{total}] {company_name} — SKIP (no domain)")
            not_found_rows.append((company_name, "", "no domain"))
            continue

        domain = _normalise_domain(raw_domain)

        # Pass 1: primary domain
        try:
            matches = hs.search_companies(domain)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR: {e}")
            not_found_rows.append((company_name, domain, f"error: {e}"))
            continue

        if matches:
            hs_id = matches[0]["id"]
            lifecycle, trial = _get_company_status(hs, hs_id)
            print(f"[{i+1}/{total}] {company_name} ({domain}) → EXISTS")
            exists_rows.append((company_name, domain, hs_id, lifecycle, trial))
            continue

        # Pass 2: additional domains
        try:
            matches = _search_by_additional_domain(hs, domain)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR on additional domain search: {e}")
            not_found_rows.append((company_name, domain, f"error: {e}"))
            continue

        if matches:
            hs_id = matches[0]["id"]
            lifecycle, trial = _get_company_status(hs, hs_id)
            print(f"[{i+1}/{total}] {company_name} ({domain}) → EXISTS (via additional domain)")
            exists_rows.append((company_name, domain, hs_id, lifecycle, trial))
            continue

        print(f"[{i+1}/{total}] {company_name} ({domain}) → NOT FOUND")
        not_found_rows.append((company_name, domain, "not found"))

    customers = [r for r in exists_rows if r[3] == "customer"]

    print(f"\n{'─'*80}")
    print(f"{'Company':<28} {'Domain':<32} {'Lifecycle':<22} {'Trial Status'}")
    print(f"{'─'*80}")
    for name, domain, _, lifecycle, trial in exists_rows:
        print(f"{name:<28} {domain:<32} {lifecycle:<22} {trial}")
    for name, domain, reason in not_found_rows:
        print(f"{name:<28} {domain:<32} {'NOT FOUND':<22} —")
    print(f"{'─'*80}")
    print(f"Total: {len(exists_rows)} in HubSpot ({len(customers)} customer(s)), {len(not_found_rows)} not found")


def main():
    parser = argparse.ArgumentParser(description="Check which accounts already exist in HubSpot (read-only).")
    parser.add_argument("--input", required=True, help="Path to enriched accounts CSV")
    args = parser.parse_args()
    check(args.input)


if __name__ == "__main__":
    main()
