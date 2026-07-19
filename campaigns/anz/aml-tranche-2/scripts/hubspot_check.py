"""
AML Tranche 2 — HubSpot Company Enrichment
-------------------------------------------
Read-only. For each company in an approved CSV (post-description-check),
looks up HubSpot by domain and enriches with deal status, account owner,
last contacted date, and outreach engagement status.

Output columns added:
  hs_exists            — Yes / No
  hs_deal_status       — open / closed-won / closed-lost / none
  hs_deal_stage        — human-readable pipeline stage label
  hs_account_owner     — owner full name
  hs_last_contacted    — D Mon YYYY
  hs_engagement_status — outreach engagement status value

Usage:
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/hubspot_check.py \\
    --input campaigns/company-checks/description-check/output/<approved_file>.csv
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

import pandas as pd

from scripts.hubspot_client import HubSpotClient
from scripts.utils import save_csv, timestamp

OUTREACH_STATUS_PROP = "outreach_engagement_status"
OUTPUT_DIR = "campaigns/anz/aml-tranche-2/output"

DOMAIN_CANDIDATES = ["website", "domain", "company_website", "company_domain", "url"]
NAME_CANDIDATES = ["company_name", "name", "company"]


def _normalise_domain(raw: str) -> str:
    d = str(raw).strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _format_ms_date(ms_str: str) -> str:
    if not ms_str:
        return ""
    try:
        ms = int(float(ms_str))
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%-d %b %Y")
    except Exception:
        return ""


def _classify_deals(deals: list, stage_label_map: dict) -> tuple[str, str]:
    """Return (deal_status, stage_label) for the most relevant deal.

    Priority: open > closed-won > closed-lost > none.
    """
    parsed = []
    for d in deals:
        props = d.get("properties", {})
        stage_id = props.get("dealstage", "")
        parsed.append({
            "stage_id": stage_id,
            "stage_label": stage_label_map.get(stage_id, stage_id),
            "is_closed": str(props.get("hs_is_closed", "false")).lower() == "true",
            "is_closed_won": str(props.get("hs_is_closed_won", "false")).lower() == "true",
        })

    open_deals = [d for d in parsed if not d["is_closed"]]
    if open_deals:
        return "open", open_deals[0]["stage_label"]

    won = [d for d in parsed if d["is_closed_won"]]
    if won:
        return "closed-won", won[0]["stage_label"]

    lost = [d for d in parsed if d["is_closed"] and not d["is_closed_won"]]
    if lost:
        return "closed-lost", lost[0]["stage_label"]

    return "none", ""


def _detect_col(columns: list[str], candidates: list[str]) -> str | None:
    lower_cols = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lower_cols:
            return lower_cols[candidate.lower()]
    return None


def enrich(input_path: str) -> None:
    hs = HubSpotClient()
    df = pd.read_csv(input_path, dtype=str).fillna("")

    name_col = _detect_col(list(df.columns), NAME_CANDIDATES)
    domain_col = _detect_col(list(df.columns), DOMAIN_CANDIDATES)

    if not domain_col:
        raise ValueError(
            f"No domain/website column found. Expected one of: {DOMAIN_CANDIDATES}\n"
            f"Columns in file: {list(df.columns)}"
        )

    print("Loading HubSpot owners...")
    owner_map = {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in hs.get_owners()
    }

    print("Loading deal stage labels...")
    stage_label_map = hs.get_deal_stage_label_map()

    domain_cache: dict = {}
    results = []
    total = len(df)

    for i, row in df.iterrows():
        company_name = str(row.get(name_col, f"row {i+1}")).strip() if name_col else f"row {i+1}"
        raw_domain = str(row.get(domain_col, "")).strip()

        new_cols: dict = {
            "hs_exists": "No",
            "hs_deal_status": "",
            "hs_deal_stage": "",
            "hs_account_owner": "",
            "hs_last_contacted": "",
            "hs_engagement_status": "",
        }

        if not raw_domain or raw_domain.lower() in ("nan", ""):
            print(f"[{i+1}/{total}] {company_name} — SKIP (no domain)")
            results.append({**row.to_dict(), **new_cols})
            continue

        domain = _normalise_domain(raw_domain)

        if domain in domain_cache:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — cached")
            results.append({**row.to_dict(), **domain_cache[domain]})
            continue

        try:
            companies = hs.search_companies(domain)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR searching: {e}")
            results.append({**row.to_dict(), **new_cols})
            continue

        if not companies:
            print(f"[{i+1}/{total}] {company_name} ({domain}) → not in HubSpot")
            domain_cache[domain] = new_cols
            results.append({**row.to_dict(), **new_cols})
            continue

        company_id = companies[0]["id"]
        new_cols["hs_exists"] = "Yes"

        try:
            props = hs.get_company_properties(
                company_id,
                ["hubspot_owner_id", "notes_last_contacted", OUTREACH_STATUS_PROP]
            )
            owner_id = props.get("hubspot_owner_id") or ""
            new_cols["hs_account_owner"] = owner_map.get(owner_id, "")
            new_cols["hs_last_contacted"] = _format_ms_date(props.get("notes_last_contacted", ""))
            new_cols["hs_engagement_status"] = props.get(OUTREACH_STATUS_PROP) or ""
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR fetching props: {e}")

        try:
            deal_ids = hs.get_associated_ids("companies", company_id, "deals")
            if deal_ids:
                deal_objects = hs.batch_get_objects(
                    "deals", deal_ids, ["dealstage", "hs_is_closed", "hs_is_closed_won"]
                )
                status, stage_label = _classify_deals(deal_objects, stage_label_map)
                new_cols["hs_deal_status"] = status
                new_cols["hs_deal_stage"] = stage_label
            else:
                new_cols["hs_deal_status"] = "none"
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR fetching deals: {e}")

        owner_display = new_cols["hs_account_owner"] or "unowned"
        print(f"[{i+1}/{total}] {company_name} ({domain}) → {new_cols['hs_deal_status']} | {owner_display}")
        domain_cache[domain] = new_cols
        results.append({**row.to_dict(), **new_cols})

    out_df = pd.DataFrame(results)
    out_path = f"{OUTPUT_DIR}/aml_hubspot_{timestamp()}.csv"
    save_csv(out_df, out_path)
    print(f"\nWritten: {out_path} ({len(results)} rows)")

    exists = sum(1 for r in results if r.get("hs_exists") == "Yes")
    open_count = sum(1 for r in results if r.get("hs_deal_status") == "open")
    won_count = sum(1 for r in results if r.get("hs_deal_status") == "closed-won")
    lost_count = sum(1 for r in results if r.get("hs_deal_status") == "closed-lost")
    no_deal = sum(1 for r in results if r.get("hs_deal_status") == "none")
    not_found = sum(1 for r in results if r.get("hs_exists") == "No")

    print(f"\n{'─' * 48}")
    print(f"In HubSpot:      {exists}")
    print(f"  Open deal:     {open_count}")
    print(f"  Closed-won:    {won_count}")
    print(f"  Closed-lost:   {lost_count}")
    print(f"  No deal:       {no_deal}")
    print(f"Not in HubSpot: {not_found}")
    print(f"{'─' * 48}")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich AML-approved company list with HubSpot deal + owner data (read-only)."
    )
    parser.add_argument("--input", required=True, help="Path to approved companies CSV")
    args = parser.parse_args()
    enrich(args.input)


if __name__ == "__main__":
    main()
