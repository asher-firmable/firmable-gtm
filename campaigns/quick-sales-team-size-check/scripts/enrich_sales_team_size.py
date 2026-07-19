"""Enrich a company list with regional sales team sizes (ANZ, SEA, US).

Usage:
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py --input path/to/file.csv
"""

import argparse
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from scripts.firmable_api import FirmableClient
from scripts.utils import load_csv, save_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"


def _find_latest_input() -> Path:
    candidates = list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _detect_id_column(columns: list[str]) -> tuple[str, str]:
    """Return (col_name, col_type) where col_type is 'firmable_id', 'firmable_url', or 'domain'."""
    norm = [c.lower().replace(" ", "_") for c in columns]
    for candidate in ("firmable_id", "id"):
        if candidate in norm:
            return columns[norm.index(candidate)], "firmable_id"
    for candidate in ("firmable_company_url", "firmable_company_link"):
        if candidate in norm:
            return columns[norm.index(candidate)], "firmable_url"
    for candidate in ("domain", "website", "fqdn", "company_website"):
        if candidate in norm:
            return columns[norm.index(candidate)], "domain"
    raise ValueError(
        f"No usable identifier column found. Expected one of: firmable_id, firmable_company_url, domain, website, company_website. Got: {columns}"
    )


def _resolve_row(i: int, row: pd.Series, col: str, col_type: str,
                 client: FirmableClient, domain_cache: dict) -> dict:
    """Return enrichment dict for one row. Returns None values on failure."""
    identifier = str(row[col]).strip() if pd.notna(row[col]) else ""
    _empty = {"firmable_id": None, "anz_sales_team_size": None, "sea_sales_team_size": None,
              "sg_sales_team_size": None, "my_sales_team_size": None,
              "hk_sales_team_size": None, "ph_sales_team_size": None,
              "apac_sales_team_size": None, "us_sales_team_size": None}

    if not identifier:
        log.warning(f"Row {i + 1}: empty identifier — skipping")
        return _empty

    try:
        if col_type == "firmable_url":
            firmable_id = identifier.rstrip("/").split("/")[-1]
        elif col_type == "domain":
            if identifier not in domain_cache:
                company = client.lookup_company(identifier)
                domain_cache[identifier] = company.get("id")
            firmable_id = domain_cache[identifier]
            if not firmable_id:
                log.warning(f"Row {i + 1}: domain '{identifier}' not found in Firmable")
                return _empty
        else:
            firmable_id = identifier

        sizes = client.get_sales_team_size(firmable_id)
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        sea = sizes.get("sea_sales_team_size") or 0
        us = sizes.get("us_sales_team_size") or 0

        return {
            "firmable_id": firmable_id,
            "anz_sales_team_size": au + nz,
            "sea_sales_team_size": sea,
            "sg_sales_team_size": sizes.get("sg_sales_team_size"),
            "my_sales_team_size": sizes.get("my_sales_team_size"),
            "hk_sales_team_size": sizes.get("hk_sales_team_size"),
            "ph_sales_team_size": sizes.get("ph_sales_team_size"),
            "apac_sales_team_size": (au + nz) + sea,
            "us_sales_team_size": us,
        }

    except Exception as exc:
        log.error(f"Row {i + 1} ('{identifier}'): {exc}")
        return _empty


def enrich(input_path: str) -> str:
    df = load_csv(input_path)
    col, col_type = _detect_id_column(list(df.columns))
    log.info(f"Using '{col}' column as identifier ({col_type})")
    log.info(f"Enriching {len(df)} companies...")

    client = FirmableClient()
    domain_cache: dict = {}
    results = [None] * len(df)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_resolve_row, i, row, col, col_type, client, domain_cache): i
            for i, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()
            done += 1
            if done % 10 == 0 or done == len(df):
                log.info(f"  {done}/{len(df)} done")

    enrichment_df = pd.DataFrame(results)

    # Drop existing output cols if re-running on an already-enriched file
    for col_name in ("firmable_id", "anz_sales_team_size", "sea_sales_team_size",
                     "sg_sales_team_size", "my_sales_team_size", "hk_sales_team_size", "ph_sales_team_size",
                     "apac_sales_team_size", "us_sales_team_size"):
        if col_name in df.columns:
            df = df.drop(columns=[col_name])

    out_df = pd.concat([enrichment_df, df.reset_index(drop=True)], axis=1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stem = Path(input_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_enriched.csv")
    save_csv(out_df, output_path)
    log.info(f"\nDone. Output: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Enrich companies with regional sales team sizes.")
    parser.add_argument("--input", help="Path to input CSV or Excel file (default: latest file in input/)")
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    log.info(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
