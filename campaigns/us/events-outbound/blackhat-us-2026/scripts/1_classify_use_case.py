"""
Black Hat US 2026 — classify each company against the 10 Notion use-case
categories (reference/use_case_signals.json), so copy generation can pull
pre-approved "example detections" instead of inventing tech names.

Classification uses the company description first. If the description is
missing or too vague to classify confidently, falls back to a Firecrawl
scrape of the company's homepage.

Input: newest CSV/XLSX in input/. Flexible headers — looks for company name,
domain/website, description, contact first/last name, title, email.

Run:
  PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/1_classify_use_case.py [--limit N]
"""

import argparse
import glob
import json
import os
import sys
from typing import Optional

import pandas as pd
import requests

from scripts.ai import ask_claude
from scripts.utils import ensure_dirs, load_csv, save_csv, timestamp

CAMPAIGN_DIR = "campaigns/us/events-outbound/blackhat-us-2026"
INPUT_DIR = f"{CAMPAIGN_DIR}/input"
OUTPUT_DIR = f"{CAMPAIGN_DIR}/output"
REFERENCE_PATH = f"{CAMPAIGN_DIR}/reference/use_case_signals.json"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
WEBSITE_CHAR_LIMIT = 3000
MIN_DESCRIPTION_WORDS = 12


def find_col(df: pd.DataFrame, candidates: list) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load_input() -> pd.DataFrame:
    patterns = [f"{INPUT_DIR}/*.csv", f"{INPUT_DIR}/*.xlsx", f"{INPUT_DIR}/*.xls"]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        print(f"No input file found in {INPUT_DIR}/. Drop your curated CSV there and retry.")
        sys.exit(1)
    input_path = sorted(files)[-1]
    print(f"Loading {input_path}")
    df = load_csv(input_path)
    print(f"  {len(df)} rows, columns: {list(df.columns)}")
    return df


def fetch_website_markdown(url: str) -> str:
    if not FIRECRAWL_API_KEY:
        print("  [WARN] FIRECRAWL_API_KEY not set — skipping website fallback")
        return ""
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        resp = requests.post(
            FIRECRAWL_SCRAPE_URL,
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
            json={"url": url, "formats": ["markdown"]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("data", {}).get("markdown", "") or "")[:WEBSITE_CHAR_LIMIT]
    except Exception as e:
        print(f"  [WARN] Firecrawl failed for {url}: {e}")
        return ""


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def classify_company(company_name: str, description: str, website: str, use_cases: list) -> dict:
    empty = {"primary_use_case": "", "secondary_use_case": "", "classification_source": "none", "classification_notes": ""}

    source = "description"
    context = description or ""
    if len(context.split()) < MIN_DESCRIPTION_WORDS:
        if website:
            print(f"  Description thin/missing — trying Firecrawl on {website}")
            scraped = fetch_website_markdown(website)
            if scraped:
                context = scraped
                source = "firecrawl"
        if not context:
            print(f"  [SKIP] No usable description or website content for {company_name}")
            return empty

    use_case_summaries = "\n".join(
        f'- key="{uc["key"]}" name="{uc["name"]}" buyer="{uc["buyer"]}" description="{uc["description"]}"'
        for uc in use_cases
    )

    prompt = f"""You are classifying a cybersecurity vendor exhibiting at Black Hat US 2026 against a fixed list of use-case categories, so we know which category of prospect they'd want to see surfaced by Firmable's data.

Company: {company_name}
Company info:
{context}

Use-case categories (pick ONLY from this list, by key):
{use_case_summaries}

Return ONLY a JSON object, no markdown, no explanation:
{{
  "primary_use_case": "<key of best-fit category>",
  "secondary_use_case": "<key of second-best-fit category, or empty string if none>",
  "notes": "<one sentence on why this fits, referencing what this company sells and who they sell to>"
}}"""

    try:
        raw = ask_claude(prompt)
        result = parse_json_response(raw)
        return {
            "primary_use_case": result.get("primary_use_case", ""),
            "secondary_use_case": result.get("secondary_use_case", ""),
            "classification_source": source,
            "classification_notes": result.get("notes", ""),
        }
    except Exception as e:
        print(f"  [WARN] Classification failed for {company_name}: {e}")
        return empty


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only classify the first N unique companies (for sample-batch review)")
    args = parser.parse_args()

    ensure_dirs(OUTPUT_DIR)

    with open(REFERENCE_PATH) as f:
        reference = json.load(f)
    use_cases = reference["use_cases"]
    use_cases_by_key = {uc["key"]: uc for uc in use_cases}

    df = load_input()

    company_col = find_col(df, ["company_name", "company", "account_name"])
    domain_col = find_col(df, ["domain_name", "domain", "website", "company_website", "url"])
    description_col = find_col(df, ["company_description", "description", "about"])

    if not company_col:
        print(f"Could not find a company name column. Available columns: {list(df.columns)}")
        sys.exit(1)

    unique_companies = df[[c for c in [company_col, domain_col, description_col] if c]].drop_duplicates(subset=[company_col])
    if args.limit:
        unique_companies = unique_companies.head(args.limit)
        print(f"Sample mode: classifying first {args.limit} unique companies only")

    print(f"Classifying {len(unique_companies)} unique companies...")

    classifications = {}
    for i, row in enumerate(unique_companies.itertuples(index=False), 1):
        company_name = getattr(row, company_col)
        description = str(getattr(row, description_col, "") or "").strip() if description_col else ""
        website = str(getattr(row, domain_col, "") or "").strip() if domain_col else ""

        print(f"[{i}/{len(unique_companies)}] {company_name}")
        result = classify_company(company_name, description, website, use_cases)

        primary_key = result["primary_use_case"]
        secondary_key = result["secondary_use_case"]
        primary_uc = use_cases_by_key.get(primary_key)
        secondary_uc = use_cases_by_key.get(secondary_key)

        example_detections = list(primary_uc["example_detections"]) if primary_uc else []
        if secondary_uc:
            for d in secondary_uc["example_detections"]:
                if d not in example_detections:
                    example_detections.append(d)

        classifications[company_name] = {
            **result,
            "primary_use_case_name": primary_uc["name"] if primary_uc else "",
            "buyer": primary_uc["buyer"] if primary_uc else "",
            "example_detections": "; ".join(example_detections),
        }

    if args.limit:
        df = df[df[company_col].isin(unique_companies[company_col])]

    for field in ["primary_use_case", "primary_use_case_name", "secondary_use_case", "buyer", "example_detections", "classification_source", "classification_notes"]:
        df[field] = df[company_col].map(lambda name: classifications.get(name, {}).get(field, ""))

    out_path = os.path.join(OUTPUT_DIR, f"1_classified_{timestamp()}.csv")
    save_csv(df, out_path)

    classified_count = sum(1 for c in classifications.values() if c["primary_use_case"])
    print(f"\nOutput: {out_path}")
    print(f"  Companies classified: {classified_count}/{len(classifications)}")
    print(f"  Contact rows written: {len(df)}")


if __name__ == "__main__":
    main()
