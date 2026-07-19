"""
Test the niche classifier prompt against a list of companies.

Drop a CSV or Excel into campaigns/us/zoominfo-displacement/input/ with at least:
  - a company name column (e.g. "Company name", "company", "name")
  - a description column (e.g. "Description", "company_description", "about")

Run:
  PYTHONPATH=. python3 campaigns/us/zoominfo-displacement/scripts/test_niche_classifier.py
"""

import os
import sys
import json
import glob
import time
import anthropic
import pandas as pd
from dotenv import load_dotenv
from scripts.utils import ensure_dirs, timestamp

load_dotenv()

INPUT_DIR  = "campaigns/us/zoominfo-displacement/input"
OUTPUT_DIR = "campaigns/us/zoominfo-displacement/output"

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = json.dumps({
    "role": "B2B company niche specialist",
    "goal": "Read a company description and output a specific niche label and ICP",
    "company_niche_rules": [
        "A specific 2–4 word label for what kind of company this is.",
        "This label will be embedded in a cold email sentence: 'Our data might be great for [company_niche] like yours.' It must work as a readable noun phrase.",
        "Be domain-specific. Not 'IT services' → 'Salesforce consulting firm' or 'cybersecurity MSP'. Not 'marketing software' → 'martech platform'. Not 'restaurant software' → 'hospitality tech platform'. Not 'healthcare software' → 'medtech platform'.",
        "Do not use 'SaaS platform' together — 'platform' alone implies SaaS. Do not use 'SaaS consulting' — just use the domain.",
        "Lowercase except proper nouns (e.g. Salesforce).",
        "If too vague to determine a specific domain, return empty string."
    ],
    "company_icp_rules": [
        "Who they sell to. Under 5 words.",
        "Format: '[role A] or [role B] [function]'. E.g. 'RevOps or Salesforce admins', 'IT or operations managers', 'restaurant or hospitality operators'.",
        "If unclear, return empty string."
    ],
    "output_format": "Return only a JSON object with keys company_niche and company_icp. No explanation, no markdown, no wrapper.",
    "worked_examples": [
        {"description": "Salesforce implementation partner for enterprise CRM workflows", "company_niche": "Salesforce consulting firm", "company_icp": "RevOps or Salesforce admins"},
        {"description": "SaaS for restaurant and hospitality reservations and orders", "company_niche": "hospitality tech platform", "company_icp": "restaurant or hospitality operators"},
        {"description": "Managed IT and cybersecurity for mid-size US businesses", "company_niche": "cybersecurity MSP", "company_icp": "IT or operations managers"},
        {"description": "Marketing attribution and ad spend management platform", "company_niche": "martech platform", "company_icp": "marketing or performance leaders"},
        {"description": "AI-powered diagnostic tools for radiologists", "company_niche": "medtech platform", "company_icp": "radiologists or clinical directors"},
        {"description": "Outsourced SDR firm running outbound for B2B SaaS", "company_niche": "sales outsourcing agency", "company_icp": "sales or growth leaders"},
        {"description": "Cap table and equity management for startups", "company_niche": "fintech platform", "company_icp": "founders or CFOs"},
        {"description": "Compliance training and certifications for enterprises", "company_niche": "compliance training provider", "company_icp": "HR or L&D managers"},
        {"description": "AI-native data infrastructure for enterprise analytics teams", "company_niche": "data infrastructure platform", "company_icp": "data or analytics leaders"},
        {"description": "We help businesses succeed", "company_niche": "", "company_icp": ""}
    ]
})


def classify(client: anthropic.Anthropic, description: str) -> dict:
    main_prompt = json.dumps({
        "task": "Classify the company description. Follow your system instructions exactly.",
        "description": description
    })
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": main_prompt}]
        )
        text = resp.content[0].text.strip()
        # strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        return {"company_niche": f"ERROR: {e}", "company_icp": ""}


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    lowered = {col.lower().strip(): col for col in df.columns}
    for c in candidates:
        if c.lower().strip() in lowered:
            return lowered[c.lower().strip()]
    return None


def main():
    ensure_dirs(OUTPUT_DIR)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    patterns = [f"{INPUT_DIR}/*.csv", f"{INPUT_DIR}/*.xlsx", f"{INPUT_DIR}/*.xls"]
    files = [f for p in patterns for f in glob.glob(p)]

    if not files:
        print(f"No input file found in {INPUT_DIR}/")
        sys.exit(1)

    input_path = sorted(files)[-1]
    print(f"Loading {input_path}")

    df = pd.read_csv(input_path) if input_path.endswith(".csv") else pd.read_excel(input_path)
    print(f"  {len(df)} rows")

    name_col = find_col(df, ["Company name", "company_name", "company", "name", "Company"])
    desc_col = find_col(df, [
        "Description", "description", "company_description", "about",
        "About", "Company description", "Company Description", "Overview", "overview",
        "short_description", "Short description"
    ])

    if not name_col:
        print(f"Could not find company name column. Available: {list(df.columns)}")
        sys.exit(1)
    if not desc_col:
        print(f"Could not find description column. Available: {list(df.columns)}")
        sys.exit(1)

    print(f"  name={name_col}, description={desc_col}")
    print(f"\nRunning classifier on {len(df)} companies (model: {MODEL})...\n")

    results = []
    for i, row in df.iterrows():
        company = str(row[name_col]).strip()
        description = str(row.get(desc_col, "")).strip()

        if not description or description in ("nan", "None", ""):
            result = {"company_niche": "", "company_icp": ""}
            status = "skipped (no description)"
        else:
            result = classify(client, description)
            status = f"{result.get('company_niche', '')} / {result.get('company_icp', '')}"

        print(f"  [{i+1:>3}] {company:<40} {status}")
        results.append({
            "company_name": company,
            "description": description,
            "company_niche": result.get("company_niche", ""),
            "company_icp": result.get("company_icp", ""),
        })

        # avoid rate limits
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    out_df = pd.DataFrame(results)
    out_path = os.path.join(OUTPUT_DIR, f"niche_test_{timestamp()}.csv")
    out_df.to_csv(out_path, index=False)

    blank = out_df[out_df["company_niche"] == ""].shape[0]
    print(f"\nOutput: {out_path}")
    print(f"  Classified:  {len(out_df) - blank}")
    print(f"  Blank niche: {blank} (too vague or no description)")


if __name__ == "__main__":
    main()
