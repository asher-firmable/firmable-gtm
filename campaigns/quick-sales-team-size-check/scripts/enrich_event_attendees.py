"""Enrich an event attendee CSV with Firmable Person ID and regional sales team sizes.

Usage:
    PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_event_attendees.py \
      --input "/path/to/attendees.csv"

Adds four columns before the allergies column:
    Firmable ID, AU Sales Team Size, NZ Sales Team Size, SEA Sales Team Size
"""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from scripts.firmable_api import FirmableClient
from scripts.utils import save_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
ALLERGY_COL = "Do you have any allergies that we s"


def _enrich_row(i: int, row: pd.Series, client: FirmableClient, domain_cache: dict) -> dict:
    result = {
        "Firmable ID": None,
        "AU Sales Team Size": None,
        "NZ Sales Team Size": None,
        "SEA Sales Team Size": None,
    }

    # Person ID lookup
    email = str(row.get("Email", "")).strip()
    linkedin = str(row.get("LinkedIn Profile", "")).strip()
    person_id = None
    try:
        if email and email.lower() != "nan":
            resp = client.get_person(work_email=email)
            person_id = resp.get("id") if isinstance(resp, dict) else None
    except Exception:
        pass

    if not person_id:
        try:
            if linkedin and linkedin.lower() != "nan":
                resp = client.get_person(ln_url=linkedin)
                person_id = resp.get("id") if isinstance(resp, dict) else None
        except Exception:
            pass

    if not person_id:
        log.warning(f"Row {i + 1} ({row.get('Full Name', '')}): Firmable person not found")
    result["Firmable ID"] = person_id

    # Company sales team sizes
    domain = str(row.get("Company Domain", "")).strip()
    if domain and domain.lower() != "nan":
        try:
            if domain not in domain_cache:
                company = client.lookup_company(domain)
                domain_cache[domain] = company.get("id") if isinstance(company, dict) else None
            company_id = domain_cache[domain]
            if company_id:
                sizes = client.get_sales_team_size(company_id)
                result["AU Sales Team Size"] = sizes.get("au_sales_team_size")
                result["NZ Sales Team Size"] = sizes.get("nz_sales_team_size")
                result["SEA Sales Team Size"] = sizes.get("sea_sales_team_size")
            else:
                log.warning(f"Row {i + 1}: domain '{domain}' not found in Firmable")
        except Exception as exc:
            log.error(f"Row {i + 1} ({domain}): company lookup failed — {exc}")

    return result


def enrich(input_path: str) -> str:
    df = pd.read_csv(input_path)
    log.info(f"Loaded {len(df)} rows from {input_path}")

    client = FirmableClient()
    domain_cache: dict = {}
    results = [None] * len(df)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_enrich_row, i, row, client, domain_cache): i
            for i, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()
            done += 1
            log.info(f"  {done}/{len(df)} done")

    enrichment_df = pd.DataFrame(results, index=df.index)

    # Find insert position — before the allergy column
    allergy_matches = [c for c in df.columns if c.startswith(ALLERGY_COL[:20])]
    if allergy_matches:
        insert_pos = df.columns.get_loc(allergy_matches[0])
    else:
        insert_pos = len(df.columns)
        log.warning("Allergy column not found — appending new columns at the end")

    for offset, col_name in enumerate(["Firmable ID", "AU Sales Team Size", "NZ Sales Team Size", "SEA Sales Team Size"]):
        df.insert(insert_pos + offset, col_name, enrichment_df[col_name])

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = str(OUTPUT_DIR / "humanitix_enriched.csv")
    df.to_csv(output_path, index=False)
    log.info(f"\nDone. Output: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input CSV")
    args = parser.parse_args()
    enrich(args.input)


if __name__ == "__main__":
    main()
