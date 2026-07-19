#!/usr/bin/env python3
"""
Categorize companies as potential Firmable GTM partners.

Usage:
    # First batch (creates output file)
    PYTHONPATH=. python3 campaigns/partner-identification/scripts/categorize_partners.py \\
        --start 0 --count 20

    # Subsequent batches (appends to existing output)
    PYTHONPATH=. python3 campaigns/partner-identification/scripts/categorize_partners.py \\
        --start 20 --count 100 --append
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
INPUT_DIR = CAMPAIGN_DIR / "input"
OUTPUT_DIR = CAMPAIGN_DIR / "output"

VALID_CATEGORIES = [
    "GTM Recruitment",
    "Training",
    "Implementation Partner",
    "Consulting / Advisory",
    "Community",
    "Media",
    "Other",
    "Disqualified",
]

CLASSIFICATION_PROMPT = """You are classifying companies as potential partners for Firmable, a B2B data platform used by sales teams in Australia, New Zealand, South-East Asia, and the US.

Classify the company into exactly one category:

GTM Recruitment — firms whose PRIMARY focus is recruiting or headhunting for sales, SDR, RevOps, or GTM roles. A generalist recruiter that lists "sales" as one of many practice areas (alongside legal, finance, engineering, healthcare, etc.) does NOT qualify — disqualify instead.

Training — providers whose PRIMARY focus is sales training, SDR coaching, GTM enablement, or revenue team education. Includes programs, academies, workshops, and e-learning specifically for sales or GTM professionals. Sector-specific B2B sales training (e.g. life science, pharma, tech, financial services) still qualifies. B2C-focused sales training (e.g. automotive dealerships, retail store staff, consumer-facing roles) does NOT qualify — disqualify instead.

Implementation Partner — firms whose PRIMARY offering is delivering or implementing B2B sales or GTM services (e.g. outsourced SDR teams, HubSpot/CRM implementation, sales process design, pipeline generation, B2B outsourced sales execution). B2B GTM SaaS platforms used by sales and marketing teams also qualify (platform-to-platform partnership angle). Generic nearshore/offshore/staff-aug companies that cover all business functions do NOT qualify. VA or admin services not specifically focused on sales execution do NOT qualify. Marketplaces or platforms that connect buyers and sellers (rather than directly delivering the service) do NOT qualify — use Other for those instead. B2C-oriented sales outsourcing (retail, consumer-facing, automotive dealerships) does NOT qualify. Disqualify generic outsourcing firms.

Consulting / Advisory — GTM strategy advisors, sales transformation consultants, or RevOps advisory firms. General management consultants where sales is a minor service line do NOT qualify.

Community — practitioner groups, associations, professional networks, or events whose PRIMARY audience is sales, RevOps, GTM, channel, partnerships, or alliances professionals.

Media — podcasts, newsletters, content creators, or publications whose PRIMARY focus is sales, GTM, or RevOps topics.

Other — company appears to be a plausible Firmable partner but does not fit any named category above; must include a specific reason explaining the partner angle.

Disqualified — not a relevant Firmable partner. Use for: unrelated industries, generic outsourcing/staffing/recruitment across many functions, consumer products, financial services, nonprofits, or any company where GTM/sales is not a primary focus.

Rules:
1. Apply the PRIMARY focus test strictly — if a company does many things and GTM/sales is just one of them, disqualify.
2. If none of the 6 named categories fits but the company is clearly a GTM ecosystem player, use Other.
3. When in doubt between a named category and Disqualified, choose Disqualified.
4. If the description is missing or too vague to classify, use Disqualified with reason "Insufficient information to classify."

Respond with JSON only, no other text: {"category": "<category>", "reason": "<one sentence>"}"""


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def _find_latest_input() -> Path:
    files = sorted(
        list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError(f"No CSV or Excel files found in {INPUT_DIR}")
    return files[0]


def _detect_columns(columns: list) -> tuple:
    """Return (name_col, desc_col) by case-insensitive detection."""
    normalized = {c.lower().replace(" ", "_"): c for c in columns}

    name_col = None
    for candidate in ("company_name", "name", "company"):
        if candidate in normalized:
            name_col = normalized[candidate]
            break

    desc_col = None
    for candidate in ("description", "company_description", "about", "overview", "summary"):
        if candidate in normalized:
            desc_col = normalized[candidate]
            break

    if desc_col is None:
        raise ValueError(
            f"No description column found. Expected one of: description, company_description, about, overview, summary.\nGot: {list(columns)}"
        )

    return name_col, desc_col


def _classify_row(idx: int, row: pd.Series, name_col: Optional[str], desc_col: str) -> dict:
    from scripts.ai import ask_claude

    company_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown"
    description = str(row[desc_col]).strip() if pd.notna(row[desc_col]) else ""

    prompt = (
        f"Company name: {company_name}\n"
        f"Description: {description if description else '(no description provided)'}"
    )

    try:
        raw = ask_claude(prompt=prompt, context=CLASSIFICATION_PROMPT)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in response: {raw[:200]}")
        parsed = json.loads(match.group())
        category = parsed.get("category", "Disqualified").strip()
        reason = parsed.get("reason", "").strip()
        if category not in VALID_CATEGORIES:
            log.warning(f"Row {idx + 1}: unexpected category '{category}', defaulting to Disqualified")
            category = "Disqualified"
        return {"partner_category": category, "category_reason": reason}
    except Exception as exc:
        log.warning(f"Row {idx + 1} ({company_name}): classification error — {exc}")
        return {"partner_category": "Disqualified", "category_reason": f"Classification error: {exc}"}


def categorize(
    input_path: Path,
    start: int,
    count: int,
    output_path: Path,
    append: bool,
) -> None:
    from scripts.utils import load_csv

    df = load_csv(str(input_path))
    total = len(df)
    end = min(start + count, total)
    batch = df.iloc[start:end].copy()
    batch_size = len(batch)

    if batch_size == 0:
        log.info(f"No rows to process (--start {start} exceeds total {total}).")
        return

    log.info(f"Classifying rows {start + 1}–{end} of {total} ({batch_size} rows)…")

    name_col, desc_col = _detect_columns(list(df.columns))
    if name_col:
        log.info(f"Name column: {name_col} | Description column: {desc_col}")
    else:
        log.info(f"No name column detected | Description column: {desc_col}")

    results = [None] * batch_size
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_classify_row, start + i, row, name_col, desc_col): i
            for i, (_, row) in enumerate(batch.iterrows())
        }
        done = 0
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            done += 1
            if done % 10 == 0 or done == batch_size:
                log.info(f"  {done}/{batch_size} classified")

    batch = batch.copy()
    batch["partner_category"] = [r["partner_category"] for r in results]
    batch["category_reason"] = [r["category_reason"] for r in results]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if append and output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, batch], ignore_index=True)
        combined.to_csv(output_path, index=False)
        log.info(f"Appended {batch_size} rows → {output_path} ({len(combined)} total)")
    else:
        batch.to_csv(output_path, index=False)
        log.info(f"Wrote {batch_size} rows → {output_path}")

    counts = Counter(r["partner_category"] for r in results)
    label_width = max(len(c) for c in VALID_CATEGORIES)
    print(f"\nBatch {start + 1}–{end} complete")
    print("─" * (label_width + 8))
    for cat in VALID_CATEGORIES:
        n = counts.get(cat, 0)
        if n == 0:
            continue
        note = ""
        if cat == "Other":
            note = "  (potential partner, non-standard fit)"
        elif cat == "Disqualified":
            note = "  (no GTM/sales relevance)"
        print(f"  {cat:<{label_width}}  {n}{note}")
    print(f"\nOutput: {output_path}\n")


def main():
    parser = argparse.ArgumentParser(description="Categorize companies as potential Firmable GTM partners.")
    parser.add_argument("--input", help="Input CSV/Excel path (default: latest file in input/)")
    parser.add_argument("--output", default="partner_categories.csv", help="Output filename (default: partner_categories.csv)")
    parser.add_argument("--start", type=int, default=0, help="0-based start row index (default: 0)")
    parser.add_argument("--count", type=int, default=20, help="Number of rows to process (default: 20)")
    parser.add_argument("--append", action="store_true", help="Append to existing output file instead of overwriting")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else _find_latest_input()
    output_path = OUTPUT_DIR / args.output

    log.info(f"Input:  {input_path}")
    log.info(f"Output: {output_path}")

    categorize(
        input_path=input_path,
        start=args.start,
        count=args.count,
        output_path=output_path,
        append=args.append,
    )


if __name__ == "__main__":
    main()
