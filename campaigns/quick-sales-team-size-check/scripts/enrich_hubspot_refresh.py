"""
HubSpot refresh: enrich a company file with core HubSpot account intel.

Adds four columns:
  - Paying Customer?     Yes / No  (lifecyclestage = "customer")
  - HubSpot Account Owner
  - Open Deal?           Yes / No
  - HubSpot Link         https://app.hubspot.com/contacts/{portalId}/company/{id}

Usage:
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_hubspot_refresh.py
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_hubspot_refresh.py --input path/to/file.csv
"""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from scripts.hubspot_client import HubSpotClient
from scripts.utils import save_csv

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

COLS_TO_ADD = ["Paying Customer?", "HubSpot Account Owner", "Company Owner (SEA)", "Open Deal?", "HubSpot Link"]
MAX_WORKERS = 10

DOMAIN_CANDIDATES = (
    "domain", "website", "fqdn", "domain_name",
    "company_website", "company_domain_name", "website_url",
)
HS_EXISTS_CANDIDATES = ("exists_in_hubspot?", "hs_exists", "exists_in_hubspot")


def _find_latest_input() -> Path:
    candidates = (
        list(INPUT_DIR.glob("*.csv"))
        + list(INPUT_DIR.glob("*.xlsx"))
        + list(INPUT_DIR.glob("*.xls"))
    )
    if not candidates:
        raise FileNotFoundError(f"No input files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _norm(columns: list[str]) -> dict[str, str]:
    return {c.lower().replace(" ", "_"): c for c in columns}


def _find_col(columns: list[str], candidates: tuple) -> str | None:
    norm = _norm(columns)
    return next((norm[k] for k in candidates if k in norm), None)


def _normalise_domain(raw: str) -> str:
    d = str(raw).strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _is_open_deal(deals: list) -> bool:
    for d in deals:
        if str(d.get("properties", {}).get("hs_is_closed", "false")).lower() != "true":
            return True
    return False


def enrich(input_path: str) -> str:
    p = Path(input_path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(input_path, dtype=str)
    else:
        df = pd.read_csv(input_path, dtype=str)
    df = df.fillna("")

    cols = list(df.columns)
    domain_col = _find_col(cols, DOMAIN_CANDIDATES)
    hs_exists_col = _find_col(cols, HS_EXISTS_CANDIDATES)

    if not domain_col:
        raise ValueError(f"No domain column found. Columns: {cols}")

    print(f"Domain column:    {domain_col}")
    print(f"HS exists column: {hs_exists_col or '(none — will search all)'}")
    print(f"Enriching {len(df)} rows...")

    hs = HubSpotClient()
    portal_id = hs.get_portal_id()
    owner_map = {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in hs.get_owners()
    }

    # --- Phase 1: collect unique domains to look up ---
    # Build a mapping: domain -> set of row indices that need it
    domain_to_rows: dict[str, list[int]] = {}
    skip_results: dict[int, dict] = {}  # rows we can answer without an API call

    for i, row in df.iterrows():
        raw_domain = str(row.get(domain_col, "")).strip()
        hs_exists = str(row.get(hs_exists_col, "")).strip() if hs_exists_col else ""

        if not raw_domain or raw_domain.lower() in ("nan", ""):
            skip_results[i] = {"paying_customer": "", "hs_owner": "", "sea_owner": "", "open_deal": "", "hs_link": ""}
            continue

        if hs_exists_col and hs_exists.lower() == "no":
            skip_results[i] = {"paying_customer": "No", "hs_owner": "", "sea_owner": "", "open_deal": "No", "hs_link": ""}
            continue

        domain = _normalise_domain(raw_domain)
        domain_to_rows.setdefault(domain, []).append(i)

    unique_domains = list(domain_to_rows.keys())
    print(f"Unique domains to look up: {len(unique_domains)} (skipping {len(skip_results)} rows)")

    # --- Phase 2: parallel HubSpot lookup per unique domain ---
    completed = 0
    total_domains = len(unique_domains)
    domain_results: dict[str, dict] = {}

    def lookup(domain: str) -> tuple[str, dict]:
        try:
            companies = hs.search_companies(domain)
        except Exception as exc:
            return domain, {"paying_customer": "", "hs_owner": "", "sea_owner": "", "open_deal": "", "hs_link": "", "error": str(exc)}

        if not companies:
            return domain, {"paying_customer": "No", "hs_owner": "", "sea_owner": "", "open_deal": "No", "hs_link": ""}

        company_id = companies[0]["id"]
        hs_link = f"https://app.hubspot.com/contacts/{portal_id}/company/{company_id}"
        paying_customer = "No"
        hs_owner = ""
        sea_owner = ""
        open_deal = "No"

        try:
            props = hs.get_company_properties(company_id, ["lifecyclestage", "hubspot_owner_id", "company_owner_sea"])
            if (props.get("lifecyclestage") or "").lower() == "customer":
                paying_customer = "Yes"
            owner_id = props.get("hubspot_owner_id") or ""
            hs_owner = owner_map.get(owner_id, "")
            sea_owner_id = props.get("company_owner_sea") or ""
            sea_owner = owner_map.get(sea_owner_id, "")
        except Exception:
            pass

        try:
            deal_ids = hs.get_associated_ids("companies", company_id, "deals")
            if deal_ids:
                deal_objects = hs.batch_get_objects("deals", deal_ids, ["hs_is_closed"])
                open_deal = "Yes" if _is_open_deal(deal_objects) else "No"
        except Exception:
            pass

        return domain, {"paying_customer": paying_customer, "hs_owner": hs_owner, "sea_owner": sea_owner, "open_deal": open_deal, "hs_link": hs_link}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(lookup, d): d for d in unique_domains}
        for future in as_completed(futures):
            domain, result = future.result()
            domain_results[domain] = result
            completed += 1
            status = result.get("error", f"customer={result['paying_customer']} | owner={result['hs_owner'] or 'none'} | sea={result['sea_owner'] or 'none'} | open={result['open_deal']}")
            print(f"[{completed}/{total_domains}] {domain} — {status}")

    # --- Phase 3: map results back to every row ---
    paying_customers, hs_owners, sea_owners, open_deals, hs_links = [], [], [], [], []

    for i, row in df.iterrows():
        if i in skip_results:
            r = skip_results[i]
        else:
            raw_domain = str(row.get(domain_col, "")).strip()
            domain = _normalise_domain(raw_domain)
            r = domain_results.get(domain, {"paying_customer": "", "hs_owner": "", "sea_owner": "", "open_deal": "", "hs_link": ""})
        paying_customers.append(r["paying_customer"])
        hs_owners.append(r["hs_owner"])
        sea_owners.append(r["sea_owner"])
        open_deals.append(r["open_deal"])
        hs_links.append(r["hs_link"])

    # Drop existing versions of output columns if re-running
    for col in COLS_TO_ADD:
        if col in df.columns:
            df = df.drop(columns=[col])

    df["Paying Customer?"] = paying_customers
    df["HubSpot Account Owner"] = hs_owners
    df["Company Owner (SEA)"] = sea_owners
    df["Open Deal?"] = open_deals
    df["HubSpot Link"] = hs_links

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stem = p.stem
    output_path = str(OUTPUT_DIR / f"{stem}_hs.csv")
    save_csv(df, output_path)

    in_hs = sum(1 for v in hs_links if v)
    paying = sum(1 for v in paying_customers if v == "Yes")
    open_count = sum(1 for v in open_deals if v == "Yes")
    print(f"\n{'─' * 48}")
    print(f"In HubSpot:       {in_hs} / {len(df)}")
    print(f"Paying customers: {paying}")
    print(f"Open deals:       {open_count}")
    print(f"\nOutput: {output_path}")
    print(f"{'─' * 48}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Add HubSpot account intel to a company file.")
    parser.add_argument("--input", help="Path to input file (default: latest in input/)")
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    print(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
