"""
Signal — Contact Activation: Headcount Enrichment (Step 2)
-----------------------------------------------------------
Takes the classified CSV output from classify_new_roles.py, looks up Firmable
sales headcount for each ICP Yes contact, and writes an enriched CSV.

New columns added for ICP Yes rows:
  - apac_sales_team_size  (total across all regions)
  - anz_sales_team_size   (AU + NZ)
  - sea_sales_team_size   (PH + MY + SG + ID + HK + JP)

Requires FIRMABLE_OS_API_KEY in .env (separate from FIRMABLE_API_KEY).

Usage:
  PYTHONPATH=. python3 projects/signal-contact-activation/contacts-new-role/scripts/enrich_headcount.py \\
    --input "projects/signal-contact-activation/contacts-new-role/output/classified_<timestamp>.csv"
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from scripts.firmable_api import FirmableClient
from scripts.utils import load_csv, save_csv, timestamp

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)


def _extract_company_id(firmable_url: str):
    """Extract company ID from a Firmable dashboard URL.
    e.g. https://app.firmable.com/dashboard/company/f000000075897 → f000000075897
    """
    if not firmable_url or str(firmable_url).strip() in ("", "nan"):
        return None
    return str(firmable_url).rstrip("/").split("/")[-1]


def _fetch_headcount(i: int, row: dict, total: int) -> tuple:
    """Fetch headcount for a single row. Returns (i, apac, anz, sea)."""
    company_id = _extract_company_id(row.get("firmable_company_url", ""))
    company_name = row.get("company_name", f"row {i}")

    if not company_id:
        print(f"  [{i+1}/{total}] SKIP — no Firmable company ID: {company_name}", flush=True)
        return i, None, None, None

    print(f"  [{i+1}/{total}] {company_name} ({company_id})", flush=True)
    try:
        client = FirmableClient()
        hc = client.get_sales_team_size(company_id)
        au = hc.get("au_sales_team_size") or 0
        nz = hc.get("nz_sales_team_size") or 0
        anz = au + nz
        sea = hc.get("sea_sales_team_size")
        apac = hc.get("total_sales_team_size")
        return i, apac, anz, sea
    except Exception as e:
        print(f"    ! headcount error: {e}", flush=True)
        return i, None, None, None


def enrich(input_path: str, output_path: str, workers: int = 5) -> str:
    df = load_csv(input_path)
    total = len(df)

    yes_mask = df["icp_match"].str.strip().str.lower() == "yes"
    yes_count = yes_mask.sum()
    print(f"Loaded {total} contacts ({yes_count} ICP Yes) from: {input_path}")

    apac_col = [None] * total
    anz_col = [None] * total
    sea_col = [None] * total

    yes_rows = [(i, row) for i, row in df.iterrows() if yes_mask.iloc[i]]

    print(f"\nFetching headcount for {yes_count} ICP Yes contacts...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for seq, (i, row) in enumerate(yes_rows):
            futures[executor.submit(_fetch_headcount, seq, row, yes_count)] = i

        for future in as_completed(futures):
            orig_i = futures[future]
            _, apac, anz, sea = future.result()
            apac_col[orig_i] = apac
            anz_col[orig_i] = anz
            sea_col[orig_i] = sea

    df["apac_sales_team_size"] = apac_col
    df["anz_sales_team_size"] = anz_col
    df["sea_sales_team_size"] = sea_col

    save_csv(df, output_path)

    # Print summary table for ICP Yes contacts
    yes_df = df[yes_mask][
        ["first_name", "last_name", "position", "company_name",
         "apac_sales_team_size", "anz_sales_team_size", "sea_sales_team_size"]
    ].copy()

    def _fmt(v):
        return str(int(v)) if v is not None and str(v) not in ("", "nan") else "—"

    print(f"\n{'='*90}")
    print(f"  ICP Yes — Headcount Summary ({yes_count} contacts)")
    print(f"{'='*90}")
    print(f"{'Name':<28} {'Position':<36} {'Company':<26} {'APAC':>5} {'ANZ':>5} {'SEA':>5}")
    print(f"{'-'*28} {'-'*36} {'-'*26} {'-'*5} {'-'*5} {'-'*5}")
    for _, r in yes_df.iterrows():
        name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()[:27]
        pos = str(r.get("position", ""))[:35]
        co = str(r.get("company_name", ""))[:25]
        apac = _fmt(r["apac_sales_team_size"])
        anz = _fmt(r["anz_sales_team_size"])
        sea = _fmt(r["sea_sales_team_size"])
        print(f"{name:<28} {pos:<36} {co:<26} {apac:>5} {anz:>5} {sea:>5}")
    print(f"{'='*90}")
    print(f"\nOutput: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Enrich ICP Yes contacts with Firmable sales headcount (APAC, ANZ, SEA)."
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to classified CSV (output of classify_new_roles.py)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Path to output CSV (default: output/enriched_<timestamp>.csv)"
    )
    parser.add_argument(
        "--workers", type=int, default=5,
        help="Parallel workers for Firmable API calls (default: 5)"
    )
    args = parser.parse_args()

    output_path = args.output or os.path.join(OUTPUT_DIR, f"enriched_{timestamp()}.csv")
    enrich(args.input, output_path, workers=args.workers)


if __name__ == "__main__":
    main()
