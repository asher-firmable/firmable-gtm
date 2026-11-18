"""
Full Account + Contact Enrichment
----------------------------------
Read-only enrichment for a contact list: HubSpot account status/owner/engagement/
last-contacted, HubSpot contact location, and Firmable ANZ sales team size.

Input CSV/Excel must have an 'email' column. A 'domain' column (or website/company
website alias) is required for the HubSpot company-level and Firmable columns —
rows without a resolvable domain get those columns left blank.

Usage:
  PYTHONPATH=. python3 campaigns/contact-account-enrichment/scripts/enrich_contacts.py \\
    --input campaigns/contact-account-enrichment/input/contacts.xlsx
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.hubspot_client import HubSpotClient
from scripts.firmable_api import FirmableClient
from scripts.hubspot_eligibility import _parse_hs_timestamp
from scripts.utils import load_csv, save_csv

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

EMAIL_ALIASES = ["email", "primary_work_email", "work_email"]
DOMAIN_ALIASES = ["domain", "company_website", "website", "fqdn", "company_domain_name"]

COMPANY_PROPS = ["lifecyclestage", "trial_status", "hubspot_owner_id", "outreach_engagement_status"]


def _find_latest_input() -> Path:
    candidates = list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _resolve_column(columns: list, aliases: list) -> str | None:
    norm = [c.lower().replace(" ", "_") for c in columns]
    for alias in aliases:
        if alias in norm:
            return columns[norm.index(alias)]
    return None


def _normalise_domain(raw: str) -> str:
    if not raw:
        return ""
    return (
        str(raw).strip()
        .replace("https://", "").replace("http://", "")
        .split("/")[0]
        .removeprefix("www.")
    )


def _fmt_date(raw: str) -> str:
    ms = _parse_hs_timestamp(raw) if raw else 0
    if ms <= 0:
        return ""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%-d %b %Y")


def _build_owner_map(hs: HubSpotClient) -> dict:
    owners = hs.get_owners()
    return {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in owners
    }


def _build_stage_maps(hs: HubSpotClient) -> tuple[dict, set]:
    """Return (stage_id -> label, set of stage IDs considered 'closed').

    HubSpot's pipelines endpoint doesn't expose a clean isClosed flag through the
    existing get_deal_stage_label_map() wrapper, so closed stages are inferred from
    label text (e.g. 'Closed won' / 'Closed lost') — verify against real pipeline
    labels if Open Deal? looks wrong for this portal.
    """
    label_map = hs.get_deal_stage_label_map()
    closed_ids = {sid for sid, label in label_map.items() if "closed" in label.lower()}
    return label_map, closed_ids


def _company_lookup(hs: HubSpotClient, domain: str, owner_map: dict,
                     label_map: dict, closed_ids: set, cache: dict) -> dict:
    empty = {
        "exists_in_hubspot": "", "paying_customer": "", "open_deal": "",
        "deal_stage": "", "account_owner": "", "engagement_status": "", "last_contacted": "",
    }
    if not domain:
        return dict(empty)
    if domain in cache:
        return cache[domain]

    companies = hs.search_companies(domain)
    if not companies:
        result = {**empty, "exists_in_hubspot": "No"}
        cache[domain] = result
        return result

    company_id = companies[0]["id"]
    props = hs.get_company_properties(company_id, COMPANY_PROPS)

    paying_customer = "Yes" if props.get("lifecyclestage") == "customer" else "No"
    owner_name = owner_map.get(str(props.get("hubspot_owner_id") or ""), "")
    engagement_status = props.get("outreach_engagement_status") or ""

    stage_ids = hs.get_company_deal_stages(company_id)
    open_stage_labels = [
        label_map.get(sid, sid) for sid in stage_ids if sid and sid not in closed_ids
    ]
    open_deal = "Yes" if open_stage_labels else "No"
    deal_stage = "; ".join(dict.fromkeys(open_stage_labels)) if open_deal == "Yes" else ""

    contact_ids = hs.get_associated_ids("companies", company_id, "contacts")
    last_contacted = ""
    if contact_ids:
        contacts = hs.batch_get_objects("contacts", contact_ids, ["notes_last_contacted"])
        raw_dates = [c.get("properties", {}).get("notes_last_contacted") for c in contacts]
        ms_values = [_parse_hs_timestamp(d) for d in raw_dates if d]
        if ms_values:
            last_contacted = _fmt_date(str(max(ms_values)))

    result = {
        "exists_in_hubspot": "Yes",
        "paying_customer": paying_customer,
        "open_deal": open_deal,
        "deal_stage": deal_stage,
        "account_owner": owner_name,
        "engagement_status": engagement_status,
        "last_contacted": last_contacted,
    }
    cache[domain] = result
    return result


def _contact_location(hs: HubSpotClient, email: str) -> str:
    if not email:
        return ""
    contact = hs.get_contact_by_email(email)
    if not contact:
        return ""
    props = hs.batch_get_objects("contacts", [contact["id"]], ["city", "state", "country"])
    if not props:
        return ""
    fields = props[0].get("properties", {})
    parts = [fields.get("city"), fields.get("state"), fields.get("country")]
    # HubSpot enum properties (e.g. country) are sometimes stored internally as all-lowercase;
    # title-case only fully-lowercase values so already-proper-cased ones (e.g. "VIC") are untouched.
    parts = [p.title() if p and p.islower() else p for p in parts]
    return ", ".join(p for p in parts if p)


def _firmable_lookup(fc: FirmableClient, domain: str, cache: dict) -> dict:
    empty = {"firmable_id": "", "au_sales_team_size": None, "nz_sales_team_size": None,
             "total_anz_sales_team_size": None}
    if not domain:
        return dict(empty)
    if domain in cache:
        return cache[domain]

    try:
        company = fc.lookup_company(domain)
        firmable_id = company.get("id") or company.get("companyId") or ""
        if not firmable_id:
            cache[domain] = empty
            return empty
        sizes = fc.get_sales_team_size(str(firmable_id))
        au = sizes.get("au_sales_team_size")
        nz = sizes.get("nz_sales_team_size")
        result = {
            "firmable_id": str(firmable_id),
            "au_sales_team_size": au,
            "nz_sales_team_size": nz,
            "total_anz_sales_team_size": (au or 0) + (nz or 0) if (au is not None or nz is not None) else None,
        }
    except Exception:
        result = empty

    cache[domain] = result
    return result


def enrich(input_path: str) -> str:
    df = load_csv(input_path)
    columns = list(df.columns)

    email_col = _resolve_column(columns, EMAIL_ALIASES)
    if not email_col:
        raise ValueError(f"Could not find an 'email' column. Found: {columns}")
    domain_col = _resolve_column(columns, DOMAIN_ALIASES)
    if not domain_col:
        print("Warning: no domain/website column found — HubSpot company and Firmable columns will be left blank for all rows.")

    hs = HubSpotClient()
    fc = FirmableClient()

    print("Fetching HubSpot owners and deal stage labels...")
    owner_map = _build_owner_map(hs)
    label_map, closed_ids = _build_stage_maps(hs)

    company_cache: dict = {}
    firmable_cache: dict = {}
    rows = []

    print(f"Enriching {len(df)} contacts...")
    for i, row in df.iterrows():
        email = str(row[email_col]).strip() if pd.notna(row[email_col]) else ""
        domain = _normalise_domain(row[domain_col]) if domain_col and pd.notna(row[domain_col]) else ""

        company = _company_lookup(hs, domain, owner_map, label_map, closed_ids, company_cache)
        location = _contact_location(hs, email)
        firmable = _firmable_lookup(fc, domain, firmable_cache)

        rows.append({
            "Exists in HubSpot?": company["exists_in_hubspot"],
            "Paying Customer?": company["paying_customer"],
            "Open Deal?": company["open_deal"],
            "HubSpot Deal Stage": company["deal_stage"],
            "HubSpot Account Owner": company["account_owner"],
            "HubSpot Engagement Status": company["engagement_status"],
            "Last Contacted": company["last_contacted"],
            "Location": location,
            "Firmable ID": firmable["firmable_id"],
            "AU Sales Team Size": firmable["au_sales_team_size"],
            "NZ Sales Team Size": firmable["nz_sales_team_size"],
            "Total ANZ Sales Team Size": firmable["total_anz_sales_team_size"],
        })

        if (i + 1) % 10 == 0 or (i + 1) == len(df):
            print(f"  {i + 1}/{len(df)} done")

    enrichment_df = pd.DataFrame(rows)
    out_df = pd.concat([df.reset_index(drop=True), enrichment_df], axis=1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_enriched.csv")
    save_csv(out_df, output_path)

    blank_location = int((enrichment_df["Location"] == "").sum())
    print(f"\nDone. Output: {output_path}")
    print(f"Rows with blank Location: {blank_location}/{len(df)}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Full account + contact enrichment (read-only).")
    parser.add_argument("--input", help="Path to input CSV or Excel file (default: latest file in input/)")
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    print(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
