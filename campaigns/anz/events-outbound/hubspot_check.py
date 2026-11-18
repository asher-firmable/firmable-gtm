#!/usr/bin/env python3
"""
Reusable HubSpot + Firmable company check for ANZ events-outbound campaigns.

Given an exhibitor CSV (must have a domain/website column), looks up each
company in HubSpot and Firmable and computes an eligibility Status/Reason —
all in a single pass (one HubSpot company lookup, one Firmable lookup, plus
a conditional deals/tasks check per company).

Domain matching (HubSpot):
  1. Strip protocol, path, www. → bare domain (e.g. security.gallagher.com)
  2. domain EQ bare_domain → exact match preferred
  3. If no exact match → domain CONTAINS_TOKEN <SLD>, first result wins

Firmable enrichment:
  - Real-time lookup for every company, including those not in HubSpot
  - One FirmableClient.lookup_company(domain) call returns firmable_id +
    hq_country; one get_sales_team_size(id) call returns AU/NZ/SEA/US
    headcount — no duplicate calls for fields that share a response.

Status/Reason (computed, priority order — first match wins):
  1. Already customer or trialing (customer_status)
  2. Open deal (any non-closed deal on the company)
  3. Next step scheduled — only checked when an SDR (AU/NZ/SEA) is assigned
     and the company is otherwise clear of 1-2 (an open/NOT_STARTED task)
  4. No Firmable match
  Else: Eligible.
  Contacted in the last 30 days (notes_last_contacted) does NOT make a company
  ineligible (rule changed 2026-11-12). If an otherwise-eligible company was
  contacted recently, Reason carries the note
  "Contacted in last 30 days (last contact DD Mon YYYY)".

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
        --input  campaigns/anz/events-outbound/<event>/output/exhibitors.csv \
        --output campaigns/anz/events-outbound/<event>/output/hubspot_check.csv
"""

import argparse
import csv
import os
import time
from datetime import datetime, timezone
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
    "sdr__new_", "sdr_nz", "sdr_sea",
    "company_owner_nz", "company_owner_sea",
    "outreach_engagement_status", "outreach_engagement_statussea",
    "customer_status",
    "notes_last_contacted",
]

OUTPUT_COLUMNS = [
    "exists_in_hubspot",
    "found_in_firmable",
    "firmable_id",
    "company_name",
    "company_website",
    "tier",
    "stand",
    "status",
    "reason",
    "company_hubspot_url",
    "company_owner",
    "company_owner_anz",
    "company_owner_sea",
    "sdr_au",
    "sdr_nz",
    "sdr_sea",
    "outreach_engagement_status",
    "outreach_engagement_status_sea",
    "customer_status",
    "open_deal",
    "deal_owner",
    "sales_team_au",
    "sales_team_nz",
    "sales_team_sea",
    "sales_team_us",
    "sales_team_anz",
    "hq_country",
    "last_contacted",
]

CUSTOMER_TRIAL_STATUSES = {"Paying Customer", "Trialing Customer"}
CUTOFF_DAYS = 30

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
TIER_COLS = ("tier", "category")
STAND_COLS = ("stand", "booth", "booth_number")

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

FIRMABLE_EMPTY = {
    "found_in_firmable": "NO", "firmable_id": "",
    "sales_team_au": "", "sales_team_nz": "", "sales_team_sea": "", "sales_team_us": "",
    "hq_country": "",
}


def get_firmable_sizes(fm: FirmableClient, bare_domain: str) -> dict:
    """
    Look up a company in Firmable by domain and return real-time sales team sizes
    plus HQ country. One lookup_company call (id + hq_country) + one
    get_sales_team_size call (AU/NZ/SEA/US in one response) — no duplicate calls.
    """
    try:
        company = fm.lookup_company(bare_domain)
        if not company:
            return dict(FIRMABLE_EMPTY)
        company_id = company.get("id") or company.get("company_id")
        if not company_id:
            return dict(FIRMABLE_EMPTY)
        sizes = fm.get_sales_team_size(company_id)

        def val(key):
            v = sizes.get(key)
            return v if v is not None else ""

        return {
            "found_in_firmable": "YES",
            "firmable_id": company_id,
            "sales_team_au": val("au_sales_team_size"),
            "sales_team_nz": val("nz_sales_team_size"),
            "sales_team_sea": val("sea_sales_team_size"),
            "sales_team_us": val("us_sales_team_size"),
            "hq_country": company.get("hq_country") or "",
        }
    except Exception:
        return dict(FIRMABLE_EMPTY)


def compute_anz_size(sales_team_au, sales_team_nz):
    """AU + NZ sales team size. Blank only if both inputs are blank."""
    if sales_team_au == "" and sales_team_nz == "":
        return ""
    au_val = sales_team_au if sales_team_au != "" else 0
    nz_val = sales_team_nz if sales_team_nz != "" else 0
    return au_val + nz_val


# ── Deal helpers ─────────────────────────────────────────────────────────────

CLOSED_STAGES = {"closedwon", "closedlost"}


def get_deal_info(hs: HubSpotClient, company_id: str, owner_map: dict) -> tuple:
    """
    Return (open_deal, deal_owner) for a company's associated deals in one pass:
    open_deal is 'YES'/'NO', deal_owner is the resolved name(s) of the owner(s)
    of any deal not in a closed stage (comma-joined if more than one).
    """
    try:
        deal_ids = hs.get_associated_ids("companies", company_id, "deals")
        if not deal_ids:
            return "NO", ""
        deals = hs.batch_get_objects("deals", deal_ids, ["dealstage", "hubspot_owner_id"])
        has_open = False
        owner_ids = []
        for d in deals:
            props = d.get("properties", {})
            stage = props.get("dealstage") or ""
            if stage and stage not in CLOSED_STAGES:
                has_open = True
                oid = str(props.get("hubspot_owner_id") or "")
                if oid:
                    owner_ids.append(oid)
        owner_names = sorted({owner_map.get(oid, "") for oid in owner_ids if owner_map.get(oid, "")})
        return ("YES" if has_open else "NO"), ", ".join(owner_names)
    except Exception:
        return "", ""


# ── Task / eligibility helpers ────────────────────────────────────────────────

def parse_hs_timestamp_ms(raw) -> int:
    """Parse a HubSpot timestamp (ms-int string or ISO-8601) to milliseconds. 0 if unparseable/blank."""
    if not raw:
        return 0
    raw = str(raw).strip()
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def is_contacted_recently(raw_last_contacted, now_ms: int) -> bool:
    """True if notes_last_contacted falls within the last CUTOFF_DAYS."""
    ts_ms = parse_hs_timestamp_ms(raw_last_contacted)
    if ts_ms == 0:
        return False
    return ts_ms >= now_ms - CUTOFF_DAYS * 24 * 60 * 60 * 1000


def get_active_task_info(hs: HubSpotClient, company_id: str, now_ms: int) -> tuple:
    """
    Return (has_active_task, due_date_str) for a company's open/scheduled tasks —
    a task counts as active if NOT_STARTED and its due date is blank or in the future.
    """
    try:
        task_ids = hs.get_associated_ids("companies", company_id, "tasks")
        if not task_ids:
            return False, ""
        tasks = hs.batch_get_objects("tasks", task_ids, ["hs_task_status", "hs_timestamp"])
        for t in tasks:
            props = t.get("properties", {})
            status = props.get("hs_task_status") or ""
            due_ms = parse_hs_timestamp_ms(props.get("hs_timestamp") or "")
            if status == "NOT_STARTED" and (due_ms == 0 or due_ms > now_ms):
                return True, (format_date(str(due_ms)) if due_ms else "")
        return False, ""
    except Exception:
        return False, ""


def compute_status_reason(customer_status, open_deal, is_recent, has_next_step, next_step_due, found_in_firmable,
                          last_contacted: str = "") -> tuple:
    """Priority order: customer/trial > open deal > next step scheduled > no Firmable match.

    Recent contact (last 30 days) is not an exclusion: the company stays Eligible
    and Reason carries a note so the SDR knows it was touched recently.
    """
    if customer_status in CUSTOMER_TRIAL_STATUSES:
        return "Ineligible", f"Already customer or trialing ({customer_status})"
    if open_deal == "YES":
        return "Ineligible", "Open deal"
    if has_next_step:
        return "Ineligible", f"Next step scheduled (due {next_step_due})" if next_step_due else "Next step scheduled"
    if found_in_firmable == "NO":
        return "Ineligible", "No Firmable match"
    if is_recent:
        note = f"Contacted in last 30 days (last contact {last_contacted})" if last_contacted else "Contacted in last 30 days"
        return "Eligible", note
    return "Eligible", ""


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
    tier: str = "",
    stand: str = "",
    open_deal: str = "",
    deal_owner: str = "",
    is_recent: bool = False,
    has_next_step: bool = False,
    next_step_due: str = "",
) -> dict:
    in_hs = hs_record is not None
    props = hs_record["properties"] if in_hs else {}
    oid = str(props.get("hubspot_owner_id") or "")
    owner_anz_id = str(props.get("company_owner_nz") or "")
    owner_sea_id = str(props.get("company_owner_sea") or "")
    customer_status = props.get("customer_status") or ""

    status, reason = compute_status_reason(
        customer_status, open_deal, is_recent, has_next_step, next_step_due, firmable["found_in_firmable"],
        format_date(props.get("notes_last_contacted")),
    )

    return {
        "exists_in_hubspot": "YES" if in_hs else "NO",
        "found_in_firmable": firmable["found_in_firmable"],
        "firmable_id": firmable.get("firmable_id", ""),
        "company_name": props.get("name") or input_name,
        "company_website": props.get("domain") or bare_domain or raw_url,
        "tier": tier,
        "stand": stand,
        "status": status,
        "reason": reason,
        "company_hubspot_url": hs_url(portal_id, hs_record["id"]) if in_hs else "",
        "company_owner": owner_map.get(oid, "") if in_hs else "",
        "company_owner_anz": owner_map.get(owner_anz_id, "") if in_hs else "",
        "company_owner_sea": owner_map.get(owner_sea_id, "") if in_hs else "",
        "sdr_au": props.get("sdr__new_") or "",
        "sdr_nz": props.get("sdr_nz") or "",
        "sdr_sea": props.get("sdr_sea") or "",
        "outreach_engagement_status": props.get("outreach_engagement_status") or "",
        "outreach_engagement_status_sea": props.get("outreach_engagement_statussea") or "",
        "customer_status": customer_status,
        "open_deal": open_deal,
        "deal_owner": deal_owner,
        "sales_team_au": firmable["sales_team_au"],
        "sales_team_nz": firmable["sales_team_nz"],
        "sales_team_sea": firmable["sales_team_sea"],
        "sales_team_us": firmable["sales_team_us"],
        "sales_team_anz": compute_anz_size(firmable["sales_team_au"], firmable["sales_team_nz"]),
        "hq_country": firmable["hq_country"],
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
    tier_col = detect_col(fieldnames, TIER_COLS)
    stand_col = detect_col(fieldnames, STAND_COLS)
    if not domain_col:
        raise SystemExit("ERROR: No domain/website column found. Expected one of: " + ", ".join(DOMAIN_COLS))

    hs = HubSpotClient()
    fm = FirmableClient()
    portal_id = hs.get_portal_id()
    owner_map = build_owner_map(hs)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    out_rows = []
    for i, row in enumerate(rows, 1):
        raw_url = (row.get(domain_col) or "").strip()
        input_name = (row.get(name_col) or "").strip() if name_col else ""
        tier = (row.get(tier_col) or "").strip() if tier_col else ""
        stand = (row.get(stand_col) or "").strip() if stand_col else ""
        label = input_name or raw_url

        print(f"[{i}/{len(rows)}] {label}", end=" ... ", flush=True)

        bare = extract_bare_domain(raw_url)
        if not bare:
            print("SKIP (no domain)")
            out_rows.append(build_row(None, dict(FIRMABLE_EMPTY), input_name, raw_url, bare, portal_id, owner_map, tier, stand))
            continue

        hs_record = find_hs_company(hs, bare)
        firmable = get_firmable_sizes(fm, bare)

        open_deal, deal_owner = ("", "")
        is_recent = False
        has_next_step, next_step_due = False, ""

        if hs_record:
            company_id = hs_record["id"]
            props = hs_record["properties"]
            open_deal, deal_owner = get_deal_info(hs, company_id, owner_map)
            is_recent = is_contacted_recently(props.get("notes_last_contacted"), now_ms)

            sdr_assigned = bool(props.get("sdr__new_") or props.get("sdr_nz") or props.get("sdr_sea"))
            is_customer_trial = (props.get("customer_status") or "") in CUSTOMER_TRIAL_STATUSES
            if sdr_assigned and not is_customer_trial and open_deal != "YES":
                has_next_step, next_step_due = get_active_task_info(hs, company_id, now_ms)

        hs_status = f"HubSpot={'YES' if hs_record else 'NO'}"
        fm_status = f"Firmable={firmable['found_in_firmable']}"
        name_found = hs_record["properties"].get("name") if hs_record else ""
        print(f"{hs_status} {fm_status}" + (f" → {name_found}" if name_found else ""))

        out_rows.append(build_row(
            hs_record, firmable, input_name, raw_url, bare, portal_id, owner_map,
            tier, stand, open_deal, deal_owner, is_recent, has_next_step, next_step_due,
        ))
        time.sleep(REQUEST_DELAY)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    hs_found = sum(1 for r in out_rows if r["exists_in_hubspot"] == "YES")
    fm_found = sum(1 for r in out_rows if r["found_in_firmable"] == "YES")
    eligible = sum(1 for r in out_rows if r["status"] == "Eligible")
    print(f"\nDone — HubSpot: {hs_found}/{len(out_rows)} | Firmable: {fm_found}/{len(out_rows)} | Eligible: {eligible}/{len(out_rows)} → {args.output}")


if __name__ == "__main__":
    main()
