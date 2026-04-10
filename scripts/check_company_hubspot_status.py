"""
HubSpot Company Status Check
-----------------------------
Reads a company CSV and cross-references each domain against HubSpot.
Prints a two-part summary:

  1. How many domains exist in HubSpot vs. don't
  2. For those in HubSpot: how many have outreach_engagement_status of
     'No product fit' or 'Time Out' vs. any other status

Usage:
  PYTHONPATH=. python3 scripts/check_company_hubspot_status.py --input <path/to/companies.csv>

CSV requirements:
  - Must have a domain column: 'domain', 'website', 'company_website', or 'company_domain'
  - Company name column is optional: 'name', 'company_name', or 'company'
"""

import argparse
import csv
import time
from pathlib import Path
from typing import Optional

from scripts.hubspot_client import HubSpotClient

# ── Constants ──────────────────────────────────────────────────────────────────

RULED_OUT_STATUSES = {"No product fit", "Time Out"}
OUTREACH_STATUS_PROP = "outreach_engagement_status"
CLOSED_LOST_STAGE = "closedlost"

DOMAIN_COLS       = ["domain", "website", "company_website", "company_domain"]
NAME_COLS         = ["name", "company_name", "company"]
FIRMABLE_ID_COLS  = ["firmable id", "firmable_id", "firmable company id", "firmable_company_id"]
APAC_HC_COLS      = ["apac sales hc", "apac_sales_hc", "apac_hc", "apac sales headcount"]

DEFAULT_INPUT_DIR  = Path("projects/sea-company-upload/input")
DEFAULT_OUTPUT_DIR = Path("projects/sea-company-upload/output")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_col(headers: list, candidates: list) -> Optional[str]:
    """Return the first matching column name (case-insensitive), or None."""
    lower = {h.lower(): h for h in headers}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def _clean_domain(raw: str) -> str:
    """Strip protocol, www, and path segments from a URL or domain string."""
    d = raw.strip()
    d = d.replace("https://", "").replace("http://", "")
    d = d.replace("www.", "")
    d = d.split("/")[0].strip()
    return d


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Check company domains against HubSpot.")
    parser.add_argument("--input", required=False, help="Path to input CSV (default: latest CSV in projects/sea-company-upload/input/)")
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
    else:
        csvs = sorted(DEFAULT_INPUT_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not csvs:
            raise FileNotFoundError(
                f"No CSV found in {DEFAULT_INPUT_DIR}. "
                "Drop a company CSV there and retry, or pass --input <path>."
            )
        input_path = csvs[0]
        print(f"Auto-detected input: {input_path.name}")

    hs = HubSpotClient()
    stage_labels = hs.get_deal_stage_label_map()

    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []

    domain_col      = _find_col(headers, DOMAIN_COLS)
    name_col        = _find_col(headers, NAME_COLS)
    firmable_id_col = _find_col(headers, FIRMABLE_ID_COLS)
    apac_hc_col     = _find_col(headers, APAC_HC_COLS)

    if not domain_col:
        raise ValueError(
            f"No domain column found. Expected one of: {DOMAIN_COLS}\n"
            f"Columns in file: {headers}"
        )

    total = len(rows)
    print(f"Loaded {total} companies from {input_path.name}")
    print(f"  Domain column      : {domain_col}")
    print(f"  Name column        : {name_col or '(not found — using row index)'}")
    print(f"  Firmable ID column : {firmable_id_col or '(not found)'}")
    print(f"  APAC HC column     : {apac_hc_col or '(not found)'}")
    print()

    skipped            = []  # no domain in row
    not_in_hs          = []  # domain not found in HubSpot
    ruled_out          = []  # in HubSpot, status = No product fit / Time Out
    active_deal_out    = []  # in HubSpot, other/not-set status, but has a non-closed-lost deal
    other_status       = []  # in HubSpot, other/not-set status, no active deal (truly viable)

    for i, row in enumerate(rows, 1):
        name        = (row.get(name_col) or f"Row {i}").strip() if name_col else f"Row {i}"
        raw         = (row.get(domain_col) or "").strip()
        domain      = _clean_domain(raw) if raw else ""
        firmable_id = (row.get(firmable_id_col) or "").strip() if firmable_id_col else ""
        apac_hc     = (row.get(apac_hc_col) or "").strip() if apac_hc_col else ""

        print(f"[{i}/{total}] {name} | {domain or '(no domain)'}", end=" ... ", flush=True)

        if not domain:
            print("SKIPPED")
            skipped.append({"name": name, "firmable_id": firmable_id, "apac_hc": apac_hc})
            continue

        # ── HubSpot company search ─────────────────────────────────────────────
        try:
            companies = hs.search_companies(domain)
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR ({e})")
            not_in_hs.append({"name": name, "domain": domain, "firmable_id": firmable_id, "apac_hc": apac_hc})
            continue

        if not companies:
            print("NOT IN HUBSPOT")
            not_in_hs.append({"name": name, "domain": domain, "firmable_id": firmable_id, "apac_hc": apac_hc})
            continue

        # ── Fetch outreach status ──────────────────────────────────────────────
        company_id = companies[0]["id"]
        try:
            props = hs.get_company_properties(company_id, [OUTREACH_STATUS_PROP])
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR fetching props ({e})")
            other_status.append({"name": name, "domain": domain, "firmable_id": firmable_id, "apac_hc": apac_hc, "status": "ERROR", "hubspot_id": company_id})
            continue

        status = (props.get(OUTREACH_STATUS_PROP) or "").strip()

        if status in RULED_OUT_STATUSES:
            print(f"IN HUBSPOT — ruled out ({status})")
            ruled_out.append({"name": name, "domain": domain, "status": status, "firmable_id": firmable_id})
        else:
            # ── Deal check ────────────────────────────────────────────────────
            try:
                deal_stages = hs.get_company_deal_stages(company_id)
                time.sleep(0.1)
            except Exception as e:
                print(f"ERROR fetching deals ({e})")
                other_status.append({"name": name, "domain": domain, "firmable_id": firmable_id, "apac_hc": apac_hc, "status": status, "hubspot_id": company_id, "deals": "ERROR"})
                continue

            active_stages = [s for s in deal_stages if s and s != CLOSED_LOST_STAGE]
            label = status if status else "(no status set)"

            if active_stages:
                active_labels = [stage_labels.get(s, s) for s in active_stages]
                stages_str = ", ".join(active_labels)
                print(f"IN HUBSPOT — ruled out (active deal: {stages_str})")
                active_deal_out.append({"name": name, "domain": domain, "status": label, "deal_stages": active_labels, "firmable_id": firmable_id})
            else:
                print(f"IN HUBSPOT — viable ({label})")
                other_status.append({"name": name, "domain": domain, "firmable_id": firmable_id, "apac_hc": apac_hc, "status": status, "hubspot_id": company_id})

    # ── Terminal summary ───────────────────────────────────────────────────────
    sep = "=" * 60
    in_hs_total = len(ruled_out) + len(active_deal_out) + len(other_status)
    viable_total = len(other_status) + len(not_in_hs)
    viable_pct = (viable_total / total * 100) if total else 0

    print(f"\n{sep}")
    print("SUMMARY 1 — HubSpot Presence")
    print(sep)
    print(f"  Total companies:       {total}")
    print(f"  Skipped (no domain):   {len(skipped)}")
    print(f"  In HubSpot:            {in_hs_total}")
    print(f"  NOT in HubSpot:        {len(not_in_hs)}")

    print(f"\n{sep}")
    print(f"SUMMARY 2 — Outreach Status  (for {in_hs_total} in HubSpot)")
    print(sep)
    print(f"  Ruled out - No product fit / Time Out:   {len(ruled_out)}")
    print(f"  Ruled out - Active deal (not closed):    {len(active_deal_out)}")
    print(f"  Viable - Engagement Status is other/not set, no active deal on company:   {len(other_status)}")

    if ruled_out:
        print(f"\n  Ruled out (status):")
        for c in ruled_out:
            print(f"    - {c['name']} | {c['domain']} | {c['status']}")

    if active_deal_out:
        print(f"\n  Ruled out (active deal):")
        for c in active_deal_out:
            stages_str = ", ".join(c['deal_stages'])
            print(f"    - {c['name']} | {c['domain']} | {c['status']} | deals: {stages_str}")

    if other_status:
        print(f"\n  Viable - Engagement Status is other/not set, no active deal on company:")
        for c in other_status:
            label = c['status'] if c['status'] else "(no status set)"
            print(f"    - {c['name']} | {c['domain']} | {label}")

    print(f"\n{sep}")
    print("SUMMARY 3 — Total Viable for Outreach")
    print(sep)
    print(f"  In HubSpot (viable):         {len(other_status)}")
    print(f"  NOT in HubSpot:              {len(not_in_hs)}")
    print(f"  TOTAL VIABLE:                {viable_total}  ({viable_pct:.1f}% of {total} uploaded)")

    print()

    # ── Save intermediate CSVs for downstream commands ─────────────────────────
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    not_in_hs_path = DEFAULT_OUTPUT_DIR / "viable_not_in_hubspot.csv"
    with open(not_in_hs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "domain", "firmable_id", "apac_sales_hc"])
        writer.writeheader()
        for c in not_in_hs:
            writer.writerow({
                "company_name": c["name"],
                "domain":       c["domain"],
                "firmable_id":  c.get("firmable_id", ""),
                "apac_sales_hc": c.get("apac_hc", ""),
            })

    in_hs_path = DEFAULT_OUTPUT_DIR / "viable_in_hubspot.csv"
    with open(in_hs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "domain", "firmable_id", "apac_sales_hc", "current_outreach_status", "hubspot_id"])
        writer.writeheader()
        for c in other_status:
            writer.writerow({
                "company_name":           c["name"],
                "domain":                 c["domain"],
                "firmable_id":            c.get("firmable_id", ""),
                "apac_sales_hc":          c.get("apac_hc", ""),
                "current_outreach_status": c.get("status", ""),
                "hubspot_id":             c.get("hubspot_id", ""),
            })

    print(f"Saved: {not_in_hs_path}  ({len(not_in_hs)} companies)")
    print(f"Saved: {in_hs_path}  ({len(other_status)} companies)")
    print()


if __name__ == "__main__":
    main()
