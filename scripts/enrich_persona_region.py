"""
Persona & Region Enrichment
----------------------------
Adds two columns to a campaign CSV:
  • persona — 1-2 word description of the type of leader this company sells to
              (e.g. "Sales", "Cybersecurity", "Finance", "HR", "Data")
  • region  — geographic scope derived from the contact's position + headline

Persona is determined by fetching each unique company's homepage and asking Claude.
Results are cached per domain so each company is only fetched once.
Multiple persona words are joined with "/" not ",".

Region priority (from position + headline text):
  1. SEA + ANZ (or ASEAN + ANZ) → APAC  (covers both)
  2. ASEAN                       → ASEAN
  3. SEA / South-East Asia       → SEA
  4. ANZ                         → ANZ
  5. APJ                         → APJ
  6. APAC / Asia Pacific         → APAC
  7. (default)                   → APAC

Usage:
  PYTHONPATH=. python3 scripts/enrich_persona_region.py --input path/to/contacts.csv
  PYTHONPATH=. python3 scripts/enrich_persona_region.py --input path/to/contacts.csv --output path/to/out.csv
"""

from __future__ import annotations

import re
import argparse
import requests
import pandas as pd

from scripts.ai import ask_claude
from scripts.utils import load_csv, save_csv


# ── Region ─────────────────────────────────────────────────────────────────────

def get_region(position: str, headline: str) -> str:
    text = f"{position or ''} {headline or ''}".upper()
    has_sea   = bool(re.search(r"\bSEA\b|SOUTH[\s-]?EAST ASIA|SOUTHEAST ASIA", text))
    has_anz   = bool(re.search(r"\bANZ\b", text))
    has_asean = bool(re.search(r"\bASEAN\b", text))
    has_apj   = bool(re.search(r"\bAPJ\b", text))
    has_apac  = bool(re.search(r"\bAPAC\b|ASIA[\s-]?PACIFIC", text))

    if (has_sea and has_anz) or (has_asean and has_anz):
        return "APAC"
    if has_asean:
        return "ASEAN"
    if has_sea:
        return "SEA"
    if has_anz:
        return "ANZ"
    if has_apj:
        return "APJ"
    if has_apac:
        return "APAC"
    return "APAC"


# ── Persona ─────────────────────────────────────────────────────────────────────

def _fetch_text(domain: str) -> str:
    for scheme in ("https", "http"):
        try:
            r = requests.get(
                f"{scheme}://{domain}", timeout=8,
                headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True,
            )
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:2500]
        except Exception:
            continue
    return ""


def get_persona(company_name: str, domain: str, cache: dict) -> str:
    if domain in cache:
        return cache[domain]

    text = _fetch_text(domain)
    prompt = (
        f"Company: {company_name}\n"
        f"Website snippet: {text if text else '(could not fetch)'}\n\n"
        "This company uses B2B data tools to find leads. Based on their product or service, "
        "what type of professional leader are they most likely selling to or trying to reach?\n\n"
        "Reply with ONLY 1-2 words. Examples: Sales, Marketing, Cybersecurity, Finance, HR, "
        "Operations, Data, Healthcare, IT, Risk, Retail, Legal, Aviation.\n\n"
        "Just the 1-2 word answer, nothing else."
    )
    result = ask_claude(prompt=prompt).strip().strip(".")
    # Standardise separators: commas → slashes
    result = result.replace(", ", "/").replace(",", "/")
    cache[domain] = result
    return result


# ── Main ────────────────────────────────────────────────────────────────────────

def run(input_path: str, output_path: str) -> None:
    df = load_csv(input_path)

    for col in ("company_name", "domain", "position", "headline"):
        if col not in df.columns:
            raise ValueError(f"Input CSV must have a '{col}' column")

    persona_cache: dict = {}
    personas, regions = [], []

    total = len(df)
    for i, row in enumerate(df.itertuples(index=False), 1):
        region = get_region(
            getattr(row, "position", "") or "",
            getattr(row, "headline", "") or "",
        )
        persona = get_persona(row.company_name, row.domain, persona_cache)
        personas.append(persona)
        regions.append(region)
        print(f"[{i}/{total}] {row.domain} | persona={persona} | region={region}")

    df["persona"] = personas
    df["region"] = regions

    save_csv(df, output_path)
    print(f"\nOutput: {output_path}")
    print(df[["company_name", "persona", "region"]].drop_duplicates().to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich campaign CSV with persona and region columns.")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", default=None, help="Output CSV path (default: overwrite input)")
    args = parser.parse_args()
    run(args.input, args.output or args.input)


if __name__ == "__main__":
    main()
