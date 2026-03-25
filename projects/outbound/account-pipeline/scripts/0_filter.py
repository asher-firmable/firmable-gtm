"""
Step 0: Filter junk accounts from input Excel/CSV.

Removes:
- Lead generation / contact data companies (Apollo, ZoomInfo, Lusha, etc.)
- Companies with non-English or suspect names

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/0_filter.py --input data/input/accounts.xlsx
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.ai import ask_claude

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def classify_accounts(accounts: list[dict]) -> list[dict]:
    """Ask Claude to classify each account. Returns list with 'keep' and 'filter_reason' added."""
    numbered = "\n".join(
        f"{i+1}. {a.get('account_name', a.get('company_name', 'Unknown'))}"
        for i, a in enumerate(accounts)
    )

    prompt = f"""You are reviewing a list of companies for a B2B outbound campaign.

For each company, decide whether to EXCLUDE it for one of two reasons:
1. LEAD_GEN — the company is a lead generation, contact data, or sales tooling vendor
   (e.g. Apollo, ZoomInfo, Lusha, Cognism, Hunter, Clearbit, Seamless, LeadIQ, SalesLoft,
   Outreach, DiscoverOrg, Bombora, Demandbase, or similar products).
2. SUSPECT_NAME — the company name contains non-English characters, Chinese/Japanese/Korean
   script, garbled strings, or is otherwise unclear/suspicious.

If neither applies, respond KEEP.

Return a JSON array with one object per company in the same order:
[{{"name": "...", "decision": "KEEP"|"LEAD_GEN"|"SUSPECT_NAME"}}]

Companies:
{numbered}

Return only the JSON array, no other text."""

    raw = ask_claude(prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    decisions = json.loads(raw.strip())
    return decisions


def run(input_path: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = Path(input_path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="warn", engine="python")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Accept common column name aliases
    if "firmable_id" in df.columns and "firmable_company_id" not in df.columns:
        df = df.rename(columns={"firmable_id": "firmable_company_id"})
    if "company" in df.columns and "account_name" not in df.columns and "company_name" not in df.columns:
        df = df.rename(columns={"company": "account_name"})

    if "firmable_company_id" not in df.columns:
        print("ERROR: Input must have a 'firmable_company_id' (or 'Firmable ID') column.", file=sys.stderr)
        sys.exit(1)

    if "account_name" not in df.columns and "company_name" not in df.columns:
        print("ERROR: Input must have an 'account_name', 'company_name', or 'Company' column.", file=sys.stderr)
        sys.exit(1)

    accounts = df.to_dict(orient="records")
    print(f"Loaded {len(accounts)} accounts from {path.name}")

    # Classify in batches of 50 to stay within prompt limits
    BATCH_SIZE = 50
    all_decisions = []
    for i in range(0, len(accounts), BATCH_SIZE):
        batch = accounts[i : i + BATCH_SIZE]
        print(f"  Classifying accounts {i+1}–{min(i+BATCH_SIZE, len(accounts))}...", flush=True)
        decisions = classify_accounts(batch)
        all_decisions.extend(decisions)

    kept = []
    excluded = []
    for account, decision in zip(accounts, all_decisions):
        d = decision.get("decision", "KEEP")
        if d == "KEEP":
            kept.append(account)
        else:
            account["filter_reason"] = d
            excluded.append(account)

    kept_path = OUTPUT_DIR / "filtered_accounts.csv"
    excl_path = OUTPUT_DIR / "excluded_accounts.csv"

    if kept:
        pd.DataFrame(kept).to_csv(kept_path, index=False)
    else:
        pd.DataFrame(columns=df.columns).to_csv(kept_path, index=False)

    if excluded:
        pd.DataFrame(excluded).to_csv(excl_path, index=False)
    else:
        pd.DataFrame(columns=list(df.columns) + ["filter_reason"]).to_csv(excl_path, index=False)

    print(f"\nDone. Kept: {len(kept)}, Excluded: {len(excluded)}")
    print(f"  -> {kept_path}")
    print(f"  -> {excl_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input Excel or CSV file")
    args = parser.parse_args()
    run(args.input)
