"""
Company Name Normalisation
--------------------------
Strips legal suffixes, dot-TLDs, and parenthetical descriptors from the
company_name column of a campaign CSV. Prints a diff of what changed.

Rules applied in order:
  1. Manual overrides (exact-match corrections verified via domain)
  2. Strip parenthetical descriptors  e.g. "LSEG (London Stock Exchange Group)" → "LSEG"
  3. Strip dot-TLDs                   e.g. "H2O.ai" → "H2O", "Accedo.tv" → "Accedo"
  4. Strip legal suffixes (loop ×3)   e.g. "Pte. Ltd.", "Corporation", "Inc."
  5. (Optional) --check-domains: for names still ≥3 words, fetch homepage and ask
     Claude for the short brand name. Use the full readable name if the site only
     returns a generic abbreviation (e.g. prefer "Public Sector Network" over "PSN").

Usage:
  PYTHONPATH=. python3 scripts/normalize_company_names.py --input path/to/contacts.csv
  PYTHONPATH=. python3 scripts/normalize_company_names.py --input path/to/contacts.csv --output path/to/out.csv
  PYTHONPATH=. python3 scripts/normalize_company_names.py --input path/to/contacts.csv --check-domains
"""

from __future__ import annotations

import re
import argparse
import requests
import pandas as pd

from scripts.utils import load_csv, save_csv

# ── Manual overrides (domain-verified) ────────────────────────────────────────
# Add new entries here when a 3+ word name is confirmed via domain check.
OVERRIDES: dict[str, str] = {
    "Archer Integrated Risk Management": "Archer",   # archerirm.com
    "Info Tech Research Group": "Info Tech",          # infotech.com
}

# ── Regex patterns ─────────────────────────────────────────────────────────────
_LEGAL_SUFFIXES = [
    # Singapore / SEA
    r"Pte\.?\s*Ltd\.?", r"Private Limited", r"Pvt\.?\s*Ltd\.?",
    # Australia
    r"Pty\.?\s*Ltd\.?",
    # Malaysia
    r"Sdn\.?\s*Bhd\.?", r"Berhad",
    # Global
    r"Limited", r"Ltd\.?", r"Inc\.?", r"Corp\.?", r"Corporation",
    r"LLC", r"L\.L\.C\.?", r"GmbH", r"PLC", r"plc", r"AG",
    r"B\.?V\.?", r"S\.?A\.?", r"N\.?V\.?", r"Co\.",
]
_SUFFIX_RE = re.compile(
    r"[\s,]+(" + "|".join(_LEGAL_SUFFIXES) + r")[\s,]*$",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\s*\(.*?\)\s*$")
_DOTTLD_RE = re.compile(r"\.(ai|tv|io|co|app|net|fm|so|gg|xyz)$", re.IGNORECASE)


def normalize(name: str) -> str:
    if not isinstance(name, str):
        return name
    name = name.strip()
    if name in OVERRIDES:
        return OVERRIDES[name]
    name = _PAREN_RE.sub("", name).strip()
    name = _DOTTLD_RE.sub("", name).strip()
    for _ in range(3):
        new = _SUFFIX_RE.sub("", name).strip().rstrip(",").strip()
        if new == name:
            break
        name = new
    return name


def _fetch_brand_name(company_name: str, domain: str) -> str:
    """Fetch homepage and ask Claude for the short brand name. Falls back to current name."""
    try:
        from scripts.ai import ask_claude
        resp = requests.get(
            f"https://{domain}", timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True,
        )
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()[:2000]
        result = ask_claude(
            prompt=(
                f"Company: {company_name}\n"
                f"Website snippet: {text}\n\n"
                "What is the short, commonly used brand name for this company? "
                "Return ONLY the name (1-3 words max). "
                "If the site only shows a generic abbreviation, return the full readable name instead."
            )
        ).strip().strip(".")
        return result
    except Exception:
        return company_name


def run(input_path: str, output_path: str, check_domains: bool = False) -> None:
    df = load_csv(input_path)

    if "company_name" not in df.columns:
        raise ValueError("Input CSV must have a 'company_name' column")

    original = df["company_name"].copy()
    df["company_name"] = df["company_name"].apply(normalize)

    # Optional domain check for names still ≥3 words
    if check_domains and "domain" in df.columns:
        mask = df["company_name"].str.split().str.len() >= 3
        checked: dict[str, str] = {}
        for idx in df[mask].index:
            domain = df.at[idx, "domain"]
            name = df.at[idx, "company_name"]
            if domain not in checked:
                fetched = _fetch_brand_name(name, domain)
                checked[domain] = fetched
                print(f"  [domain check] {domain} → '{fetched}'")
            df.at[idx, "company_name"] = checked[domain]

    # Diff
    changed = df[original.str.strip() != df["company_name"]][
        ["company_name"]
    ].copy()
    changed["before"] = original[changed.index].str.strip()
    changed["after"] = changed["company_name"]

    if len(changed):
        print(f"\nChanged {len(changed)} of {len(df)} names:")
        for _, row in changed.iterrows():
            print(f"  {row['before']!r:50s} → {row['after']!r}")
    else:
        print("No names changed.")

    save_csv(df, output_path)
    print(f"\nOutput: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalise company_name column in a campaign CSV.")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", default=None, help="Output CSV path (default: overwrite input)")
    parser.add_argument("--check-domains", action="store_true",
                        help="Web-fetch homepage for names still ≥3 words after rule-based normalisation")
    args = parser.parse_args()
    run(args.input, args.output or args.input, args.check_domains)


if __name__ == "__main__":
    main()
