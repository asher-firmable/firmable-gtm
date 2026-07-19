"""
Add SDR columns and 30-day contact flag to an already-enriched company file.

Adds three columns:
  - SDR (AU)                    from HubSpot property sdr__new_
  - SDR (NZ)                    from HubSpot property sdr_nz
  - Connected in Last 30 Days?  Yes / No  derived from existing "Last Contacted" column

Requires a "HubSpot Link" column — company IDs are extracted from the URL directly,
so no search API calls are needed. Only companies with a HubSpot link get SDR data.

Usage:
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_sdr.py
    PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_sdr.py --input path/to/file.csv
"""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from scripts.hubspot_client import HubSpotClient
from scripts.utils import save_csv

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR.parent / "input"
OUTPUT_DIR = SCRIPT_DIR.parent / "output"

COLS_TO_ADD = ["SDR (AU)", "SDR (NZ)", "Connected in Last 30 Days?"]
MAX_WORKERS = 10
CUTOFF_DATE = date(2026, 6, 9)  # 30 days before 9 Jul 2026

HS_LINK_CANDIDATES = ("hubspot_link", "hs_link", "company_hubspot_url", "hubspot_url")
LAST_CONTACTED_CANDIDATES = ("last_contacted", "hs_last_contacted", "last_contact")


def _find_latest_input() -> Path:
    candidates = (
        list(INPUT_DIR.glob("*.csv"))
        + list(INPUT_DIR.glob("*.xlsx"))
        + list(INPUT_DIR.glob("*.xls"))
    )
    if not candidates:
        raise FileNotFoundError(f"No input files found in {INPUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _norm(columns: list[str]) -> dict[str, str]:
    return {c.lower().replace(" ", "_"): c for c in columns}


def _find_col(columns: list[str], candidates: tuple) -> str | None:
    norm = _norm(columns)
    return next((norm[k] for k in candidates if k in norm), None)


def _extract_company_id(hs_link: str) -> str | None:
    """Extract company ID from a HubSpot URL like .../company/12345678."""
    if not hs_link:
        return None
    m = re.search(r"/company/(\d+)", hs_link)
    return m.group(1) if m else None


def _within_30_days(last_contacted_str: str) -> str:
    """Return Yes/No based on whether last_contacted_str is within 30 days of today."""
    if not last_contacted_str or last_contacted_str.strip() == "":
        return "No"
    s = last_contacted_str.strip()
    for fmt in ("%d-%b-%y", "%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            return "Yes" if d >= CUTOFF_DATE else "No"
        except ValueError:
            continue
    return "No"


def enrich(input_path: str) -> str:
    p = Path(input_path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(input_path, dtype=str)
    else:
        df = pd.read_csv(input_path, dtype=str)
    df = df.fillna("")

    cols = list(df.columns)
    hs_link_col = _find_col(cols, HS_LINK_CANDIDATES)
    last_contacted_col = _find_col(cols, LAST_CONTACTED_CANDIDATES)

    if not hs_link_col:
        raise ValueError(f"No HubSpot Link column found. Columns: {cols}")

    print(f"HubSpot Link column:  {hs_link_col}")
    print(f"Last Contacted column: {last_contacted_col or '(not found — Connected column will be No for all)'}")
    print(f"Enriching {len(df)} rows...")

    hs = HubSpotClient()

    # --- Phase 1: collect unique company IDs ---
    id_to_rows: dict[str, list[int]] = {}
    for i, row in df.iterrows():
        company_id = _extract_company_id(str(row.get(hs_link_col, "")))
        if company_id:
            id_to_rows.setdefault(company_id, []).append(i)

    unique_ids = list(id_to_rows.keys())
    print(f"Unique HubSpot company IDs: {len(unique_ids)} (skipping {len(df) - len(df.index.isin([j for ids in id_to_rows.values() for j in ids]))} without a link)")

    # --- Phase 2: parallel property fetch ---
    completed = 0
    total = len(unique_ids)
    id_results: dict[str, dict] = {}

    def fetch(company_id: str) -> tuple[str, dict]:
        try:
            props = hs.get_company_properties(company_id, ["sdr__new_", "sdr_nz"])
            return company_id, {
                "sdr_au": props.get("sdr__new_") or "",
                "sdr_nz": props.get("sdr_nz") or "",
            }
        except Exception as exc:
            return company_id, {"sdr_au": "", "sdr_nz": "", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch, cid): cid for cid in unique_ids}
        for future in as_completed(futures):
            company_id, result = future.result()
            id_results[company_id] = result
            completed += 1
            status = result.get("error", f"au={result['sdr_au'] or 'none'} | nz={result['sdr_nz'] or 'none'}")
            print(f"[{completed}/{total}] {company_id} — {status}")

    # --- Phase 3: map back to rows ---
    sdr_aus, sdr_nzs, connected_flags = [], [], []

    for i, row in df.iterrows():
        company_id = _extract_company_id(str(row.get(hs_link_col, "")))
        if company_id and company_id in id_results:
            r = id_results[company_id]
            sdr_aus.append(r["sdr_au"])
            sdr_nzs.append(r["sdr_nz"])
        else:
            sdr_aus.append("")
            sdr_nzs.append("")

        last_contacted = str(row.get(last_contacted_col, "")) if last_contacted_col else ""
        connected_flags.append(_within_30_days(last_contacted))

    # Drop existing versions of output columns if re-running
    for col in COLS_TO_ADD:
        if col in df.columns:
            df = df.drop(columns=[col])

    df["SDR (AU)"] = sdr_aus
    df["SDR (NZ)"] = sdr_nzs
    df["Connected in Last 30 Days?"] = connected_flags

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stem = p.stem
    output_path = str(OUTPUT_DIR / f"{stem}_sdr.csv")
    save_csv(df, output_path)

    connected = sum(1 for v in connected_flags if v == "Yes")
    print(f"\n{'─' * 48}")
    print(f"Connected in last 30 days: {connected} / {len(df)}")
    print(f"\nOutput: {output_path}")
    print(f"{'─' * 48}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Add SDR columns and 30-day contact flag.")
    parser.add_argument("--input", help="Path to input file (default: latest in input/)")
    args = parser.parse_args()

    input_path = args.input or str(_find_latest_input())
    print(f"Input: {input_path}")
    enrich(input_path)


if __name__ == "__main__":
    main()
