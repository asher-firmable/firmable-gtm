"""
HubSpot Status Check — Sydney Build Expo 2026 Exhibitors
---------------------------------------------------------
Reads exhibitors.csv (name, domain) and cross-references each company against
HubSpot CRM. Outputs two CSVs:

  hubspot_status_results.csv  — all companies with full status
  outreach_candidates.csv     — only companies safe to outreach
                                (not a customer, no open deal)

Classification:
  CUSTOMER      — trial_status is "Active Trial"/"Paying Customer from Trial"
                  OR lifecyclestage == "customer"
  OPEN_DEAL     — at least one open (non-closed) deal attached to the company
  CANDIDATE     — in HubSpot but not a customer and no open deal
  NOT_IN_HUBSPOT — no HubSpot record found

Usage:
  PYTHONPATH=. python3 campaigns/anz/events-outbound/sydney-build-expo-2026/check_hubspot_status.py
"""

import csv
import time
from pathlib import Path

from scripts.hubspot_client import HubSpotClient
from scripts.firmable_api import FirmableClient

# ── Constants ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
INPUT_CSV = SCRIPT_DIR / "output" / "exhibitors.csv"
OUTPUT_FULL_CSV = SCRIPT_DIR / "output" / "hubspot_status_results.csv"
OUTPUT_CANDIDATES_CSV = SCRIPT_DIR / "output" / "outreach_candidates.csv"

CUSTOMER_TRIAL_STATUSES = {"Active Trial", "Paying Customer from Trial"}

COMPANY_PROPS = ["name", "domain", "trial_status", "lifecyclestage"]
DEAL_PROPS = ["dealname", "hs_is_closed", "dealstage"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _firmable_sales_size(fc: FirmableClient, domain: str, cache: dict) -> dict:
    """Look up Firmable APAC sales team size by domain. Caches per domain."""
    if domain in cache:
        return cache[domain]
    empty = {"apac_sales_team_size": None}
    try:
        company = fc.lookup_company(domain)
        firmable_id = str(company.get("id") or company.get("companyId") or "")
        if not firmable_id:
            cache[domain] = empty
            return empty
        sizes = fc.get_sales_team_size(firmable_id)
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        sea = sizes.get("sea_sales_team_size") or 0
        apac = au + nz + sea if (au or nz or sea) else None
        result = {"apac_sales_team_size": apac}
        cache[domain] = result
        return result
    except Exception:
        cache[domain] = empty
        return empty


def _is_deal_open(deal: dict) -> bool:
    props = deal.get("properties", {})
    closed = (props.get("hs_is_closed") or "false").lower()
    return closed != "true"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    hs = HubSpotClient()
    fc = FirmableClient()
    firmable_cache: dict = {}

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    print(f"Loaded {total} companies from {INPUT_CSV.name}\n")

    customers = []
    open_deals = []
    candidates_not_in_hs = []
    candidates_in_hs = []
    skipped = []

    output_rows = []

    for i, row in enumerate(rows, 1):
        name = (row.get("name") or "").strip()
        domain = (row.get("domain") or "").strip()
        domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].strip()

        print(f"[{i}/{total}] {name} | {domain or '(no domain)'}", end=" ... ", flush=True)

        if not domain:
            print("SKIPPED (no domain)")
            skipped.append(name)
            output_rows.append({
                "name": name, "domain": "", "hubspot_status": "SKIPPED",
                "is_customer": "", "trial_status": "", "lifecyclestage": "",
                "has_open_deal": "", "open_deal_names": "",
                "apac_sales_team_size": "",
            })
            continue

        # ── Search HubSpot ─────────────────────────────────────────────────────
        try:
            companies = hs.search_companies(domain)
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR ({e})")
            output_rows.append({
                "name": name, "domain": domain, "hubspot_status": "ERROR",
                "is_customer": "", "trial_status": "", "lifecyclestage": "",
                "has_open_deal": "", "open_deal_names": str(e),
                "apac_sales_team_size": "",
            })
            candidates_not_in_hs.append({"name": name, "domain": domain})
            continue

        if not companies:
            sizes = _firmable_sales_size(fc, domain, firmable_cache)
            print(f"NOT IN HUBSPOT (APAC sales: {sizes['apac_sales_team_size']})")
            candidates_not_in_hs.append({"name": name, "domain": domain})
            output_rows.append({
                "name": name, "domain": domain, "hubspot_status": "NOT_IN_HUBSPOT",
                "is_customer": "no", "trial_status": "", "lifecyclestage": "",
                "has_open_deal": "no", "open_deal_names": "",
                "apac_sales_team_size": sizes["apac_sales_team_size"],
            })
            continue

        # ── Fetch company properties ───────────────────────────────────────────
        company_id = companies[0]["id"]
        try:
            props = hs.get_company_properties(company_id, COMPANY_PROPS)
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR fetching props ({e})")
            output_rows.append({
                "name": name, "domain": domain, "hubspot_status": "ERROR",
                "is_customer": "", "trial_status": "", "lifecyclestage": "",
                "has_open_deal": "", "open_deal_names": str(e),
                "apac_sales_team_size": "",
            })
            candidates_not_in_hs.append({"name": name, "domain": domain})
            continue

        trial_status = props.get("trial_status") or ""
        lifecyclestage = props.get("lifecyclestage") or ""
        is_customer = trial_status in CUSTOMER_TRIAL_STATUSES or lifecyclestage == "customer"

        # ── Check open deals ───────────────────────────────────────────────────
        has_open_deal = False
        open_deal_names = []
        try:
            deal_ids = hs.get_associated_ids("companies", company_id, "deals")
            time.sleep(0.1)
            if deal_ids:
                deals = hs.batch_get_objects("deals", deal_ids, DEAL_PROPS)
                time.sleep(0.1)
                for deal in deals:
                    if _is_deal_open(deal):
                        has_open_deal = True
                        open_deal_names.append(deal.get("properties", {}).get("dealname") or "Unnamed deal")
        except Exception as e:
            print(f"ERROR fetching deals ({e})")

        # ── Classify ───────────────────────────────────────────────────────────
        sizes = {"apac_sales_team_size": None}

        if is_customer:
            status = "CUSTOMER"
            customers.append({
                "name": name, "domain": domain,
                "trial_status": trial_status, "lifecyclestage": lifecyclestage,
            })
            print(f"CUSTOMER ({trial_status or lifecyclestage})")
        elif has_open_deal:
            status = "OPEN_DEAL"
            open_deals.append({
                "name": name, "domain": domain,
                "open_deal_names": ", ".join(open_deal_names),
            })
            print(f"OPEN DEAL ({', '.join(open_deal_names)})")
        else:
            status = "CANDIDATE"
            sizes = _firmable_sales_size(fc, domain, firmable_cache)
            candidates_in_hs.append({"name": name, "domain": domain})
            print(f"CANDIDATE (APAC sales: {sizes['apac_sales_team_size']})")

        output_rows.append({
            "name": name,
            "domain": domain,
            "hubspot_status": status,
            "is_customer": "yes" if is_customer else "no",
            "trial_status": trial_status,
            "lifecyclestage": lifecyclestage,
            "has_open_deal": "yes" if has_open_deal else "no",
            "open_deal_names": ", ".join(open_deal_names),
            "apac_sales_team_size": sizes["apac_sales_team_size"],
        })

    # ── Write full results CSV ─────────────────────────────────────────────────
    OUTPUT_FULL_CSV.parent.mkdir(parents=True, exist_ok=True)
    full_fields = [
        "name", "domain", "hubspot_status", "is_customer",
        "trial_status", "lifecyclestage", "has_open_deal", "open_deal_names",
        "apac_sales_team_size",
    ]
    with open(OUTPUT_FULL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=full_fields)
        writer.writeheader()
        writer.writerows(output_rows)

    # ── Write outreach candidates CSV ──────────────────────────────────────────
    candidate_rows = [
        r for r in output_rows
        if r["hubspot_status"] in ("CANDIDATE", "NOT_IN_HUBSPOT")
    ]
    with open(OUTPUT_CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "hubspot_status", "apac_sales_team_size"])
        writer.writeheader()
        for r in candidate_rows:
            writer.writerow({
                "name": r["name"], "domain": r["domain"],
                "hubspot_status": r["hubspot_status"],
                "apac_sales_team_size": r.get("apac_sales_team_size", ""),
            })

    # ── Terminal summary ───────────────────────────────────────────────────────
    sep = "=" * 60

    print(f"\n{sep}")
    print(f"EXISTING CUSTOMERS ({len(customers)})")
    print(sep)
    if customers:
        for c in customers:
            print(f"  - {c['name']} | {c['domain']} | {c['trial_status'] or c['lifecyclestage']}")
    else:
        print("  (none)")

    print(f"\n{sep}")
    print(f"OPEN DEALS ({len(open_deals)})")
    print(sep)
    if open_deals:
        for c in open_deals:
            print(f"  - {c['name']} | {c['domain']} | Deal: {c['open_deal_names']}")
    else:
        print("  (none)")

    print(f"\n{sep}")
    candidate_total = len(candidates_in_hs) + len(candidates_not_in_hs)
    print(f"OUTREACH CANDIDATES ({candidate_total})")
    print(sep)

    if candidates_not_in_hs:
        print(f"\n  [Not in HubSpot] ({len(candidates_not_in_hs)})")
        for c in candidates_not_in_hs:
            print(f"    - {c['name']} | {c['domain']}")

    if candidates_in_hs:
        print(f"\n  [In HubSpot, no customer/deal] ({len(candidates_in_hs)})")
        for c in candidates_in_hs:
            print(f"    - {c['name']} | {c['domain']}")

    if not candidates_not_in_hs and not candidates_in_hs:
        print("  (none)")

    print(f"\n{sep}")
    print(f"SUMMARY")
    print(sep)
    print(f"  Total companies:        {total}")
    print(f"  Skipped (no domain):    {len(skipped)}")
    print(f"  Existing customers:     {len(customers)}")
    print(f"  Open deals:             {len(open_deals)}")
    print(f"  Outreach candidates:    {candidate_total}")
    print(f"    - Not in HubSpot:     {len(candidates_not_in_hs)}")
    print(f"    - In HubSpot (clean): {len(candidates_in_hs)}")
    print(f"\n  Full results:      {OUTPUT_FULL_CSV}")
    print(f"  Candidates CSV:    {OUTPUT_CANDIDATES_CSV}")


if __name__ == "__main__":
    main()
