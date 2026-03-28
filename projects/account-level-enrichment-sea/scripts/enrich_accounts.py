"""
Account Level Enrichment
------------------------
Takes a Firmable-exported accounts CSV (must have a Firmable ID column),
calls the Firmable API to pull regional sales headcount and company details,
then uses Claude to generate a short enrichment note per account.

New column added to output:
  - enrichment_note  (contains date, headcount, target persona, problem, solution)

Usage:
  PYTHONPATH=. python3 projects/account-level-enrichment/scripts/enrich_accounts.py \
    --input "data/input/Darcy Accounts.csv"
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from scripts.firmable_api import FirmableClient
from scripts.ai import ask_claude
from scripts.utils import load_csv, save_csv, timestamp

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)

NOTE_PROMPT = """You are a concise B2B analyst. Given the company data below, write a short enrichment note with exactly these three labelled sections:

Target persona: [one sentence listing 2–4 job titles this company's sales team would typically target, e.g. "Head of Sales, VP Revenue, Head of Marketing"]
Problem they solve: [1–2 sentences on the core business problem this company addresses]
How they solve it: [1–2 sentences on the product or approach they use to solve that problem]

Rules:
- Keep each section to the length specified — no longer.
- Use plain English, no bullet points, no markdown.
- If you cannot determine a field from the data, write "Not available".
- Output only the three labelled lines, nothing else.

Company data:
{company_data}"""


def _format_date() -> str:
    """Return today's date as 'D Month YYYY', e.g. '25 March 2026'."""
    return datetime.now().strftime("%-d %B %Y")


def _build_company_context(company: dict) -> str:
    name = company.get("name", "")
    description = company.get("description", "")
    tagline = company.get("tagline", "")
    industries = ", ".join(company.get("industries", [])) if company.get("industries") else ""
    next_gen = company.get("nextGen", {}) or {}
    technographics = next_gen.get("technographics", "")

    parts = []
    if name:
        parts.append(f"Company: {name}")
    if tagline:
        parts.append(f"Tagline: {tagline}")
    if description:
        parts.append(f"Description: {description}")
    if industries:
        parts.append(f"Industries: {industries}")
    if technographics:
        parts.append(f"Tech stack: {technographics}")
    return "\n".join(parts)


def _generate_note(company: dict, date_str: str, apac: object, anz: object, sea: object) -> str:
    context = _build_company_context(company)
    if not context.strip():
        ai_body = "Target persona: Not available\nProblem they solve: Not available\nHow they solve it: Not available"
    else:
        raw = ask_claude(NOTE_PROMPT.format(company_data=context))
        ai_body = "\n\n".join(line for line in raw.splitlines() if line.strip())

    apac_str = str(apac) if apac not in (None, "") else "Not available"
    anz_str = str(anz) if anz not in (None, "") else "Not available"
    sea_str = str(sea) if sea not in (None, "") else "Not available"

    headcount_block = (
        f"APAC Sales Team Size: {apac_str}\n"
        f"ANZ Sales Team Size: {anz_str}\n"
        f"SEA Sales Team Size: {sea_str}"
    )
    return f"Data extracted: {date_str}\n\n{headcount_block}\n\n{ai_body}"


def _enrich_one(i: int, row, total: int, date_str: str) -> tuple:
    """Enrich a single row. Creates its own FirmableClient (thread-safe)."""
    client = FirmableClient()
    firmable_id = row.get("firmable_id")
    company_name = row.get("company", row.get("name", f"row {i}"))

    if not firmable_id or str(firmable_id).strip() in ("", "nan"):
        print(f"[{i+1}/{total}] SKIP — no Firmable ID: {company_name}", flush=True)
        return i, ""

    firmable_id = str(firmable_id).strip()
    print(f"[{i+1}/{total}] Enriching: {company_name} ({firmable_id})", flush=True)

    apac = anz = sea = None
    try:
        hc = client.get_sales_team_size(firmable_id)
        au = hc.get("au_sales_team_size") or 0
        nz = hc.get("nz_sales_team_size") or 0
        sea = hc.get("sea_sales_team_size")
        apac = hc.get("total_sales_team_size")
        anz = au + nz
    except Exception as e:
        print(f"  ! [{i+1}] headcount error: {e}", flush=True)

    try:
        company = client.lookup_company_by_id(firmable_id)
        note = _generate_note(company, date_str, apac, anz, sea)
    except Exception as e:
        print(f"  ! [{i+1}] company lookup/note error: {e}", flush=True)
        note = f"Data extracted: {date_str}\n\nEnrichment failed: {e}"

    return i, note


def enrich(input_path: str, output_path: str, workers: int = 5) -> str:
    df = load_csv(input_path)

    # Firmable ID column normalises to 'firmable_id' via load_csv
    if "firmable_id" not in df.columns:
        raise ValueError(
            f"No 'Firmable ID' column found in {input_path}. "
            f"Columns present: {list(df.columns)}"
        )

    date_str = _format_date()
    total = len(df)
    notes = [""] * total

    rows = [(i, row) for i, row in df.iterrows()]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_enrich_one, i, row, total, date_str): i
            for i, row in rows
        }
        for future in as_completed(futures):
            i, note = future.result()
            notes[i] = note

    df["enrichment_note"] = notes

    country_cols = ["au_sales", "nz_emp", "sg_sales", "my_sales", "id_sales", "ph_sales", "hk_sales", "jp_sales"]
    df.drop(columns=[c for c in country_cols if c in df.columns], inplace=True)

    save_csv(df, output_path)
    print(f"\nDone. {total} rows written to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Enrich Firmable accounts with regional headcount and AI notes.")
    parser.add_argument("--input", required=True, help="Path to input accounts CSV (must have Firmable ID column)")
    parser.add_argument("--output", default=None, help="Path to output CSV (default: output/enriched_<timestamp>.csv)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    args = parser.parse_args()

    output_path = args.output or os.path.join(OUTPUT_DIR, f"enriched_{timestamp()}.csv")
    enrich(args.input, output_path, workers=args.workers)


if __name__ == "__main__":
    main()
