"""Enrich a company list with US, AU, and NZ sales team sizes separately.

Accepts columns in any combination (uses best available per row, in priority order):
  firmable_id / id  →  firmable_website / firmable_company_url  →  domain / website / fqdn  →  company_name / name

Usage:
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_us_au_nz_sales.py
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_us_au_nz_sales.py --input path/to/file.csv
"""

import argparse
import logging
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd

from scripts.firmable_api import FirmableClient
from scripts.utils import load_csv, save_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

OUTPUT_COLS = ["firmable_id", "us_sales_team_size", "au_sales_team_size", "nz_sales_team_size"]

# Resolution method labels used in the summary
METHOD_DIRECT_ID  = "direct firmable_id"
METHOD_URL        = "firmable_website URL"
METHOD_DOMAIN     = "domain lookup"
METHOD_NAME       = "company_name (unresolvable)"
METHOD_EMPTY      = "no identifier"


def _find_latest_input() -> Path:
    candidates = list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _norm(columns: list[str]) -> dict[str, str]:
    """Return {normalised_name: original_name} for all columns."""
    return {c.lower().replace(" ", "_"): c for c in columns}


def _detect_columns(columns: list[str]) -> dict[str, Optional[str]]:
    """Detect which identifier columns are present. Returns {type: original_col_name or None}."""
    norm = _norm(columns)
    result: dict[str, Optional[str]] = {
        "firmable_id":      next((norm[k] for k in ("firmable_id", "id") if k in norm), None),
        "firmable_website": next((norm[k] for k in ("firmable_website", "firmable_company_url",
                                                     "firmable_company_link") if k in norm), None),
        "domain":           next((norm[k] for k in ("domain", "website", "fqdn",
                                                     "company_website", "company_domain_name",
                                                     "website_url") if k in norm), None),
        "company_name":     next((norm[k] for k in ("company_name", "name") if k in norm), None),
    }
    return result


def _extract_id_from_url(url: str) -> Optional[str]:
    """Extract Firmable company ID from a URL like .../dashboard/company/f000000117274."""
    match = re.search(r"/company/([^/?#]+)", url)
    return match.group(1) if match else None


def _resolve_row(i: int, row: pd.Series, cols: dict[str, Optional[str]],
                 client: FirmableClient, domain_cache: dict) -> dict:
    """Resolve one row to a firmable_id and fetch sales team sizes. Returns enrichment dict."""
    empty = {"firmable_id": "", "us_sales_team_size": "", "au_sales_team_size": "",
             "nz_sales_team_size": "", "_method": METHOD_EMPTY}

    def _val(col_key: str) -> str:
        col = cols.get(col_key)
        if col is None:
            return ""
        v = row.get(col, "")
        return str(v).strip() if pd.notna(v) else ""

    firmable_id = None
    method = METHOD_EMPTY

    # Priority 1: direct firmable_id
    raw_id = _val("firmable_id")
    if raw_id:
        firmable_id = raw_id
        method = METHOD_DIRECT_ID

    # Priority 2: Firmable website URL
    if not firmable_id:
        raw_url = _val("firmable_website")
        if raw_url:
            extracted = _extract_id_from_url(raw_url)
            if extracted:
                firmable_id = extracted
                method = METHOD_URL
            else:
                log.warning(f"Row {i + 1}: could not extract ID from URL '{raw_url}'")

    # Priority 3: domain lookup
    if not firmable_id:
        raw_domain = _val("domain")
        if raw_domain:
            if raw_domain in domain_cache:
                firmable_id = domain_cache[raw_domain]
            else:
                try:
                    company = client.lookup_company(raw_domain)
                    firmable_id = company.get("id")
                    domain_cache[raw_domain] = firmable_id
                except Exception as exc:
                    log.warning(f"Row {i + 1}: domain lookup failed for '{raw_domain}': {exc}")
                    domain_cache[raw_domain] = None
            if firmable_id:
                method = METHOD_DOMAIN
            else:
                log.warning(f"Row {i + 1}: domain '{raw_domain}' not found in Firmable")

    # Priority 4: company name — not resolvable without a domain, just flag it
    if not firmable_id:
        raw_name = _val("company_name")
        if raw_name:
            method = METHOD_NAME
            log.warning(f"Row {i + 1}: only company name available for '{raw_name}' — cannot resolve without domain or ID")
        return {**empty, "_method": method}

    try:
        sizes = client.get_sales_team_size(firmable_id)
        return {
            "firmable_id":        firmable_id,
            "us_sales_team_size": sizes.get("us_sales_team_size") if sizes.get("us_sales_team_size") is not None else 0,
            "au_sales_team_size": sizes.get("au_sales_team_size") if sizes.get("au_sales_team_size") is not None else 0,
            "nz_sales_team_size": sizes.get("nz_sales_team_size") if sizes.get("nz_sales_team_size") is not None else 0,
            "_method":            method,
        }
    except Exception as exc:
        log.error(f"Row {i + 1} (ID '{firmable_id}'): {exc}")
        return {**empty, "firmable_id": firmable_id, "_method": method}


def enrich(input_path: str) -> str:
    df = load_csv(input_path)
    cols = _detect_columns(list(df.columns))

    detected = {k: v for k, v in cols.items() if v is not None}
    if not detected:
        raise ValueError(
            "No usable identifier columns found. Expected at least one of: "
            "firmable_id, firmable_website, domain, company_name"
        )
    log.info(f"Detected identifier columns: {detected}")
    log.info(f"Enriching {len(df)} companies...")

    client = FirmableClient()
    domain_cache: dict = {}
    results = [None] * len(df)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_resolve_row, i, row, cols, client, domain_cache): i
            for i, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()
            done += 1
            if done % 10 == 0 or done == len(df):
                log.info(f"  {done}/{len(df)} done")

    methods = Counter(r["_method"] for r in results)
    resolved = sum(1 for r in results if r["firmable_id"])
    unresolved = len(df) - resolved

    enrichment_df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "_method"} for r in results
    ])

    # Drop existing output cols if re-running on an already-enriched file
    for col_name in OUTPUT_COLS:
        if col_name in df.columns:
            df = df.drop(columns=[col_name])

    out_df = pd.concat([df.reset_index(drop=True), enrichment_df], axis=1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stem = Path(input_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_us_au_nz.csv")
    save_csv(out_df, output_path)

    log.info(f"\n--- Summary ---")
    log.info(f"Total rows:  {len(df)}")
    log.info(f"Resolved:    {resolved}")
    log.info(f"Unresolved:  {unresolved}")
    log.info(f"Resolution breakdown:")
    for method, count in methods.most_common():
        log.info(f"  {method}: {count}")
    log.info(f"\nOutput: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Enrich companies with US, AU, and NZ sales team sizes.")
    parser.add_argument("--input", help="Path to input CSV or Excel file (default: latest file in input/)")
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    log.info(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
