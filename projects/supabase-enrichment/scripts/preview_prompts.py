"""
Preview classification prompts on pending rows without running Trigger.dev.

Usage:
    PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py
    PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py --limit 3
"""

import argparse
import os
import sys
import requests
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dotenv import load_dotenv
from scripts.ai import ask_claude
from scripts.utils import load_csv

load_dotenv()

COMPANY_TYPE_PROMPT = """
You are a B2B company classifier. Classify the company into exactly one of these five types:

- SaaS/Software providers: sells a software product on a subscription or license basis
- MSPs: managed service provider; manages IT infrastructure or cloud environments for clients on an ongoing basis
- IT services firms: IT consulting, staffing, implementation, or support services (people and expertise, not a product)
- IT Solutions providers: sells technology solutions that combine hardware and/or software into a packaged system (e.g. control room systems, networking hardware, industrial tech, AV/surveillance, purpose-built devices); may also offer related services
- Other B2B companies: any other B2B business that doesn't fit the above (e.g. pure hardware manufacturing, robotics integrators, engineering firms, staffing outside IT)

Key distinctions:
- If the company's core offering is a deployable technology system (hardware+software together), use IT Solutions providers — not SaaS/Software providers or Other B2B companies
- If the company makes or integrates physical machinery/robotics with no software product, use Other B2B companies
- MSPs vs IT services firms: MSPs implies ongoing managed contracts; IT services firms implies project-based consulting or implementation
- Pure IT staffing and recruiting firms (no consulting, no implementation — just placing candidates or contractors) go to Other B2B companies, not IT services firms

Reply with a JSON object: {"label": "<one of the five types>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}
""".strip()

PERSONA_PROMPT = """
You are a B2B sales analyst. Identify who the PRIMARY buyer or target customer is for this company.

Return the label as exactly two roles joined with "or", followed by a shared descriptor where it makes sense.
Format: "[Role1] or [Role2] [shared descriptor]"
All lowercase. 3-6 words total.

Rules:
- Always two roles joined with "or" — never one, never three
- Pick roles that are genuinely different but both realistic buyers
- Use the most specific titles that fit — avoid vague catch-alls like "business leaders"
- The shared descriptor (managers, leaders, directors, owners, operators, etc.) is optional if both roles already end in a title

Reply with a JSON object:
{"label": "<label>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}

Examples:
- "CFOs or operations managers"
- "IT or security leaders"
- "CMOs or marketing directors"
- "restaurant or hotel operators"
- "developers or project owners"
- "CIOs or IT managers"
- "HR or wellness managers"
- "shipowners or fleet managers"
- "bank or fintech leaders"
- "L&D or HR managers"
""".strip()

CONFIDENCE_THRESHOLD = 0.75


def fetch_firmable_description(firmable_id: str) -> Optional[str]:
    api_key = os.getenv("FIRMABLE_API_KEY")
    if not api_key or not firmable_id:
        return None
    try:
        resp = requests.get(
            "https://api.firmable.com/company",
            params={"id": firmable_id},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if not resp.ok:
            return None
        data = resp.json()
        return data.get("description", "").strip() or data.get("tagline", "").strip() or None
    except Exception:
        return None


def classify(system_prompt: str, description: str, domain: str) -> dict:
    import json, re
    user_msg = (
        f"Company domain: {domain}\n\nDescription:\n{description}"
        if description
        else f"Company domain: {domain}\n\n(No description available.)"
    )
    raw = ask_claude(prompt=user_msg, context=system_prompt)
    try:
        cleaned = re.sub(r"```json\n?|```", "", raw).strip()
        return json.loads(cleaned)
    except Exception:
        return {"label": "Unknown", "confidence": 0.0, "reasoning": raw[:200]}


def main():
    input_dir = os.path.join(os.path.dirname(__file__), "..", "input")
    csv_files = [f for f in os.listdir(input_dir) if f.endswith(".csv") or f.endswith(".xlsx")]
    if not csv_files:
        print(f"No CSV found in {input_dir}")
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0, help="Skip first N rows")
    parser.add_argument("--file", default=None, help="CSV filename (default: first file found)")
    args = parser.parse_args()

    csv_path = os.path.join(input_dir, args.file or csv_files[0])
    print(f"Reading from: {os.path.basename(csv_path)}")

    df = load_csv(csv_path)
    if "company_domain" in df.columns and "domain" not in df.columns:
        df = df.rename(columns={"company_domain": "domain"})
    df = df.iloc[args.offset : args.offset + args.limit]

    print(f"\nPreviewing rows {args.offset + 1}–{args.offset + len(df)}\n" + "=" * 80)

    for _, row in df.iterrows():
        name = str(row.get("company", "") or row.get("domain", "")).strip()
        domain = str(row.get("domain", "")).strip().lstrip("www.").lower()

        # Extract raw Firmable ID from URL
        raw_fid = str(row.get("firmable_id", "")).strip()
        firmable_id = raw_fid.rstrip("/").split("/")[-1] if raw_fid.startswith("http") else raw_fid or None
        print(f"\n{name} ({domain})")
        print("-" * 60)

        # --- Inputs ---
        industry = str(row.get("industry", "") or "").strip()
        country  = str(row.get("country",  "") or "").strip()
        print(f"  Industry:    {industry or 'N/A'}")
        print(f"  Country:     {country or 'N/A'}")
        print(f"  Firmable ID: {firmable_id or 'N/A'}")

        # Get description — Firmable API first, then CSV column
        description = fetch_firmable_description(firmable_id) if firmable_id else None
        if description:
            desc_source = "Firmable API"
        else:
            csv_desc = str(row.get("description", "") or "").strip()
            description = csv_desc if csv_desc and csv_desc != "nan" else ""
            desc_source = "CSV" if description else "none"

        print(f"  Desc source: {desc_source}")
        if description:
            print(f"  Description: {description}")
        else:
            print(f"  Description: (none)")

        # --- Classification ---
        ct = classify(COMPANY_TYPE_PROMPT, description, domain)
        persona = classify(PERSONA_PROMPT, description, domain)

        ct_flag = " LOW CONFIDENCE" if ct["confidence"] < CONFIDENCE_THRESHOLD else ""
        p_flag  = " LOW CONFIDENCE" if persona["confidence"] < CONFIDENCE_THRESHOLD else ""

        print()
        print(f"  COMPANY TYPE:   {ct['label']} ({ct['confidence']:.0%}){ct_flag}")
        print(f"  Reasoning:      {ct['reasoning']}")
        print()
        print(f"  TARGET PERSONA: {persona['label']} ({persona['confidence']:.0%}){p_flag}")
        print(f"  Reasoning:      {persona['reasoning']}")

    print("\n" + "=" * 80)
    print("Done. Adjust prompts in this script, re-run to preview again.")
    print("When happy, trigger enrich-batch in Trigger.dev to write results to Supabase.")


if __name__ == "__main__":
    main()
