#!/usr/bin/env python3
"""
Build the combined Excel workbook deliverable from a hubspot_check.csv —
one sheet, one row per deduped exhibitor, covering every exhibitor
(eligible + ineligible), colour-coded by Status with live hyperlinks.

hubspot_check.py already carries every field this workbook needs
(Tier/Stand pass-through, computed Status/Reason, all enrichment columns) —
this script only formats and dedupes, it does not fetch or compute anything.

Dedup: exact (company_name, company_website) duplicates are dropped,
keeping the first occurrence, before the row count is used anywhere.

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/build_workbook.py \
        --input  campaigns/anz/events-outbound/<event>/output/hubspot_check.csv \
        --output campaigns/anz/events-outbound/<event>/output/<name>.xlsx
"""

import argparse
import csv

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ── Column order + source mapping ────────────────────────────────────────────
# (header, source_csv_column, width)
COLUMNS = [
    ("Company Name", "company_name", 30),
    ("Domain", "company_website", 24),
    ("Tier", "tier", 12),
    ("Stand", "stand", 10),
    ("Status", "status", 12),
    ("Reason", "reason", 34),
    ("In HubSpot", "exists_in_hubspot", 11),
    ("In Firmable", "found_in_firmable", 11),
    ("Firmable ID", "firmable_id", 16),
    ("HubSpot Link", "company_hubspot_url", 16),
    ("Company Owner", "company_owner", 18),
    ("Company Owner (ANZ)", "company_owner_anz", 18),
    ("Company Owner (SEA)", "company_owner_sea", 18),
    ("SDR AU", "sdr_au", 16),
    ("SDR NZ", "sdr_nz", 16),
    ("SDR SEA", "sdr_sea", 16),
    ("Engagement Status (AU)", "outreach_engagement_status", 20),
    ("Engagement Status (SEA)", "outreach_engagement_status_sea", 20),
    ("Customer Status", "customer_status", 16),
    ("ICP Match (ANZ)", "icp_match_anz", 14),
    ("ICP Match (SEA)", "icp_match_sea", 14),
    ("Open Deal", "open_deal", 10),
    ("Deal Owner", "deal_owner", 18),
    ("Sales Team AU", "sales_team_au", 12),
    ("Sales Team NZ", "sales_team_nz", 12),
    ("Sales Team SEA", "sales_team_sea", 12),
    ("Sales Team US", "sales_team_us", 12),
    ("Last Contacted", "last_contacted", 14),
    ("ANZ Sales Team Size", "sales_team_anz", 16),
    ("HQ Country", "hq_country", 10),
]

FIRMABLE_URL = "https://app.firmable.com/dashboard/company/{id}"

HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
ELIGIBLE_FILL = PatternFill(start_color="D9F2D9", end_color="D9F2D9", fill_type="solid")
INELIGIBLE_FILL = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
LINK_FONT = Font(color="1155CC", underline="single")


def dedupe(rows: list) -> list:
    seen = set()
    out = []
    for r in rows:
        key = (r.get("company_name", ""), r.get("company_website", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build(input_path: str, output_path: str) -> int:
    with open(input_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    before = len(rows)
    rows = dedupe(rows)
    if len(rows) != before:
        print(f"Deduped {before - len(rows)} exact (company_name, company_website) duplicate(s)")

    wb = Workbook()
    ws = wb.active
    ws.title = "Exhibitors"

    for col_idx, (header, _, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")

    for row_idx, row in enumerate(rows, start=2):
        status = row.get("status", "")
        fill = ELIGIBLE_FILL if status == "Eligible" else INELIGIBLE_FILL

        for col_idx, (header, source_col, _) in enumerate(COLUMNS, start=1):
            value = row.get(source_col, "")
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = fill

            if header == "Firmable ID" and value:
                cell.value = value
                cell.hyperlink = FIRMABLE_URL.format(id=value)
                cell.font = LINK_FONT
            elif header == "HubSpot Link" and value:
                cell.value = "Open in HubSpot"
                cell.hyperlink = value
                cell.font = LINK_FONT
            else:
                cell.value = value

    for col_idx, (_, _, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"

    wb.save(output_path)
    eligible = sum(1 for r in rows if r.get("status") == "Eligible")
    return len(rows), eligible


def main():
    parser = argparse.ArgumentParser(description="Build the combined Excel exhibitor workbook from hubspot_check.csv")
    parser.add_argument("--input", required=True, help="Path to hubspot_check.csv")
    parser.add_argument("--output", required=True, help="Path for the output .xlsx")
    args = parser.parse_args()

    count, eligible = build(args.input, args.output)
    print(f"Saved {count} rows ({eligible} eligible) -> {args.output}")


if __name__ == "__main__":
    main()
