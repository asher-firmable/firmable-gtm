"""
Account check: HubSpot owner/deal status + Firmable ANZ sales team size.

For each company in the input CSV, looks up HubSpot by domain (owner, deal status,
last contacted, engagement status) and Firmable (AU, NZ, ANZ sales headcount).
All original columns are preserved; enrichment columns are appended.

Output columns added:
  hs_exists            — Yes / No
  hs_deal_status       — open / closed-won / closed-lost / none
  hs_deal_stage        — human-readable pipeline stage label
  hs_account_owner     — owner full name (blank if unowned or not found)
  hs_last_contacted    — D Mon YYYY (blank if never contacted)
  hs_engagement_status — outreach engagement status value
  firmable_id          — Firmable company ID
  au_sales_team_size   — AU sales headcount
  nz_sales_team_size   — NZ sales headcount
  anz_sales_team_size  — AU + NZ combined

Usage:
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_account_check.py
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_account_check.py --input path/to/file.csv
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from scripts.firmable_api import FirmableClient
from scripts.hubspot_client import HubSpotClient
from scripts.utils import load_csv, save_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

OUTREACH_STATUS_PROP = "outreach_engagement_status"

HS_OUTPUT_COLS = [
    "hs_exists", "hs_deal_status", "hs_deal_stage",
    "hs_account_owner", "hs_last_contacted", "hs_engagement_status",
]
FIRMABLE_OUTPUT_COLS = [
    "firmable_id", "au_sales_team_size", "nz_sales_team_size", "anz_sales_team_size",
]
ALL_OUTPUT_COLS = HS_OUTPUT_COLS + FIRMABLE_OUTPUT_COLS

DOMAIN_CANDIDATES = (
    "domain", "website", "fqdn", "domain_name",
    "company_website", "company_domain_name", "website_url",
)
FIRMABLE_URL_CANDIDATES = (
    "firmable_website", "firmable_company_url", "firmable_company_link",
)
FIRMABLE_ID_CANDIDATES = ("firmable_id", "id")
NAME_CANDIDATES = ("company_name", "name")


def _find_latest_input() -> Path:
    candidates = list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _norm_cols(columns: list[str]) -> dict[str, str]:
    """Map normalised column name → original column name."""
    return {c.lower().replace(" ", "_"): c for c in columns}


def _detect_columns(columns: list[str]) -> dict[str, Optional[str]]:
    norm = _norm_cols(columns)
    return {
        "firmable_id":      next((norm[k] for k in FIRMABLE_ID_CANDIDATES if k in norm), None),
        "firmable_website": next((norm[k] for k in FIRMABLE_URL_CANDIDATES if k in norm), None),
        "domain":           next((norm[k] for k in DOMAIN_CANDIDATES if k in norm), None),
        "company_name":     next((norm[k] for k in NAME_CANDIDATES if k in norm), None),
    }


def _normalise_domain(raw: str) -> str:
    d = str(raw).strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _extract_id_from_url(url: str) -> Optional[str]:
    match = re.search(r"/company/([^/?#]+)", url)
    return match.group(1) if match else None


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
    parsed = []
    for d in deals:
        props = d.get("properties", {})
        stage_id = props.get("dealstage", "")
        parsed.append({
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


def _resolve_firmable(
    i: int, firmable_id: Optional[str], domain: Optional[str],
    firmable: FirmableClient, firmable_cache: dict,
) -> dict:
    empty = {"firmable_id": "", "au_sales_team_size": "", "nz_sales_team_size": "", "anz_sales_team_size": ""}

    if not firmable_id and domain:
        if domain in firmable_cache:
            firmable_id = firmable_cache[domain]
        else:
            try:
                company = firmable.lookup_company(domain)
                firmable_id = company.get("id")
            except Exception as exc:
                log.warning(f"Row {i+1}: Firmable domain lookup failed for '{domain}': {exc}")
                firmable_id = None
            firmable_cache[domain] = firmable_id

    if not firmable_id:
        return empty

    try:
        sizes = firmable.get_sales_team_size(firmable_id)
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        return {
            "firmable_id": firmable_id,
            "au_sales_team_size": au,
            "nz_sales_team_size": nz,
            "anz_sales_team_size": au + nz,
        }
    except Exception as exc:
        log.warning(f"Row {i+1}: Firmable size lookup failed for ID '{firmable_id}': {exc}")
        return {**empty, "firmable_id": firmable_id}


def enrich(input_path: str) -> str:
    df = load_csv(input_path)
    cols = _detect_columns(list(df.columns))

    detected = {k: v for k, v in cols.items() if v is not None}
    if not detected:
        raise ValueError(
            "No usable identifier columns found. Expected at least one of: "
            "firmable_id, firmable_company_url, domain, company_name"
        )
    log.info(f"Detected identifier columns: {detected}")
    log.info(f"Enriching {len(df)} companies...")

    hs = HubSpotClient()
    firmable = FirmableClient()

    log.info("Loading HubSpot owners...")
    owner_map = {
        str(o["id"]): f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        for o in hs.get_owners()
    }
    log.info("Loading deal stage labels...")
    stage_label_map = hs.get_deal_stage_label_map()

    def _val(row: pd.Series, col_key: str) -> str:
        col = cols.get(col_key)
        if col is None:
            return ""
        v = row.get(col, "")
        return str(v).strip() if pd.notna(v) else ""

    # ── Pass 1: HubSpot (sequential — respects domain cache cleanly) ──────────
    hs_results = []
    firmable_inputs = []  # (i, firmable_id_or_none, domain_or_none)
    hs_cache: dict = {}

    total = len(df)
    for i, row in df.iterrows():
        company_name = _val(row, "company_name") or f"row {i+1}"

        # Resolve domain
        raw_domain = _val(row, "domain")
        domain = _normalise_domain(raw_domain) if raw_domain else None

        # Resolve firmable_id (from direct ID or URL — domain resolved later in Firmable pass)
        firmable_id: Optional[str] = None
        raw_id = _val(row, "firmable_id")
        if raw_id:
            firmable_id = raw_id
        if not firmable_id:
            raw_url = _val(row, "firmable_website")
            if raw_url:
                firmable_id = _extract_id_from_url(raw_url)

        firmable_inputs.append((i, firmable_id, domain))

        hs_row = {
            "hs_exists": "No",
            "hs_deal_status": "",
            "hs_deal_stage": "",
            "hs_account_owner": "",
            "hs_last_contacted": "",
            "hs_engagement_status": "",
        }

        if not domain:
            log.info(f"[{i+1}/{total}] {company_name} — SKIP HubSpot (no domain)")
            hs_results.append(hs_row)
            continue

        if domain in hs_cache:
            log.info(f"[{i+1}/{total}] {company_name} ({domain}) — HubSpot cached")
            hs_results.append(hs_cache[domain])
            continue

        try:
            companies = hs.search_companies(domain)
        except Exception as exc:
            log.warning(f"[{i+1}/{total}] {company_name} ({domain}) — HubSpot search error: {exc}")
            hs_cache[domain] = hs_row
            hs_results.append(hs_row)
            continue

        if not companies:
            log.info(f"[{i+1}/{total}] {company_name} ({domain}) → not in HubSpot")
            hs_cache[domain] = hs_row
            hs_results.append(hs_row)
            continue

        company_id = companies[0]["id"]
        hs_row["hs_exists"] = "Yes"

        try:
            props = hs.get_company_properties(
                company_id,
                ["hubspot_owner_id", "notes_last_contacted", OUTREACH_STATUS_PROP],
            )
            owner_id = props.get("hubspot_owner_id") or ""
            hs_row["hs_account_owner"] = owner_map.get(owner_id, "")
            hs_row["hs_last_contacted"] = _format_ms_date(props.get("notes_last_contacted", ""))
            hs_row["hs_engagement_status"] = props.get(OUTREACH_STATUS_PROP) or ""
        except Exception as exc:
            log.warning(f"[{i+1}/{total}] {company_name} ({domain}) — error fetching props: {exc}")

        try:
            deal_ids = hs.get_associated_ids("companies", company_id, "deals")
            if deal_ids:
                deal_objects = hs.batch_get_objects(
                    "deals", deal_ids, ["dealstage", "hs_is_closed", "hs_is_closed_won"]
                )
                status, stage_label = _classify_deals(deal_objects, stage_label_map)
                hs_row["hs_deal_status"] = status
                hs_row["hs_deal_stage"] = stage_label
            else:
                hs_row["hs_deal_status"] = "none"
        except Exception as exc:
            log.warning(f"[{i+1}/{total}] {company_name} ({domain}) — error fetching deals: {exc}")

        owner_display = hs_row["hs_account_owner"] or "unowned"
        log.info(f"[{i+1}/{total}] {company_name} ({domain}) → {hs_row['hs_deal_status']} | {owner_display}")
        hs_cache[domain] = hs_row
        hs_results.append(hs_row)

    # ── Pass 2: Firmable (parallel) ───────────────────────────────────────────
    log.info(f"\nFetching Firmable sales team sizes...")
    firmable_cache: dict = {}
    firmable_results = [None] * len(df)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_resolve_firmable, i, fid, domain, firmable, firmable_cache): i
            for i, fid, domain in firmable_inputs
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            firmable_results[i] = future.result()
            done += 1
            if done % 10 == 0 or done == len(df):
                log.info(f"  {done}/{len(df)} done")

    # ── Merge & save ──────────────────────────────────────────────────────────
    for col_name in ALL_OUTPUT_COLS:
        if col_name in df.columns:
            df = df.drop(columns=[col_name])

    enrichment_df = pd.DataFrame([{**hs, **f} for hs, f in zip(hs_results, firmable_results)])
    out_df = pd.concat([df.reset_index(drop=True), enrichment_df], axis=1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stem = Path(input_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_account_check.csv")
    save_csv(out_df, output_path)

    # ── Summary ───────────────────────────────────────────────────────────────
    hs_found     = sum(1 for r in hs_results if r.get("hs_exists") == "Yes")
    open_count   = sum(1 for r in hs_results if r.get("hs_deal_status") == "open")
    won_count    = sum(1 for r in hs_results if r.get("hs_deal_status") == "closed-won")
    lost_count   = sum(1 for r in hs_results if r.get("hs_deal_status") == "closed-lost")
    no_deal      = sum(1 for r in hs_results if r.get("hs_deal_status") == "none")
    not_found    = sum(1 for r in hs_results if r.get("hs_exists") == "No")
    f_resolved   = sum(1 for r in firmable_results if r and r.get("firmable_id"))

    log.info(f"\n{'─' * 48}")
    log.info(f"HubSpot:")
    log.info(f"  In HubSpot:     {hs_found}")
    log.info(f"    Open deal:    {open_count}")
    log.info(f"    Closed-won:   {won_count}")
    log.info(f"    Closed-lost:  {lost_count}")
    log.info(f"    No deal:      {no_deal}")
    log.info(f"  Not in HubSpot: {not_found}")
    log.info(f"Firmable resolved: {f_resolved}/{len(df)}")
    log.info(f"\nOutput: {output_path}")
    log.info(f"{'─' * 48}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Enrich company list with HubSpot owner/deal status + Firmable ANZ sales team size."
    )
    parser.add_argument(
        "--input",
        help="Path to input CSV or Excel file (default: latest file in input/)",
    )
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    log.info(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
