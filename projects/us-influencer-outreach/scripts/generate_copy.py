"""
Step 2: Generate one personalised outreach email per person, written as Chester.

Email structure (3 parts, ~80-100 words total):
  Part 1 — Opener: establish connection or compliment based on person_type
  Part 2 — The ask: depends on assigned buckets (can combine multiple)
  Part 3 — Chester's context: Head of Sales ANZ at Firmable, APAC story, US expansion

Output: one 'outreach_copy' column (Subject + body) per person.

Usage:
  PYTHONPATH=. python3 projects/us-influencer-outreach/scripts/generate_copy.py

Input:  projects/us-influencer-outreach/output/classified.csv
Output: projects/us-influencer-outreach/output/with_copy.csv
"""

import os
import sys

import pandas as pd

from scripts.ai import ask_claude
from scripts.utils import load_csv, save_csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SKIP_COLS = {
    "about", "product_feedback", "warm_intro", "influencer", "buckets",
    "seniority", "person_type", "classification_reasoning", "outreach_copy",
}

COPY_PROMPT = """You are writing a short cold outreach email on behalf of Chester, formerly Head of Sales ANZ at Firmable.

The email has three parts. Keep each part to 1-2 short sentences. Total body should be under 100 words.

--- PART 1: OPENER ---
Establish a genuine connection based on who this person is. Choose the tone based on their person_type:
- Sales Leader (Active Org): "From one sales leader to another, [first name]..." — peer-to-peer tone
- Sales Coach / Trainer: "From someone who follows your work closely, [first name]..." — fan/admirer tone
- Content Creator / Influencer: "From someone who genuinely enjoys your content, [first name]..." — audience tone
- Business Owner / Founder: "From one founder building in the revenue space to another, [first name]..." — builder-to-builder tone
- Fractional Executive / Advisor: Acknowledge their cross-company perspective and GTM depth
- GTM/RevOps Leader: Peer-level acknowledgment of their operational insight
- Adapt freely if none of the above fits well — make it feel genuine, not copy-pasted

Person type: {person_type}
First name: {first_name}

--- PART 2: THE ASK ---
Based on their assigned outreach buckets, ask one clear, open question about whether they'd be willing to connect. The ask should feel like a natural next step, not a pitch.

Assigned buckets: {buckets}

Use these as guides:
- Product Feedback + Influencer: ask if they'd be open to a conversation covering both product feedback on what we're building for the US and what a potential ambassador or influencer partnership might look like
- Product Feedback + Warm Intro + Influencer: ask if they'd be open to a quick chat — could be product feedback, a potential partnership, or just getting connected to the right people
- Product Feedback only: ask if they'd be open to sharing their perspective on what a sales intelligence tool should look like for the US market
- Influencer + Warm Intro: ask if they'd be open to exploring what a partnership could look like, or connecting Chester with a few people navigating this challenge
- Warm Intro only: ask if they'd be open to connecting Chester with one or two people who might be dealing with this problem
- Influencer only: ask if they'd be open to a conversation about what a partnership or ambassador role with Firmable could look like

--- PART 3: CHESTER'S CONTEXT ---
This part has two beats. Write them as one short paragraph.

Beat A — who Chester is and what Firmable does (1-2 sentences):
Chester was Head of Sales ANZ at Firmable. Think of Firmable as the ZoomInfo, Apollo, Lusha, and Cognism alternative — built for APAC. He knows firsthand how bad sales data quality can be in ANZ, and hears the same story in the US. Firmable has helped 1,000+ customers across APAC solve this problem, and is now bringing those same capabilities to the US.

Beat B — a closing line that invites their perspective (1 sentence, always):
Assume this person has used tools like ZoomInfo, Apollo, Lusha, or Cognism before. End with something that acknowledges that, invites their honest take on what those tools get wrong or what they wish they did better, and notes that Firmable is a young team that genuinely wants to get it right.

Adapt the closing based on who they are:
- Sales Leader / C-Suite in sales: "You've no doubt used tools like these — I'd love to hear what you wish they actually got right. We're a young team and genuinely want to build something better."
- Sales Coach / Trainer: "Your clients deal with this every day — I'd love to understand what they wish these tools got right. We're a young team building from scratch."
- Content Creator: "Your audience talks about these pain points constantly — I'd love your take on what they actually need. We're a young team."
- Business Owner / Founder: "You've navigated this yourself — I'd love your honest take on what those tools miss. We're a young team."
- Fractional / Advisor: "You've seen this across more orgs than most — I'd love your take on what those vendors consistently get wrong. We're a young team."
Adapt freely if none of these fits.

--- RULES ---
- No em dashes, no bullet points, no bold text
- Do not start Part 1 with "I" or "We"
- Sound like a real person wrote it, not a template
- Keep the whole email tight — aim for around 100-120 words for the body
- Sign off as Chester (just "- Chester" at the end)
- Write a short, human subject line

Format your response exactly as:
Subject: [subject line]

[Part 1]

[Part 2]

[Part 3]

- Chester

--- PERSON INFO ---
{context}"""


def build_context(row: pd.Series) -> str:
    parts = []
    for col, val in row.items():
        if col in SKIP_COLS:
            continue
        if pd.notna(val) and str(val).strip():
            label = col.replace("_", " ").title()
            parts.append(f"{label}: {val}")
    return "\n".join(parts)


def get_first_name(row: pd.Series) -> str:
    for col in ("full_name", "name", "first_name"):
        if col in row.index and pd.notna(row[col]):
            name = str(row[col]).strip()
            # Handle nicknames like Kevin "KD" Dorsey -> Kevin
            return name.split()[0].strip('"')
    return "there"


def get_display_name(row: pd.Series) -> str:
    for col in ("full_name", "name", "first_name"):
        if col in row.index and pd.notna(row[col]):
            return str(row[col])
    return "Unknown"


def generate_copy(row: pd.Series) -> str:
    context = build_context(row)
    first_name = get_first_name(row)
    buckets = str(row.get("buckets", "Influencer"))
    person_type = str(row.get("person_type", "Other"))

    prompt = COPY_PROMPT.format(
        person_type=person_type,
        first_name=first_name,
        buckets=buckets,
        context=context,
    )
    return ask_claude(prompt).strip()


def main():
    input_path = os.path.join(OUTPUT_DIR, "classified.csv")
    if not os.path.exists(input_path):
        print(f"classified.csv not found at {input_path}")
        print("Run enrich_and_classify.py first.")
        sys.exit(1)

    df = load_csv(input_path)
    print(f"Generating copy for {len(df)} people\n")

    copies = []
    for i, (_, row) in enumerate(df.iterrows()):
        name = get_display_name(row)
        buckets = row.get("buckets", "")
        print(f"  [{i+1}/{len(df)}] {name} ({buckets})")
        try:
            copy = generate_copy(row)
        except Exception as e:
            copy = f"Error: {e}"
        copies.append(copy)

    df["outreach_copy"] = copies

    output_path = os.path.join(OUTPUT_DIR, "with_copy.csv")
    save_csv(df, output_path)
    print(f"\nDone -> {output_path}")


if __name__ == "__main__":
    main()
