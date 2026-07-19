"""
ZoomInfo displacement — generate Email 1 copy for each contact.

Expects company_niche, signal_play_1, signal_play_2 columns in the input CSV.
These are produced by running Clay AI columns (Column A: Niche Classifier,
Column B: Signal Plays) on the company table first.

If signal_play_1 or signal_play_2 is absent or empty for a row, that row is
flagged as needs_enrichment=True and no copy is generated — run Clay first.

Run:
  PYTHONPATH=. python3 campaigns/us/zoominfo-displacement/scripts/generate_copy.py
"""

import os
import sys
import glob
import pandas as pd
from scripts.utils import ensure_dirs, timestamp

INPUT_DIR  = "campaigns/us/zoominfo-displacement/input"
OUTPUT_DIR = "campaigns/us/zoominfo-displacement/output"

# ── Fixed email template ──────────────────────────────────────────────────────

EMAIL_1_SUBJECT = "a database tells reps who exists. signals tell them who to call."

EMAIL_1_BODY = (
    "Hey {first_name},\n\n"
    "Your team might be using or used ZoomInfo before? Their basic plan gives you B2B contact data, "
    "but features like buying intent or signals sit behind another paywall.\n\n"
    "Firmable bundles everything — role changes, funding rounds, hiring surges, search intent — "
    "in the platform from day one, not an upsell, including verified contact information refreshed weekly.\n\n"
    "Some actual signal-plays {company_name} can run right away:\n"
    "- {signal_play_1}\n"
    "- {signal_play_2}\n\n"
    "Worth exploring more?"
)

EMAIL_1_PS = (
    "We're in early US rollout. First accounts help shape what we build next "
    "— signals, contact types, integrations."
)

# ── Persona detection ─────────────────────────────────────────────────────────
# Retained for people-table reference and future segmentation.
# Order matters — check more specific personas first.

GROWTH_LEADER_KEYWORDS = [
    "vp growth", "vp of growth", "vice president growth", "vice president of growth",
    "head of growth", "growth director", "director of growth",
    "growth marketing", "growth & partnerships", "growth and partnerships",
    "chief growth officer", "cgo",
]

SDR_KEYWORDS = [
    "sdr manager", "bdr manager", "sales development manager",
    "head of sales development", "head of sdrs", "head of bdrs",
    "sales development lead", "director of sales development",
    "vp of sales development",
]

BIZDEV_LEADER_KEYWORDS = [
    "director of business development", "business development director",
    "vp business development", "vp of business development",
    "vice president business development", "vice president of business development",
    "head of business development", "chief business development officer",
    "business development lead",
]

CHANNEL_PARTNER_KEYWORDS = [
    "channel sales", "director of channel", "vp channel", "vp of channel",
    "channel manager", "channel lead", "channel account",
    "partner sales", "partner development manager", "partner development lead",
    "vp partnerships", "vp of partnerships", "head of partnerships",
    "director of partnerships", "alliances manager", "vp alliances",
    "head of alliances",
]

REVOPS_KEYWORDS = [
    "revenue operations", "revops", "revenue ops",
    "sales operations", "sales ops",
    "marketing operations", "marketing ops",
    "demand generation", "head of marketing", "marketing manager",
    "marketing director", "director of marketing",
    "chief marketing officer", "cmo",
    "vp marketing", "vp of marketing",
]

SALES_LEADER_KEYWORDS = [
    "vp sales", "vp of sales", "vice president sales", "vice president of sales",
    "head of sales", "sales director", "director of sales",
    "chief revenue officer", "cro", "chief sales officer",
    "national sales manager", "regional sales manager",
    "regional vice president", "regional vp",
    "director of client development", "client development director",
    "ceo", "chief executive", "founder", "co-founder",
    "president", "managing director",
    "account executive", "account manager",
]


def classify_persona(title: str) -> str:
    """Return persona name, or 'uncertain' if title doesn't match any keyword list."""
    t = title.lower().strip()
    for kw in GROWTH_LEADER_KEYWORDS:
        if kw in t:
            return "growth_leader"
    for kw in SDR_KEYWORDS:
        if kw in t:
            return "sdr_manager"
    for kw in BIZDEV_LEADER_KEYWORDS:
        if kw in t:
            return "bizdev_leader"
    for kw in CHANNEL_PARTNER_KEYWORDS:
        if kw in t:
            return "channel_partner"
    for kw in REVOPS_KEYWORDS:
        if kw in t:
            return "revops"
    for kw in SALES_LEADER_KEYWORDS:
        if kw in t:
            return "sales_leader"
    return "uncertain"


# ── Column detection ──────────────────────────────────────────────────────────

def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    lowered = {col.lower().replace(" ", "_"): col for col in df.columns}
    for c in candidates:
        if c.lower().replace(" ", "_") in lowered:
            return lowered[c.lower().replace(" ", "_")]
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs(OUTPUT_DIR)

    patterns = [f"{INPUT_DIR}/*.csv", f"{INPUT_DIR}/*.xlsx", f"{INPUT_DIR}/*.xls"]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    if not files:
        print(f"No input file found in {INPUT_DIR}/. Drop a CSV or Excel file there and retry.")
        sys.exit(1)

    input_path = sorted(files)[-1]
    print(f"Loading {input_path}")

    if input_path.endswith(".csv"):
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)

    print(f"  {len(df)} rows, columns: {list(df.columns)}")

    first_name_col  = find_col(df, ["Final First Name", "first_name", "First Name", "firstname", "first"])
    title_col       = find_col(df, ["Position", "title", "job_title", "Job Title", "Title"])
    email_col       = find_col(df, ["Primary work email", "email", "Email", "email_address"])
    company_col     = find_col(df, ["Company name", "company", "Company", "company_name"])
    niche_col       = find_col(df, ["company_niche", "Company niche", "niche"])
    signal_1_col    = find_col(df, ["signal_play_1", "Signal play 1", "signal_1"])
    signal_2_col    = find_col(df, ["signal_play_2", "Signal play 2", "signal_2"])

    missing = [name for name, col in [
        ("first_name", first_name_col), ("title", title_col),
        ("email", email_col), ("company", company_col),
    ] if col is None]

    if missing:
        print(f"Could not find required columns: {missing}")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    has_signal_cols = signal_1_col is not None and signal_2_col is not None
    if not has_signal_cols:
        print(
            "  WARNING: signal_play_1 / signal_play_2 columns not found. "
            "Run Clay AI columns (Column A + B) on the company table first.\n"
            "  All rows will be flagged as needs_enrichment=True — no copy generated."
        )

    print(f"  Signal columns present: {has_signal_cols}")
    print(f"  Mapped: first_name={first_name_col}, title={title_col}, email={email_col}, company={company_col}")

    rows = []
    persona_counts: dict[str, int] = {}
    needs_enrichment_count = 0
    uncertain_count = 0

    for _, row in df.iterrows():
        first_name   = str(row[first_name_col]).strip()
        title        = str(row.get(title_col, "") if title_col else "").strip()
        email        = str(row.get(email_col, "") if email_col else "").strip()
        company      = str(row.get(company_col, "") if company_col else "").strip()
        company_niche = str(row.get(niche_col, "") if niche_col else "").strip()
        signal_play_1 = str(row.get(signal_1_col, "") if signal_1_col else "").strip()
        signal_play_2 = str(row.get(signal_2_col, "") if signal_2_col else "").strip()

        persona = classify_persona(title)

        if persona == "uncertain":
            uncertain_count += 1
            rows.append({
                "first_name": first_name, "email": email, "company": company,
                "title": title, "persona": "uncertain",
                "company_niche": company_niche,
                "signal_play_1": signal_play_1, "signal_play_2": signal_play_2,
                "needs_enrichment": not has_signal_cols or not signal_play_1 or not signal_play_2,
                "email_1_subject": "", "email_1_body": "", "email_1_ps": "",
            })
            continue

        persona_counts[persona] = persona_counts.get(persona, 0) + 1

        missing_signals = (
            not has_signal_cols
            or not signal_play_1
            or signal_play_1 in ("nan", "None", "")
            or not signal_play_2
            or signal_play_2 in ("nan", "None", "")
        )

        if missing_signals:
            needs_enrichment_count += 1
            rows.append({
                "first_name": first_name, "email": email, "company": company,
                "title": title, "persona": persona,
                "company_niche": company_niche,
                "signal_play_1": signal_play_1, "signal_play_2": signal_play_2,
                "needs_enrichment": True,
                "email_1_subject": "", "email_1_body": "", "email_1_ps": "",
            })
            continue

        body = EMAIL_1_BODY.format(
            first_name=first_name,
            company_name=company,
            signal_play_1=signal_play_1,
            signal_play_2=signal_play_2,
        )

        rows.append({
            "first_name": first_name, "email": email, "company": company,
            "title": title, "persona": persona,
            "company_niche": company_niche,
            "signal_play_1": signal_play_1, "signal_play_2": signal_play_2,
            "needs_enrichment": False,
            "email_1_subject": EMAIL_1_SUBJECT,
            "email_1_body":    body,
            "email_1_ps":      EMAIL_1_PS,
        })

    out_df = pd.DataFrame(rows)
    out_path = os.path.join(OUTPUT_DIR, f"copy_{timestamp()}.csv")
    out_df.to_csv(out_path, index=False)

    copy_generated = len(out_df) - uncertain_count - needs_enrichment_count

    print(f"\nOutput: {out_path}")
    print(f"  Total:              {len(out_df)}")
    print(f"  Copy generated:     {copy_generated}")
    print(f"  Needs enrichment:   {needs_enrichment_count} (run Clay columns first)")
    print(f"  Uncertain persona:  {uncertain_count} (no copy generated)")
    if persona_counts:
        print("  Persona breakdown:")
        for persona, count in sorted(persona_counts.items()):
            print(f"    {persona:<20} {count}")


if __name__ == "__main__":
    main()
