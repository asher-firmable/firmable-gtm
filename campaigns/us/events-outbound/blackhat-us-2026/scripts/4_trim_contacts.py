"""
Black Hat US 2026 — trim each company's contact list down to 15.

For companies with more than 15 contacts, keeps the highest-priority 15 and
routes the rest to a "dropped" file (never silently discarded). Companies
with 15 or fewer contacts are passed through unchanged.

Priority order:
  1. Location: US West Coast (state CA/OR/WA, or a known West Coast city if
     state is blank) ranks above everyone else.
  2. Within the same location bucket, title tier:
       Tier 1 - practitioner-level Sales Development / SDR / BDR /
                Business Development / Inside Sales (no manager-or-above
                qualifier) - the direct outbound-prospecting persona.
       Tier 2 - C-suite (Chief *, CEO/CRO/COO/CSO/CCO, President,
                Founder/Co-Founder, Managing Director)
       Tier 3 - Head of Sales / Head of Revenue / Head of GTM
       Tier 4 - Director / VP (sales-related)
       Tier 5 - Manager (sales-related, non-SDR/BD)
       Tier 6 - everyone else, including plain "GTM" titles and any
                Sales Development/SDR/BDR/Business Development/Inside Sales
                title that itself carries a manager-or-above qualifier
                (e.g. "SDR Manager", "Director of Business Development") -
                per explicit instruction these are treated like plain ICs,
                not boosted into Tier 1.
  3. Tiebreak: contact data completeness (email + mobile > one > neither),
     then original row order.

Input: newest CSV/XLSX in input/.

Run:
  PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/4_trim_contacts.py
"""

import argparse
import glob
import re
import sys

import pandas as pd

from scripts.utils import ensure_dirs, load_csv, save_csv, timestamp

CAMPAIGN_DIR = "campaigns/us/events-outbound/blackhat-us-2026"
INPUT_DIR = f"{CAMPAIGN_DIR}/input"
OUTPUT_DIR = f"{CAMPAIGN_DIR}/output"
CAP = 15

WEST_COAST_STATES = {"CA", "OR", "WA"}
WEST_COAST_CITIES = {
    "los angeles", "san francisco", "san diego", "seattle", "portland",
    "sacramento", "san jose", "oakland", "bellevue", "tacoma", "long beach",
    "anaheim", "irvine", "fresno", "eugene", "vancouver", "spokane",
    "redmond", "santa monica", "burbank", "pasadena", "fremont",
    "santa clara", "sunnyvale", "palo alto", "mountain view", "berkeley",
}

SDR_BD_KEYWORDS = ["sdr", "bdr", "sales development", "business development", "inside sales"]
# "president" is deliberately excluded here and handled separately below, since
# "vice president" must resolve to VP (tier 4), not standalone President (tier 2/C-suite).
MODIFIER_KEYWORDS = [
    "manager", "director", "vp", "vice president", "svp", "avp", "rvp", "evp", "head of",
    "chief", "ceo", "coo", "cro", "cso", "cco", "founder", "team lead", "leader", "lead",
]
CSUITE_KEYWORDS = ["chief", "ceo", "cro", "coo", "cso", "cco", "founder", "co-founder", "managing director"]
VP_KEYWORDS = ["vice president", "vp", "svp", "avp", "rvp", "evp"]
DIRECTOR_KEYWORDS = ["director"]


def _has_word(t: str, keyword: str) -> bool:
    # Word-boundary match so short acronyms (cco, vp, ceo...) don't hit as
    # substrings of ordinary words, e.g. "cco" inside "Account".
    return re.search(r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])", t) is not None


def classify_tier(title: str) -> int:
    t = _clean(title).lower()

    is_sdr_bd = any(_has_word(t, k) for k in SDR_BD_KEYWORDS)
    has_modifier = any(_has_word(t, k) for k in MODIFIER_KEYWORDS) or _has_word(t, "president")

    if is_sdr_bd:
        return 1 if not has_modifier else 6

    if any(_has_word(t, k) for k in CSUITE_KEYWORDS):
        return 2
    if any(_has_word(t, k) for k in VP_KEYWORDS):
        return 4
    if _has_word(t, "president"):
        return 2
    if _has_word(t, "head of") or _has_word(t, "head"):
        return 3
    if any(_has_word(t, k) for k in DIRECTOR_KEYWORDS):
        return 4
    if _has_word(t, "manager"):
        return 5
    return 6


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def is_west_coast(state: str, suburb: str) -> bool:
    state = _clean(state).upper()
    if state:
        return state in WEST_COAST_STATES
    suburb = _clean(suburb).lower()
    return suburb in WEST_COAST_CITIES


def contact_quality_rank(row) -> int:
    has_email = bool(_clean(row.get("primary_work_email", "")))
    has_mobile = bool(_clean(row.get("primary_mobile", "")))
    if has_email and has_mobile:
        return 0
    if has_email or has_mobile:
        return 1
    return 2


def load_input(input_path=None):
    if input_path:
        files = [input_path]
    else:
        patterns = [f"{INPUT_DIR}/*.csv", f"{INPUT_DIR}/*.xlsx", f"{INPUT_DIR}/*.xls"]
        files = []
        for p in patterns:
            files.extend(glob.glob(p))
    if not files:
        print(f"No input file found in {INPUT_DIR}/. Drop your curated CSV there and retry.")
        sys.exit(1)
    path = sorted(files)[-1]
    print(f"Loading {path}")
    df = load_csv(path)
    print(f"  {len(df)} rows, columns: {list(df.columns)}\n")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None, help="Path to input CSV/XLSX (defaults to latest file in input/)")
    parser.add_argument("--cap", type=int, default=CAP, help=f"Max contacts to keep per company (default {CAP})")
    args = parser.parse_args()

    ensure_dirs(OUTPUT_DIR)
    df = load_input(args.input)

    for required in ["company_name", "position", "state", "suburb"]:
        if required not in df.columns:
            print(f"Missing expected column '{required}'. Available columns: {list(df.columns)}")
            sys.exit(1)

    df["priority_tier"] = df["position"].apply(classify_tier)
    df["is_west_coast"] = df.apply(lambda r: is_west_coast(r["state"], r["suburb"]), axis=1)
    df["_quality_rank"] = df.apply(contact_quality_rank, axis=1)

    keep_indices = []
    drop_indices = []
    trimmed_companies = 0

    for company, group in df.groupby("company_name", sort=False):
        if len(group) <= args.cap:
            keep_indices.extend(group.index.tolist())
            continue
        trimmed_companies += 1
        ranked = group.sort_values(
            by=["is_west_coast", "priority_tier", "_quality_rank"],
            ascending=[False, True, True],
            kind="stable",
        )
        keep_indices.extend(ranked.index[: args.cap].tolist())
        drop_indices.extend(ranked.index[args.cap :].tolist())

    kept_df = df.loc[df.index.isin(keep_indices)].sort_index().drop(columns=["_quality_rank"])
    dropped_df = df.loc[df.index.isin(drop_indices)].sort_index().drop(columns=["_quality_rank"])

    ts = timestamp()
    kept_path = f"{OUTPUT_DIR}/4_trimmed_contacts_{ts}.csv"
    dropped_path = f"{OUTPUT_DIR}/4_dropped_contacts_{ts}.csv"
    save_csv(kept_df, kept_path)
    save_csv(dropped_df, dropped_path)

    print(f"Companies trimmed: {trimmed_companies}")
    print(f"Contacts kept: {len(kept_df)}")
    print(f"Contacts dropped: {len(dropped_df)}")
    print(f"Total in == total out: {len(df)} == {len(kept_df) + len(dropped_df)}\n")
    print(f"Kept:    {kept_path}")
    print(f"Dropped: {dropped_path}")


if __name__ == "__main__":
    main()
