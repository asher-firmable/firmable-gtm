"""
Filter Asia Business Show exhibitors against HubSpot.

Removes companies that are:
  - Current customers (trial_status = "Active Trial" or "Paying Customer from Trial")
  - Have an open deal (any deal not in closedwon / closedlost)

Companies not found in HubSpot are kept (unknown prospects).

Reads:  output/exhibitors.csv
Writes: output/exhibitors_filtered.csv

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/asia-business-show-2026/hubspot_filter.py
"""

import csv
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from scripts.hubspot_client import HubSpotClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT_FILE    = Path(__file__).parent / "output" / "exhibitors.csv"
OUTPUT_FILE   = Path(__file__).parent / "output" / "exhibitors_filtered.csv"

CUSTOMER_STATUSES = {"Active Trial", "Paying Customer from Trial"}
CLOSED_STAGES     = {"closedwon", "closedlost"}
REQUEST_DELAY     = 0.2  # seconds between HubSpot calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def find_company(hs: HubSpotClient, domain: str) -> Optional[dict]:
    """Two-step domain lookup: exact EQ then CONTAINS_TOKEN fallback."""
    for operator in ("EQ", "CONTAINS_TOKEN"):
        results = hs._post("/crm/v3/objects/companies/search", {
            "filterGroups": [{"filters": [{"propertyName": "domain", "operator": operator, "value": domain}]}],
            "properties": ["hs_object_id", "name", "domain", "trial_status"],
            "limit": 5,
        }).get("results", [])
        if results:
            return results[0]
    return None


def has_open_deal(hs: HubSpotClient, company_id: str) -> bool:
    """Return True if the company has any deal not in a closed stage."""
    try:
        stages = hs.get_company_deal_stages(company_id)
        return any(s not in CLOSED_STAGES for s in stages if s)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    hs = HubSpotClient()

    kept, removed_customer, removed_open_deal = [], [], []

    for i, row in enumerate(rows, 1):
        name    = row.get("company_name", "")
        website = row.get("website", "")
        domain  = extract_domain(website)

        print(f"[{i}/{len(rows)}] {name}", end=" ... ", flush=True)

        if not domain or "linkedin.com" in domain:
            print("SKIP (no valid domain)")
            kept.append(row)
            continue

        company = find_company(hs, domain)

        if not company:
            print("not in HubSpot → KEEP")
            kept.append(row)
            time.sleep(REQUEST_DELAY)
            continue

        props        = company.get("properties", {})
        trial_status = props.get("trial_status") or ""
        company_id   = company["id"]

        if trial_status in CUSTOMER_STATUSES:
            print(f"REMOVE — customer ({trial_status})")
            removed_customer.append({**row, "removal_reason": f"customer: {trial_status}"})
            time.sleep(REQUEST_DELAY)
            continue

        if has_open_deal(hs, company_id):
            print("REMOVE — open deal")
            removed_open_deal.append({**row, "removal_reason": "open deal"})
            time.sleep(REQUEST_DELAY)
            continue

        hs_name = props.get("name") or ""
        print(f"KEEP (HubSpot: {hs_name})" if hs_name else "KEEP")
        kept.append(row)
        time.sleep(REQUEST_DELAY)

    # Write filtered CSV
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "website", "linkedin_url"])
        writer.writeheader()
        writer.writerows(kept)

    total   = len(rows)
    removed = len(removed_customer) + len(removed_open_deal)
    print(f"""
Summary
-------
Total exhibitors : {total}
Removed (customer): {len(removed_customer)}
Removed (open deal): {len(removed_open_deal)}
Total removed    : {removed}
Kept             : {len(kept)}

Output → {OUTPUT_FILE}
""")

    if removed_customer:
        print("Removed — customers:")
        for r in removed_customer:
            print(f"  {r['company_name']} | {r['website']}")

    if removed_open_deal:
        print("\nRemoved — open deals:")
        for r in removed_open_deal:
            print(f"  {r['company_name']} | {r['website']}")


if __name__ == "__main__":
    main()
