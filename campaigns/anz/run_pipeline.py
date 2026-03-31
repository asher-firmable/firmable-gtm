"""
ANZ Campaign Pipeline
---------------------
Runs the full pre-outreach pipeline for any ANZ campaign folder:

  Step 1  Load input CSV (auto-detects latest file in <campaign>/input/)
  Step 2  HubSpot eligibility + Firmable enrichment  → data/qualified/
  Step 3  ANZ SMB size filter (apac_sales_team_size ≤ 4 or unknown)  → data/validated/
  Step 4  Normalize company names (regex + domain check for messy names)
  Step 5  Persona enrichment (≤2 personas, lowercase + abbrev rules)
  Step 6  Save final output  → data/final/

Usage:
  PYTHONPATH=. python3 campaigns/anz/run_pipeline.py \\
      --campaign campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach

  PYTHONPATH=. python3 campaigns/anz/run_pipeline.py \\
      --campaign campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach \\
      --input campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach/input/contacts.csv
"""

from __future__ import annotations

import re
import glob
import argparse
import requests
import pandas as pd

from scripts.hubspot_eligibility import run as run_eligibility
from scripts.normalize_company_names import normalize, _fetch_brand_name
from scripts.ai import ask_claude
from scripts.utils import load_csv, save_csv, timestamp


# ── Abbreviations to always capitalise in persona values ──────────────────────
ABBREVS = ["IT", "HR", "L&D", "RTO", "NDIS", "CFO", "SEO", "ERP", "CRM", "AI", "BI"]

PERSONA_PROMPT = """\
Company: {company_name}
Website snippet: {snippet}

What type of professional buyer does this company sell to?
Reply with at most 2 buyer personas joined with " & ".
Rules:
- Lowercase everything EXCEPT abbreviations: IT, HR, L&D, RTO, NDIS, CFO, SEO, ERP, CRM, AI, BI
- Max 2 personas joined with " & "
- 1–3 words per persona
- Examples: IT, marketing, sales, operations, IT & risk management, HR & operations,
  marketing & sales, operations & procurement, IT & HR
Return ONLY the persona phrase, nothing else.\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _latest_csv(folder: str) -> str:
    """Return the most recently modified CSV in folder, or raise."""
    files = sorted(glob.glob(f"{folder}/*.csv"), key=lambda f: __import__('os').path.getmtime(f))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {folder}")
    return files[-1]


def _latest_eligible_csv(qualified_dir: str) -> str:
    """Return the eligible (not with_reasons) CSV from the qualified dir."""
    files = [
        f for f in glob.glob(f"{qualified_dir}/eligible_contacts_*.csv")
        if "with_reasons" not in f
    ]
    files.sort(key=lambda f: __import__('os').path.getmtime(f))
    if not files:
        raise FileNotFoundError(f"No eligible_contacts CSV found in {qualified_dir}")
    return files[-1]


def _is_messy(name: str) -> bool:
    """True if the company name still needs a domain-check cleanup."""
    if not isinstance(name, str):
        return False
    if re.search(r"[^\x00-\x7F®]", name):   # emoji or non-ASCII
        return True
    if re.search(r"\s[-–|]\s", name):         # descriptor separators
        return True
    if len(name.split()) >= 4:                # 4+ words
        return True
    return False


def _fix_abbrevs(text: str) -> str:
    for abbr in ABBREVS:
        text = re.sub(rf"\b{re.escape(abbr)}\b", abbr, text, flags=re.IGNORECASE)
    return text


def _clean_persona(raw: str) -> str:
    """Extract valid persona phrase from potentially verbose Claude response."""
    if not isinstance(raw, str):
        return raw
    raw = raw.strip()
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    valid = []
    skip_prefixes = (
        "based on", "i cannot", "looking at", "wait,", "let me",
        "the website", "this company", "from the", "the snippet",
        "the company", "unable to",
    )
    for line in lines:
        if any(line.lower().startswith(p) for p in skip_prefixes):
            continue
        if len(line) > 50:
            continue
        if re.match(r"^[\w\s&/\-]+$", line) and 1 <= len(line.split()) <= 8:
            valid.append(line)
    result = valid[-1] if valid else lines[0] if lines else raw
    # Strip stray markdown bold markers
    result = re.sub(r"\*+", "", result).strip()
    return _fix_abbrevs(result)


def _fetch_text(domain: str) -> str:
    for scheme in ("https", "http"):
        try:
            r = requests.get(
                f"{scheme}://{domain}", timeout=8,
                headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True,
            )
            text = re.sub(r"<[^>]+>", " ", r.text)
            return re.sub(r"\s+", " ", text).strip()[:2500]
        except Exception:
            continue
    return ""


# ── Pipeline steps ─────────────────────────────────────────────────────────────

def step_size_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int, int]:
    """Keep apac_sales_team_size ≤ 4 or unknown (NaN). Return (kept, n_removed, n_unknown)."""
    col = "apac_sales_team_size"
    keep_mask = df[col].isna() | (df[col] <= 4)
    removed = int((df[col] >= 5).sum())
    unknown = int(df[col].isna().sum())
    return df[keep_mask].copy(), removed, unknown


def step_normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Regex-normalize company names, then domain-check the messy ones."""
    df["company_name"] = df["company_name"].apply(normalize)

    messy_domains = df.loc[df["company_name"].apply(_is_messy), "domain"].unique()
    if messy_domains.size:
        print(f"  Domain-checking {len(messy_domains)} messy company name(s)...")
    checked: dict[str, str] = {}
    for domain in messy_domains:
        name = df.loc[df["domain"] == domain, "company_name"].iloc[0]
        if domain not in checked:
            fixed = _fetch_brand_name(name, domain)
            checked[domain] = fixed
            print(f"    {domain:45s} '{name}' → '{fixed}'")
        df.loc[df["domain"] == domain, "company_name"] = checked[domain]

    return df


def step_persona(df: pd.DataFrame) -> pd.DataFrame:
    """Add persona column (cached per domain)."""
    persona_cache: dict[str, str] = {}
    unique_domains = df["domain"].nunique()
    print(f"  Fetching personas for {unique_domains} unique domain(s)...")

    personas = []
    for i, row in enumerate(df.itertuples(index=False), 1):
        domain = row.domain
        company = row.company_name
        if domain not in persona_cache:
            snippet = _fetch_text(domain)
            raw = ask_claude(
                prompt=PERSONA_PROMPT.format(
                    company_name=company,
                    snippet=snippet if snippet else "(could not fetch)",
                )
            ).strip().strip(".")
            result = _clean_persona(raw)
            persona_cache[domain] = result
            print(f"  [{i}/{len(df)}] {domain} → {result}")
        else:
            print(f"  [{i}/{len(df)}] {domain} → {persona_cache[domain]} (cached)")
        personas.append(persona_cache[domain])

    df["persona"] = personas
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def run(campaign_dir: str, input_path: str | None = None) -> None:
    campaign_dir = campaign_dir.rstrip("/")
    qualified_dir = f"{campaign_dir}/data/qualified"
    validated_dir = f"{campaign_dir}/data/validated"
    final_dir = f"{campaign_dir}/data/final"

    # ── Step 1: resolve input ─────────────────────────────────────────────────
    if not input_path:
        input_path = _latest_csv(f"{campaign_dir}/input")
    print(f"\n{'─'*60}")
    print(f"Input:    {input_path}")
    input_count = len(pd.read_csv(input_path))
    print(f"Rows:     {input_count}")

    # ── Step 2: HubSpot eligibility + Firmable enrichment ─────────────────────
    print(f"\n[Step 2] HubSpot eligibility + Firmable enrichment")
    run_eligibility(input_path, qualified_dir)

    eligible_path = _latest_eligible_csv(qualified_dir)
    eligible_df = load_csv(eligible_path)
    eligible_count = len(eligible_df)

    # ── Step 3: ANZ SMB size filter ───────────────────────────────────────────
    print(f"\n[Step 3] ANZ SMB size filter (apac_sales_team_size ≤ 4 or unknown)")
    validated_df, n_removed, n_unknown = step_size_filter(eligible_df)
    validated_count = len(validated_df)
    print(f"  Kept (≤4):     {validated_count - n_unknown}")
    print(f"  Unknown (kept):{n_unknown}")
    print(f"  Removed (≥5):  {n_removed}")

    ts = timestamp()
    validated_path = f"{validated_dir}/validated_contacts_{ts}.csv"
    save_csv(validated_df, validated_path)

    # ── Step 4: Normalize company names ───────────────────────────────────────
    print(f"\n[Step 4] Normalizing company names")
    validated_df = step_normalize(validated_df)

    # ── Step 5: Persona enrichment ────────────────────────────────────────────
    print(f"\n[Step 5] Persona enrichment")
    validated_df = step_persona(validated_df)

    # ── Step 6: Save final ────────────────────────────────────────────────────
    final_path = f"{final_dir}/final_contacts_{ts}.csv"
    save_csv(validated_df, final_path)

    print(f"\n{'─'*60}")
    print(f"Input contacts:       {input_count}")
    print(f"Passed eligibility:   {eligible_count}")
    print(f"After size filter:    {validated_count}  ({n_removed} excluded ≥5, {n_unknown} unknown → kept)")
    print(f"Final output:         {len(validated_df)}")
    print(f"{'─'*60}")
    print(f"Output: {final_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ANZ campaign pipeline: eligibility → size filter → normalise → persona → final CSV.")
    parser.add_argument("--campaign", required=True, help="Path to campaign folder (e.g. campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach)")
    parser.add_argument("--input", default=None, help="Input CSV path (default: latest CSV in <campaign>/input/)")
    args = parser.parse_args()
    run(args.campaign, args.input)


if __name__ == "__main__":
    main()
