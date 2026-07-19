"""
Step 1: Classify US sales influencers into outreach buckets using Claude.

Classification adds:
  buckets       — comma-separated list of assigned outreach buckets (Product Feedback, Warm Intro, Influencer)
  seniority     — C-Suite / VP / Director / Manager / Individual Contributor / Other
  person_type   — e.g. Sales Leader (Active Org), GTM/RevOps Leader, Business Owner, Sales Coach/Trainer, etc.
  + individual boolean columns: product_feedback, warm_intro, influencer
  + classification_reasoning

The 'about' column is excluded from Claude context — too noisy, not useful for classification.

Usage:
  PYTHONPATH=. python3 projects/us-influencer-outreach/scripts/enrich_and_classify.py

Input:  projects/us-influencer-outreach/input/<any .csv file>
Output: projects/us-influencer-outreach/output/classified.csv
"""

import glob
import json
import os
import sys

import pandas as pd

from scripts.ai import ask_claude
from scripts.utils import save_csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SKIP_FROM_CONTEXT = {"about"}

CLASSIFICATION_PROMPT = """You are classifying US sales influencers for outreach by Firmable, an Australian B2B sales intelligence platform expanding to the US market.

Classify this person across three dimensions:

--- OUTREACH BUCKETS (multi-label, at least one must be true) ---
product_feedback: Can give informed feedback on a US sales intelligence product.
  Signals: VP Sales, CRO, Head of Sales, RevOps, Sales Ops, Sales Director, experience at sales tech companies (ZoomInfo, Outreach, Salesloft, Gong, Apollo, Cognism, 6sense, etc.)

warm_intro: Has a broad professional network and can open doors to potential US customers.
  Signals: Advisor roles, fractional CRO/exec, sales consultant, partner at advisory firm, multiple board/advisor seats, founder/CEO with cross-company network breadth

influencer: Has a meaningful audience in the sales or revenue community.
  Signals: LinkedIn followers above 5,000, sales coach or trainer, speaker, author, podcast host, content creator with SDR/RevOps/GTM audience. If is_creator or is_influencer is True, weight this heavily.

--- SENIORITY (pick one) ---
Choose from: C-Suite, VP, Director, Manager, Individual Contributor, Other
Base this on their current title and role scope, not just title keywords.
- C-Suite: CEO, CRO, CMO, COO, CPO, President, or equivalent
- VP: Vice President or Head of [function]
- Director: Director of [function]
- Manager: Manager, Team Lead, or similar people-manager below director
- Individual Contributor: SDR, AE, BDR, Specialist, Associate, or similar
- Other: Coach, Trainer, Advisor, Consultant, Creator, Investor — roles outside a typical org chart

--- PERSON TYPE (pick the best fit, but don't be limited to these) ---
Suggested types (use your judgement, add new types if needed):
- Sales Leader (Active Org): Currently leading or managing a sales team inside a company
- GTM/RevOps Leader: Technical GTM, revenue operations, sales enablement, or go-to-market strategy role
- Business Owner / Founder: Runs their own company or is the primary owner/founder
- Sales Coach / Trainer: Primary focus is coaching, training, or developing sales professionals
- Fractional Executive / Advisor: Consulting or advising multiple companies, no single employer
- Content Creator / Influencer: Primary activity is content, community, or audience building
- Venture / Investor: VC, angel, or investment-focused role

Return ONLY valid JSON with no markdown formatting:
{{"product_feedback": true or false, "warm_intro": true or false, "influencer": true or false, "seniority": "...", "person_type": "...", "reasoning": "1-2 sentence explanation covering all three dimensions"}}

Person data:
{context}"""

BUCKET_LABELS = {
    "product_feedback": "Product Feedback",
    "warm_intro": "Warm Intro",
    "influencer": "Influencer",
}

OUTPUT_COLS_FIRST = [
    "full_name", "buckets", "seniority", "person_type",
    "headline", "current_title", "current_company",
    "followers", "location", "linkedin_url",
]


def load_input_csv(input_dir: str) -> pd.DataFrame:
    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
    if not csv_files:
        print(f"No CSV files found in {input_dir}")
        sys.exit(1)
    path = csv_files[0]
    print(f"Loading: {path}")
    df = pd.read_csv(path, encoding="latin-1")
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def build_context(row: pd.Series) -> str:
    parts = []
    for col, val in row.items():
        if col in SKIP_FROM_CONTEXT:
            continue
        if pd.notna(val) and str(val).strip():
            label = col.replace("_", " ").title()
            parts.append(f"{label}: {val}")
    return "\n".join(parts)


def classify_person(context: str) -> dict:
    prompt = CLASSIFICATION_PROMPT.format(context=context)
    raw = ask_claude(prompt).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def get_display_name(row: pd.Series) -> str:
    for col in ("full_name", "name", "first_name"):
        if col in row.index and pd.notna(row[col]):
            return str(row[col])
    return "Unknown"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_input_csv(INPUT_DIR)
    print(f"{len(df)} people to classify\n")

    classifications = []
    for i, (_, row) in enumerate(df.iterrows()):
        name = get_display_name(row)
        context = build_context(row)
        try:
            result = classify_person(context)
            pf = bool(result.get("product_feedback", False))
            wi = bool(result.get("warm_intro", False))
            inf = bool(result.get("influencer", False))
            seniority = result.get("seniority", "Other")
            person_type = result.get("person_type", "Other")
            reasoning = result.get("reasoning", "")
            bucket_list = [BUCKET_LABELS[b] for b, v in [("product_feedback", pf), ("warm_intro", wi), ("influencer", inf)] if v]
            buckets = ", ".join(bucket_list) if bucket_list else "None"
            print(f"  [{i+1}/{len(df)}] {name}: [{buckets}] | {seniority} | {person_type}")
        except Exception as e:
            print(f"  [{i+1}/{len(df)}] {name}: error — {e}")
            pf, wi, inf = False, False, True
            seniority, person_type, reasoning = "Other", "Other", f"Classification error: {e}"
            buckets = "Influencer"
        classifications.append({
            "buckets": buckets,
            "seniority": seniority,
            "person_type": person_type,
            "product_feedback": pf,
            "warm_intro": wi,
            "influencer": inf,
            "classification_reasoning": reasoning,
        })

    cls_df = pd.DataFrame(classifications)
    for col in cls_df.columns:
        df[col] = cls_df[col].values

    # Drop 'about' from output
    df = df.drop(columns=["about"], errors="ignore")

    # Reorder: classification columns first, then everything else
    first_cols = [c for c in OUTPUT_COLS_FIRST if c in df.columns]
    cls_cols = ["buckets", "seniority", "person_type", "product_feedback", "warm_intro", "influencer", "classification_reasoning"]
    remaining = [c for c in df.columns if c not in first_cols and c not in cls_cols]
    ordered = first_cols + [c for c in cls_cols if c not in first_cols] + remaining
    df = df[[c for c in ordered if c in df.columns]]

    output_path = os.path.join(OUTPUT_DIR, "classified.csv")
    save_csv(df, output_path)

    pf_count = sum(c["product_feedback"] for c in classifications)
    wi_count = sum(c["warm_intro"] for c in classifications)
    inf_count = sum(c["influencer"] for c in classifications)
    print(f"\nDone. {len(df)} classified -> {output_path}")
    print(f"  Product Feedback: {pf_count}  |  Warm Intro: {wi_count}  |  Influencer: {inf_count}")


if __name__ == "__main__":
    main()
