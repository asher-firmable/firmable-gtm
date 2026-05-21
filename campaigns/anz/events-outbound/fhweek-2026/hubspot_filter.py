"""
Filter FH Week 2026 exhibitors against HubSpot.

Reads output/exhibitors.csv and excludes companies that are:
  1. Existing customers  — trial_status in (Active Trial, Paying Customer from Trial)
                         OR lifecyclestage = customer
  2. Have open deals     — any associated deal not in a Closed Won / Closed Lost stage

Companies not in HubSpot are kept (new prospects).

Outputs:
  output/eligible_exhibitors.csv   — companies cleared for outreach
  output/excluded_exhibitors.csv   — companies excluded, with reason

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/fhweek-2026/hubspot_filter.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from scripts.hubspot_client import HubSpotClient

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT_FILE    = Path(__file__).parent / "output" / "exhibitors.csv"
ELIGIBLE_FILE = Path(__file__).parent / "output" / "eligible_exhibitors.csv"
EXCLUDED_FILE = Path(__file__).parent / "output" / "excluded_exhibitors.csv"

CUSTOMER_TRIAL_STATUSES = {"Active Trial", "Paying Customer from Trial"}

HS_COMPANY_PROPS = ["name", "domain", "trial_status", "lifecyclestage"]

REQUEST_DELAY = 0.2  # seconds between API calls

MULTI_TLDS = {
    ".com.au", ".net.au", ".org.au", ".gov.au",
    ".co.nz", ".org.nz", ".co.uk", ".com.sg",
}
GENERIC_SLDS = {"net", "com", "org", "gov", "edu", "co"}


# ---------------------------------------------------------------------------
# Helpers (reused from hubspot_check.py pattern)
# ---------------------------------------------------------------------------

def bare_domain(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    return re.sub(r"^www\.", "", netloc)


def extract_sld(domain: str) -> str:
    for multi in MULTI_TLDS:
        if domain.endswith(multi):
            return domain[: -len(multi)].split(".")[-1]
    parts = domain.split(".")
    candidate = parts[-2] if len(parts) >= 2 else domain
    if candidate in GENERIC_SLDS:
        candidate = parts[-3] if len(parts) >= 3 else ""
    return candidate


def find_hs_company(hs: HubSpotClient, domain: str):
    results = hs._post("/crm/v3/objects/companies/search", {
        "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]}],
        "properties": HS_COMPANY_PROPS,
        "limit": 5,
    }).get("results", [])
    if results:
        return results[0]

    sld = extract_sld(domain)
    if not sld:
        return None

    results = hs._post("/crm/v3/objects/companies/search", {
        "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "CONTAINS_TOKEN", "value": sld}]}],
        "properties": HS_COMPANY_PROPS,
        "limit": 10,
    }).get("results", [])
    if not results:
        return None
    for r in results:
        if domain in (r["properties"].get("domain") or ""):
            return r
    return results[0]


def get_closed_stage_ids(hs: HubSpotClient) -> set:
    """Return deal stage IDs whose label contains 'closed' (Closed Won, Closed Lost, etc.)."""
    label_map = hs.get_deal_stage_label_map()
    return {sid for sid, label in label_map.items() if "closed" in label.lower()}


def has_open_deals(hs: HubSpotClient, company_id: str, closed_stage_ids: set) -> bool:
    stages = hs.get_company_deal_stages(company_id)
    return any(s not in closed_stage_ids for s in stages if s)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} exhibitors from {INPUT_FILE.name}")

    hs = HubSpotClient()
    closed_stage_ids = get_closed_stage_ids(hs)
    print(f"Closed deal stage IDs: {closed_stage_ids}\n")

    eligible = []
    excluded = []

    for i, row in enumerate(rows, 1):
        name    = row.get("company_name", "").strip()
        website = row.get("website", "").strip()
        domain  = bare_domain(website)
        label   = name or domain

        print(f"[{i}/{len(rows)}] {label}", end=" ... ", flush=True)

        if not domain:
            print("no domain — KEEP")
            eligible.append(row)
            continue

        company = find_hs_company(hs, domain)
        time.sleep(REQUEST_DELAY)

        if not company:
            print("not in HubSpot — KEEP")
            eligible.append(row)
            continue

        props        = company["properties"]
        company_id   = company["id"]
        trial_status = (props.get("trial_status") or "").strip()
        lifecycle    = (props.get("lifecyclestage") or "").strip().lower()

        # Check 1: existing customer
        if trial_status in CUSTOMER_TRIAL_STATUSES:
            reason = f"customer ({trial_status})"
            print(f"EXCLUDE — {reason}")
            excluded.append({**row, "exclude_reason": reason})
            continue

        if lifecycle == "customer":
            reason = "customer (lifecyclestage=customer)"
            print(f"EXCLUDE — {reason}")
            excluded.append({**row, "exclude_reason": reason})
            continue

        # Check 2: open deals
        if has_open_deals(hs, company_id, closed_stage_ids):
            reason = "open deal"
            print(f"EXCLUDE — {reason}")
            excluded.append({**row, "exclude_reason": reason})
            continue

        print("KEEP")
        eligible.append(row)

    # Write outputs
    out_dir = INPUT_FILE.parent
    fieldnames = list(rows[0].keys()) if rows else []

    with open(ELIGIBLE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(eligible)

    with open(EXCLUDED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + ["exclude_reason"])
        writer.writeheader()
        writer.writerows(excluded)

    print(f"\nDone — {len(eligible)} eligible → {ELIGIBLE_FILE.name}")
    print(f"       {len(excluded)} excluded → {EXCLUDED_FILE.name}")
    if excluded:
        from collections import Counter
        reasons = Counter(r["exclude_reason"].split(" (")[0] for r in excluded)
        for reason, count in reasons.items():
            print(f"         {count}x {reason}")


if __name__ == "__main__":
    main()
