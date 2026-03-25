"""
Step 2: Research each company's own target market and ICP.

Fetches each company's homepage and asks Claude who they sell to and what
job titles their sales team would be prospecting for.

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/2_research.py
"""

import sys
from pathlib import Path

import pandas as pd
import requests

from scripts.ai import ask_claude

OUTPUT_DIR = Path(__file__).parent.parent / "output"

WEBSITE_FETCH_TIMEOUT = 10
MAX_HTML_CHARS = 3000


def fetch_website_text(url: str) -> str:
    """Fetch a website and return truncated plain text. Returns '' on failure."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=WEBSITE_FETCH_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Strip HTML tags crudely — enough for Claude to parse meaning
        text = resp.text
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_HTML_CHARS]
    except Exception:
        return ""


def research_company(name: str, website: str, description: str, industry: str) -> tuple[str, str]:
    """Ask Claude who the company sells to. Returns (target_market, target_titles)."""
    content = ""
    if website:
        content = fetch_website_text(website)

    if content:
        context = f"Company: {name}\nWebsite content (excerpt): {content}"
    elif description:
        context = f"Company: {name}\nIndustry: {industry}\nDescription: {description}"
    else:
        context = f"Company: {name}\nIndustry: {industry}"

    prompt = f"""Based on the information below, answer two questions about this company's sales motion:

1. Who do they primarily sell to? (One sentence — describe their target market/customer type)
2. What job titles would their sales team most likely be prospecting for? (3–5 titles, comma-separated)

{context}

Respond in this exact format:
TARGET_MARKET: <one sentence>
TARGET_TITLES: <title1, title2, title3>

No other text."""

    try:
        raw = ask_claude(prompt).strip()
        target_market = ""
        target_titles = ""
        for line in raw.splitlines():
            if line.startswith("TARGET_MARKET:"):
                target_market = line.replace("TARGET_MARKET:", "").strip()
            elif line.startswith("TARGET_TITLES:"):
                target_titles = line.replace("TARGET_TITLES:", "").strip()
        return target_market, target_titles
    except Exception as e:
        print(f"  [WARN] Claude research failed for {name}: {e}", flush=True)
        return "", ""


def run():
    input_path = OUTPUT_DIR / "contacts.csv"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run 1_find_contacts.py first.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(input_path)
    if df.empty:
        print("No contacts to research.")
        df.to_csv(OUTPUT_DIR / "contacts_researched.csv", index=False)
        return

    # Deduplicate to unique companies
    unique_companies = df.drop_duplicates(subset="firmable_company_id")[
        ["firmable_company_id", "account_name", "company_website", "company_description", "company_industry"]
    ].to_dict(orient="records")

    print(f"Researching {len(unique_companies)} unique companies...")

    research_map = {}
    for i, company in enumerate(unique_companies):
        company_id = str(company["firmable_company_id"])
        name = company.get("account_name", "")
        website = str(company.get("company_website", "") or "")
        description = str(company.get("company_description", "") or "")
        industry = str(company.get("company_industry", "") or "")

        print(f"[{i+1}/{len(unique_companies)}] {name}", flush=True)
        target_market, target_titles = research_company(name, website, description, industry)
        research_map[company_id] = {
            "target_market": target_market,
            "target_titles": target_titles,
        }
        print(f"  Market: {target_market[:80] if target_market else 'N/A'}", flush=True)
        print(f"  Titles: {target_titles[:80] if target_titles else 'N/A'}", flush=True)

    df["target_market"] = df["firmable_company_id"].astype(str).map(
        lambda cid: research_map.get(cid, {}).get("target_market", "")
    )
    df["target_titles"] = df["firmable_company_id"].astype(str).map(
        lambda cid: research_map.get(cid, {}).get("target_titles", "")
    )

    output_path = OUTPUT_DIR / "contacts_researched.csv"
    df.to_csv(output_path, index=False)
    print(f"\nDone. {len(df)} rows written to {output_path}")


if __name__ == "__main__":
    run()
