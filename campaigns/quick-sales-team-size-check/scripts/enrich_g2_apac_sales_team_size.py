"""Enrich G2 APAC competitor intent list with regional sales team sizes.

Reads g2-apac-competitors.csv from input/, processes in batches of 40
with a 2-second sleep between batches, outputs lean CSV with ANZ/SEA/APAC sizes.

Usage:
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_g2_apac_sales_team_size.py
"""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from scripts.firmable_api import FirmableClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
INPUT_PATH = SCRIPT_DIR.parent / "input" / "g2-apac-competitors.csv"
OUTPUT_PATH = SCRIPT_DIR.parent / "output" / "g2-apac-competitors-sales-team-sizes.csv"
BATCH_SIZE = 40
SLEEP_BETWEEN_BATCHES = 2


def _resolve_row(i: int, domain: str, name: str, client: FirmableClient, domain_cache: dict) -> dict:
    base = {"company_name": name, "company_domain": domain, "firmable_id": None,
            "anz_sales_team_size": None, "sea_sales_team_size": None, "apac_sales_team_size": None}
    domain = domain.strip() if domain else ""
    if not domain:
        log.warning(f"Row {i+1}: empty domain — skipping")
        return base
    try:
        if domain not in domain_cache:
            company = client.lookup_company(domain)
            domain_cache[domain] = company.get("id") if company else None
        firmable_id = domain_cache[domain]
        if not firmable_id:
            log.warning(f"Row {i+1}: '{domain}' not found in Firmable")
            return base

        sizes = client.get_sales_team_size(firmable_id)
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        sea = sizes.get("sea_sales_team_size") or 0
        anz = au + nz
        return {
            "company_name": name,
            "company_domain": domain,
            "firmable_id": firmable_id,
            "anz_sales_team_size": anz,
            "sea_sales_team_size": sea,
            "apac_sales_team_size": anz + sea,
        }
    except Exception as exc:
        log.error(f"Row {i+1} ('{domain}'): {exc}")
        return base


def main():
    df = pd.read_csv(INPUT_PATH)
    total = len(df)
    log.info(f"Loaded {total} companies from {INPUT_PATH.name}")

    client = FirmableClient()
    domain_cache: dict = {}
    results = []

    rows = list(df.iterrows())
    batches = [rows[s:s + BATCH_SIZE] for s in range(0, total, BATCH_SIZE)]
    log.info(f"Processing {total} companies in {len(batches)} batches of {BATCH_SIZE}...")

    done = 0
    for b_idx, batch in enumerate(batches):
        batch_results = [None] * len(batch)
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = {
                pool.submit(
                    _resolve_row, i,
                    str(row.get("company_domain", "")) if pd.notna(row.get("company_domain")) else "",
                    str(row.get("company_name", "")) if pd.notna(row.get("company_name")) else "",
                    client, domain_cache
                ): pos
                for pos, (i, row) in enumerate(batch)
            }
            for future in as_completed(futures):
                pos = futures[future]
                batch_results[pos] = future.result()
        results.extend(batch_results)
        done += len(batch)
        log.info(f"  Batch {b_idx+1}/{len(batches)} done — {done}/{total} total")
        if b_idx < len(batches) - 1:
            time.sleep(SLEEP_BETWEEN_BATCHES)

    out_df = pd.DataFrame(results)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False)

    successes = out_df["firmable_id"].notna().sum()
    log.info(f"\n{'='*50}")
    log.info(f"Done. {successes}/{total} companies resolved.")
    log.info(f"Output: {OUTPUT_PATH}")
    log.info(f"\nRegional Sales Team Size Summary (resolved companies only):")
    resolved = out_df[out_df["firmable_id"].notna()]
    log.info(f"  ANZ total:  {int(resolved['anz_sales_team_size'].sum())}")
    log.info(f"  SEA total:  {int(resolved['sea_sales_team_size'].sum())}")
    log.info(f"  APAC total: {int(resolved['apac_sales_team_size'].sum())}")
    log.info(f"{'='*50}")


if __name__ == "__main__":
    main()
