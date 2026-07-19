#!/usr/bin/env python3
"""
Reusable HubSpot + Firmable company check for ANZ events-outbound campaigns.

Given an exhibitor CSV (must have a domain/website column), looks up each
company in HubSpot and enriches sales team sizes in real time from Firmable.

Domain matching (HubSpot):
  1. Strip protocol, path, www. → bare domain (e.g. security.gallagher.com)
  2. domain EQ bare_domain → exact match preferred
  3. If no exact match → domain CONTAINS_TOKEN <SLD>, first result wins

Sales team size (Firmable):
  - Real-time lookup for every company, including those not in HubSpot
  - Uses FirmableClient.lookup_company(domain) then get_sales_team_size(id)

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
        --input  campaigns/anz/events-outbound/<event>/output/exhibitors.csv \
        --output campaigns/anz/events-outbound/<event>/output/hubspot_check.csv
"""

import argparse
import csv
import os
import time
from datetime import datetime
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
    "sdr__new_", "sdr_nz",
    "outreach_engagement_status", "outreach_engagement_statussea",
    "customer_status",
    "notes_last_contacted",
]

OUTPUT_COLUMNS = [
    "exists_in_hubspot",
    "found_in_firmable",
    "company_name",
    "company_website",
    "company_hubspot_url",
    "company_owner",
    "sdr_au",
    "sdr_nz",
    "outreach_engagement_status",
    "outreach_engagement_status_sea",
    "customer_status",
    "open_deal",
    "sales_team_au",
    "sales_team_nz",
    "last_contacted",
]

# Known two-part country TLDs for SLD extraction
MULTI_TLDS = {
    ".com.au", ".net.au", ".org.au", ".gov.au",
    ".co.nz", ".org.nz",
    ".co.uk", ".org.uk", ".gov.uk",
    ".com.sg", ".com.hk", ".com.tw",
    ".net.cn", ".com.cn",
    ".co.jp", ".co.kr",
}

# Generic strings that are TLD components, not real SLDs
GENERIC_SLDS = {"net", "com", "org", "gov", "edu", "int", "mil", "co", "or"}

DOMAIN_COLS = ("website", "domain", "company_website", "url")
NAME_COLS = ("name", "company_name", "company")

REQUEST_DELAY = 0.2  # seconds between HubSpot API calls


# ── Domain helpers ────────────────────────────────────────────────────────────

def extract_bare_domain(raw: str) -> str:
    """
    Return the bare domain from a URL or domain string, with www. stripped.

      https://www.hikvision.com/au-en/about  →  hikvision.com
      https://security.gallagher.com/en      →  security.gallagher.com
      shop.bgwt.com.au/                      →  shop.bgwt.com.au
    """
    raw = raw.strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    netloc = urlparse(raw).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def extract_sld(domain: str) -> str:
    """
    Extract the second-level domain name for CONTAINS_TOKEN fallback.

      security.gallagher.com  →  gallagher
      das.dickerdata.com.au   →  dickerdata
      en.tvt.net.cn           →  tvt
      hikvision.com.au        →  hikvision
    Returns "" if a meaningful SLD cannot be determined.
    """
    for multi in MULTI_TLDS:
        if domain.endswith(multi):
            base = domain[: -len(multi)]
            return base.split(".")[-1]
    parts = domain.split(".")
    candidate = parts[-2] if len(parts) >= 2 else domain
    if candidate in GENERIC_SLDS:
        candidate = parts[-3] if len(parts) >= 3 else ""
    return candidate


# ── HubSpot helpers ───────────────────────────────────────────────────────────

def find_hs_company(hs: HubSpotClient, bare_domain: str) -> Optional[dict]:
    """
    Two-step HubSpot company lookup:
      1. domain EQ bare_domain → exact match
      2. domain CONTAINS_TOKEN sld → fallback, prefer closest domain, else first result
    """
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
    """Return {owner_id_str → full_name}."""
    return {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in hs.get_owners()
    }


# ── Firmable helpers ──────────────────────────────────────────────────────────

def get_firmable_sizes(fm: FirmableClient, bare_domain: str) -> dict:
    """
    Look up a company in Firmable by domain and return real-time sales team sizes.
    Returns dict with keys: found_in_firmable, sales_team_au, sales_team_nz, sales_team_sea.
    """
    empty = {"found_in_firmable": "NO", "sales_team_au": "", "sales_team_nz": ""}
    try:
        company = fm.lookup_company(bare_domain)
        if not company:
            return empty
        company_id = company.get("id") or company.get("company_id")
        if not company_id:
            return empty
        sizes = fm.get_sales_team_size(company_id)
        return {
            "found_in_firmable": "YES",
            "sales_team_au": sizes.get("au_sales_team_size", "") if sizes.get("au_sales_team_size") is not None else "",
            "sales_team_nz": sizes.get("nz_sales_team_size", "") if sizes.get("nz_sales_team_size") is not None else "",
        }
    except Exception:
        return empty


# ── Deal helpers ─────────────────────────────────────────────────────────────

CLOSED_STAGES = {"closedwon", "closedlost"}


def has_open_deal(hs: HubSpotClient, record_id: str) -> str:
    """Return 'YES' if the company has any deal not in a closed stage, else 'NO'."""
    try:
        stages = hs.get_company_deal_stages(record_id)
        return "YES" if any(s not in CLOSED_STAGES for s in stages if s) else "NO"
    except Exception:
        return ""


# ── Formatting ────────────────────────────────────────────────────────────────

def format_date(ts) -> str:
    """Convert HubSpot timestamp to DD Mon YYYY (e.g. 04 May 2026).
    HubSpot returns either ISO 8601 strings or millisecond integers."""
    if not ts:
        return ""
    try:
        s = str(ts).strip()
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.utcfromtimestamp(int(s) / 1000)
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(ts)


def hs_url(portal_id: str, record_id: str) -> str:
    return f"https://app.hubspot.com/contacts/{portal_id}/record/0-2/{record_id}"


# ── CSV helpers ───────────────────────────────────────────────────────────────

def detect_col(headers: list, candidates: tuple) -> Optional[str]:
    low = [h.lower() for h in headers]
    for c in candidates:
        if c in low:
            return headers[low.index(c)]
    return None


def build_row(
    hs_record: Optional[dict],
    firmable: dict,
    input_name: str,
    raw_url: str,
    bare_domain: str,
    portal_id: str,
    owner_map: dict,
    open_deal: str = "",
) -> dict:
    in_hs = hs_record is not None
    props = hs_record["properties"] if in_hs else {}
    oid = str(props.get("hubspot_owner_id") or "")
    return {
        "exists_in_hubspot": "YES" if in_hs else "NO",
        "found_in_firmable": firmable["found_in_firmable"],
        "company_name": props.get("name") or input_name,
        "company_website": props.get("domain") or bare_domain or raw_url,
        "company_hubspot_url": hs_url(portal_id, hs_record["id"]) if in_hs else "",
        "company_owner": owner_map.get(oid, "") if in_hs else "",
        "sdr_au": props.get("sdr__new_") or "",
        "sdr_nz": props.get("sdr_nz") or "",
        "outreach_engagement_status": props.get("outreach_engagement_status") or "",
        "outreach_engagement_status_sea": props.get("outreach_engagement_statussea") or "",
        "customer_status": props.get("customer_status") or "",
        "open_deal": open_deal,
        "sales_team_au": firmable["sales_team_au"],
        "sales_team_nz": firmable["sales_team_nz"],
        "last_contacted": format_date(props.get("notes_last_contacted")),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HubSpot + Firmable company check for ANZ event exhibitors")
    parser.add_argument("--input", required=True, help="Path to exhibitor CSV")
    parser.add_argument("--output", required=True, help="Path for output hubspot_check.csv")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    name_col = detect_col(fieldnames, NAME_COLS)
    domain_col = detect_col(fieldnames, DOMAIN_COLS)
    if not domain_col:
        raise SystemExit("ERROR: No domain/website column found. Expected one of: " + ", ".join(DOMAIN_COLS))

    hs = HubSpotClient()
    fm = FirmableClient()
    portal_id = hs.get_portal_id()
    owner_map = build_owner_map(hs)

    out_rows = []
    for i, row in enumerate(rows, 1):
        raw_url = (row.get(domain_col) or "").strip()
        input_name = (row.get(name_col) or "").strip() if name_col else ""
        label = input_name or raw_url

        print(f"[{i}/{len(rows)}] {label}", end=" ... ", flush=True)

        bare = extract_bare_domain(raw_url)
        if not bare:
            print("SKIP (no domain)")
            out_rows.append(build_row(None, {"found_in_firmable": "NO", "sales_team_au": "", "sales_team_nz": ""}, input_name, raw_url, bare, portal_id, owner_map))
            continue

        hs_record = find_hs_company(hs, bare)
        firmable = get_firmable_sizes(fm, bare)
        open_deal = has_open_deal(hs, hs_record["id"]) if hs_record else ""

        hs_status = f"HubSpot={'YES' if hs_record else 'NO'}"
        fm_status = f"Firmable={firmable['found_in_firmable']}"
        name_found = hs_record["properties"].get("name") if hs_record else ""
        print(f"{hs_status} {fm_status}" + (f" → {name_found}" if name_found else ""))

        out_rows.append(build_row(hs_record, firmable, input_name, raw_url, bare, portal_id, owner_map, open_deal))
        time.sleep(REQUEST_DELAY)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    hs_found = sum(1 for r in out_rows if r["exists_in_hubspot"] == "YES")
    fm_found = sum(1 for r in out_rows if r["found_in_firmable"] == "YES")
    print(f"\nDone — HubSpot: {hs_found}/{len(out_rows)} | Firmable: {fm_found}/{len(out_rows)} → {args.output}")


if __name__ == "__main__":
    main()
