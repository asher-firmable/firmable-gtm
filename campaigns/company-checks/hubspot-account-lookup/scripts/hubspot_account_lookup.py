#!/usr/bin/env python3
"""
HubSpot account lookup — appends account/owner/deal columns to a company CSV.

Matches each row to a HubSpot company by domain (from a website/domain column).
If no domain is present but a Firmable ID is, resolves the domain via Firmable
first, then matches on that. Preserves every existing column in the input CSV
and appends the new columns at the end (does not replace the input schema).

Usage:
    PYTHONPATH=. python3 campaigns/company-checks/hubspot-account-lookup/scripts/hubspot_account_lookup.py \
        --input  campaigns/company-checks/hubspot-account-lookup/input/<file>.csv \
        --output campaigns/company-checks/hubspot-account-lookup/output/<file>_enriched.csv
"""

import argparse
import csv
import os
import time
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from scripts.firmable_api import FirmableClient
from scripts.hubspot_client import HubSpotClient

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────

HS_PROPERTIES = [
    "name", "domain",
    "hubspot_owner_id",
    "company_owner_nz",
    "company_owner_sea",
    "sdr__new_",
    "sdr_sea",
    "customer_status",
]

NEW_COLUMNS = [
    "account_owner",
    "account_owner_anz",
    "account_owner_sea",
    "sdr_anz",
    "sdr_sea",
    "open_deal",
    "deal_owner",
    "paying_customer",
    "hubspot_url",
]

CLOSED_STAGES = {"closedwon", "closedlost"}

MULTI_TLDS = {
    ".com.au", ".net.au", ".org.au", ".gov.au",
    ".co.nz", ".org.nz",
    ".co.uk", ".org.uk", ".gov.uk",
    ".com.sg", ".com.hk", ".com.tw",
    ".net.cn", ".com.cn",
    ".co.jp", ".co.kr",
}
GENERIC_SLDS = {"net", "com", "org", "gov", "edu", "int", "mil", "co", "or"}

DOMAIN_COLS = ("website", "domain", "company_website", "url")
FIRMABLE_ID_COLS = ("firmable_id", "firmable id", "firmable_company_id")
NAME_COLS = ("company_name", "name", "company")

REQUEST_DELAY = 0.2  # seconds between HubSpot API calls


# ── Domain helpers ────────────────────────────────────────────────────────────

def extract_bare_domain(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    netloc = urlparse(raw).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def extract_sld(domain: str) -> str:
    for multi in MULTI_TLDS:
        if domain.endswith(multi):
            base = domain[: -len(multi)]
            return base.split(".")[-1]
    parts = domain.split(".")
    candidate = parts[-2] if len(parts) >= 2 else domain
    if candidate in GENERIC_SLDS:
        candidate = parts[-3] if len(parts) >= 3 else ""
    return candidate


def resolve_domain_via_firmable(fm: FirmableClient, firmable_id: str) -> str:
    """Look up a Firmable company by ID and return its bare domain, or ''."""
    try:
        company = fm.lookup_company_by_id(firmable_id)
        if not company:
            return ""
        raw = company.get("domain") or company.get("website") or company.get("fqdn") or ""
        return extract_bare_domain(raw)
    except Exception:
        return ""


# ── HubSpot helpers ───────────────────────────────────────────────────────────

def find_hs_company(hs: HubSpotClient, bare_domain: str) -> Optional[dict]:
    """Exact domain match, falling back to SLD CONTAINS_TOKEN, preferring a domain containing bare_domain."""
    results = hs._post("/crm/v3/objects/companies/search", {
        "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": bare_domain}]}],
        "properties": HS_PROPERTIES,
        "limit": 5,
    }).get("results", [])
    if results:
        return results[0]

    sld = extract_sld(bare_domain)
    if not sld:
        return None

    results = hs._post("/crm/v3/objects/companies/search", {
        "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "CONTAINS_TOKEN", "value": sld}]}],
        "properties": HS_PROPERTIES,
        "limit": 10,
    }).get("results", [])
    if not results:
        return None

    for r in results:
        if bare_domain in (r["properties"].get("domain") or ""):
            return r
    return results[0]


def build_owner_map(hs: HubSpotClient) -> dict:
    return {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in hs.get_owners()
    }


def get_open_deals(hs: HubSpotClient, company_id: str) -> list:
    """Return list of {dealstage, hubspot_owner_id} for deals not in a closed stage."""
    deal_ids = hs.get_associated_ids("companies", company_id, "deals")
    if not deal_ids:
        return []
    deals = hs.batch_get_objects("deals", deal_ids, ["dealstage", "hubspot_owner_id"])
    return [
        d.get("properties", {})
        for d in deals
        if d.get("properties", {}).get("dealstage") not in CLOSED_STAGES
    ]


def hs_url(portal_id: str, record_id: str) -> str:
    return f"https://app.hubspot.com/contacts/{portal_id}/record/0-2/{record_id}"


# ── CSV helpers ───────────────────────────────────────────────────────────────

def detect_col(headers: list, candidates: tuple) -> Optional[str]:
    low = [h.lower() for h in headers]
    for c in candidates:
        if c in low:
            return headers[low.index(c)]
    return None


def build_new_columns(
    hs_record: Optional[dict],
    portal_id: str,
    owner_map: dict,
    open_deals: list,
) -> dict:
    if not hs_record:
        return {col: "" for col in NEW_COLUMNS}

    props = hs_record["properties"]
    account_owner_id = str(props.get("hubspot_owner_id") or "")
    account_owner_anz_id = str(props.get("company_owner_nz") or "")
    account_owner_sea_id = str(props.get("company_owner_sea") or "")

    has_open = len(open_deals) > 0
    deal_owner_ids = {str(d.get("hubspot_owner_id")) for d in open_deals if d.get("hubspot_owner_id")}
    deal_owner_names = "; ".join(sorted(owner_map.get(oid, "") for oid in deal_owner_ids if owner_map.get(oid, "")))

    return {
        "account_owner": owner_map.get(account_owner_id, ""),
        "account_owner_anz": owner_map.get(account_owner_anz_id, ""),
        "account_owner_sea": owner_map.get(account_owner_sea_id, ""),
        "sdr_anz": props.get("sdr__new_") or "",
        "sdr_sea": props.get("sdr_sea") or "",
        "open_deal": "Yes" if has_open else "No",
        "deal_owner": deal_owner_names,
        "paying_customer": "Yes" if props.get("customer_status") == "Paying Customer" else "No",
        "hubspot_url": hs_url(portal_id, hs_record["id"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Append HubSpot account/owner/deal columns to a company CSV")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    domain_col = detect_col(fieldnames, DOMAIN_COLS)
    firmable_id_col = detect_col(fieldnames, FIRMABLE_ID_COLS)
    name_col = detect_col(fieldnames, NAME_COLS)
    if not domain_col and not firmable_id_col:
        raise SystemExit("ERROR: No website/domain or firmable_id column found in input CSV.")

    hs = HubSpotClient()
    fm = FirmableClient()
    portal_id = hs.get_portal_id()
    owner_map = build_owner_map(hs)

    out_rows = []
    matched = 0
    for i, row in enumerate(rows, 1):
        label = (row.get(name_col) or "").strip() if name_col else f"row {i}"
        raw_url = (row.get(domain_col) or "").strip() if domain_col else ""
        firmable_id = (row.get(firmable_id_col) or "").strip() if firmable_id_col else ""

        print(f"[{i}/{len(rows)}] {label}", end=" ... ", flush=True)

        bare = extract_bare_domain(raw_url)
        if not bare and firmable_id:
            bare = resolve_domain_via_firmable(fm, firmable_id)

        if not bare:
            print("SKIP (no domain, no resolvable Firmable ID)")
            out_rows.append({**row, **build_new_columns(None, portal_id, owner_map, [])})
            continue

        hs_record = find_hs_company(hs, bare)
        open_deals = get_open_deals(hs, hs_record["id"]) if hs_record else []
        new_cols = build_new_columns(hs_record, portal_id, owner_map, open_deals)
        out_rows.append({**row, **new_cols})

        if hs_record:
            matched += 1
            print(f"MATCHED → {hs_record['properties'].get('name', '')}")
        else:
            print("NO MATCH")

        time.sleep(REQUEST_DELAY)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out_fieldnames = fieldnames + NEW_COLUMNS
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nDone — matched {matched}/{len(out_rows)} → {args.output}")


if __name__ == "__main__":
    main()
