"""
Step 3: Generate a personalised 2-email PQS sequence per contact.

Email 1: Pain hook — references the contact's company's target market and the
         titles they prospect for; calls out APAC data gap on global tools.
Email 2: Follow-up competitor displacement — connect rate stat, customer proof point.

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/3_generate_emails.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

from scripts.ai import ask_claude

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Persona detection: map title keywords → persona label
PERSONA_MAP = {
    "sdr manager": "SDR Manager",
    "bdr manager": "SDR Manager",
    "sales development manager": "SDR Manager",
    "head of sales development": "SDR Manager",
    "revops": "RevOps",
    "revenue ops": "RevOps",
    "marketing ops": "RevOps",
    "demand generation": "RevOps",
    "vp sales": "Sales Leader",
    "vp of sales": "Sales Leader",
    "head of sales": "Sales Leader",
    "chief revenue officer": "Sales Leader",
    "cro": "Sales Leader",
    "chief sales": "Sales Leader",
    "sales director": "Sales Leader",
    "director of sales": "Sales Leader",
    "gm sales": "Sales Leader",
    "general manager": "Sales Leader",
    "ceo": "Sales Leader",
    "founder": "Sales Leader",
    "managing director": "Sales Leader",
    "md": "Sales Leader",
    "recruitment": "Recruitment Consultant",
    "talent": "Recruitment Consultant",
    "resourcing": "Recruitment Consultant",
}

PERSONA_ANGLES = {
    "SDR Manager": (
        "Their pain is connect rates and data quality. "
        "Firmable averages 22% connect rate on AU mobiles vs ~5% industry average. "
        "Mention speed to productivity — new reps get up and running in 30 minutes."
    ),
    "RevOps": (
        "Their pain is list quality, CRM hygiene, and deliverability. "
        "Position Firmable as direct data ownership — no waiting for sales to scrape ZoomInfo. "
        "Cotiss went from 30% to 85–90% contact accuracy."
    ),
    "Sales Leader": (
        "Their pain is pipeline coverage and forecast. "
        "Lead with revenue outcomes — $2M pipeline from outbound, $160K/month per SDR. "
        "APAC coverage is the differentiation angle."
    ),
    "Recruitment Consultant": (
        "Their pain is verified mobile numbers and fast BD list building. "
        "Firmable has verified AU/NZ mobiles with 22% connect rate. "
        "One credit = full profile: name, LinkedIn, mobile, email, company data."
    ),
}


def detect_persona(position: str) -> str:
    pos_lower = position.lower()
    for keyword, persona in PERSONA_MAP.items():
        if keyword in pos_lower:
            return persona
    return "Sales Leader"  # default


def generate_emails(
    first_name: str,
    account_name: str,
    position: str,
    target_market: str,
    target_titles: str,
    industry: str,
    contact_index: int = 0,
) -> tuple[str, str, str]:
    """Generate subject_1, body_1, body_2 for a contact. No subject_2 — follow-up threads as Re:."""
    persona = detect_persona(position)
    persona_angle = PERSONA_ANGLES.get(persona, PERSONA_ANGLES["Sales Leader"])

    # Cycle opener angles so the batch doesn't all start the same way
    OPENER_ANGLES = [
        "QUESTION: Open with a specific pain-related question to the contact based on their role and who they prospect.",
        "OBSERVATION: 'Teams in [their space] prospecting [target title] in SG run into the same data gap...' — lead with a pattern you've seen.",
        "CHALLENGE: Lead directly with the data problem. Apollo/ZoomInfo SG accuracy sits around 30% — state the problem bluntly before offering anything.",
        "PERSONA PAIN: Lead with this contact's specific role pain first — pipeline coverage for a Sales Leader, list quality for RevOps, BD speed for a Recruitment MD. No preamble.",
        "DIRECT OFFER: Skip the buildup. Open by telling them exactly what Firmable can find for their specific target titles in SG.",
    ]
    assigned_angle = OPENER_ANGLES[contact_index % len(OPENER_ANGLES)]

    prompt = f"""You are writing two cold emails on behalf of Firmable — an APAC-focused B2B contact data platform.

CONTACT:
- First name: {first_name}
- Company: {account_name}
- Title: {position}
- Their target market: {target_market or "B2B companies"}
- Titles they likely prospect for: {target_titles or "decision-makers"}
- Industry: {industry or "B2B"}

PERSONA CONTEXT:
{persona_angle}

FIRMABLE KEY STATS:
- 25M+ APAC contacts, 3M+ companies (strong SG/SEA coverage)
- 22% connect rate on local mobiles (vs ~5% industry average)
- 85–90% contact accuracy in APAC (vs ~30% on Apollo/ZoomInfo)
- Cotiss doubled call connects within weeks of switching
- $2M pipeline from outbound (customer G2 review)
- SG DNC Registry compliance built in

SUBJECT LINE RULES:
- Max 7 words. 4–5 words is ideal.
- Do NOT use "Finding X in APAC" — vary the format.
- Options: question / plain observation / stat-hook / soft challenge
- Examples: "SG contact coverage, {first_name}?", "Quick question on your SG lists",
  "Your team's APAC data gap", "22% vs 5% connect rate", "Coverage for your SG accounts"

ASSIGNED OPENER ANGLE FOR EMAIL 1:
{assigned_angle}

TASK: Write two emails.

EMAIL 1 — PQS Pain Hook:
- Use the ASSIGNED OPENER ANGLE above — do not deviate from it
- Connect to the pain: finding verified SG/APAC contacts for their target roles is a known gap on global tools
- Introduce Firmable as APAC-native with verified work emails + local mobiles
- End with a soft CTA
- Max 80 words. Never start with "I" or "We". Problem-first, no fluff.

EMAIL 2 — Follow-Up (no subject — it threads as Re: Email 1):
- Use a DIFFERENT angle from Email 1
- One short proof point: Cotiss doubled call connects, or $2M pipeline stat
- Offer to pull a sample list for one of their target segments
- Max 80 words. Never start with "I" or "We". Short sentences.

Return ONLY valid JSON in this exact format:
{{
  "subject_1": "...",
  "body_1": "...",
  "body_2": "..."
}}"""

    try:
        raw = ask_claude(prompt).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return (
            data.get("subject_1", ""),
            data.get("body_1", ""),
            data.get("body_2", ""),
        )
    except Exception as e:
        print(f"  [WARN] Email generation failed for {first_name} at {account_name}: {e}", flush=True)
        return "", "", ""


def run():
    input_path = OUTPUT_DIR / "contacts_researched.csv"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run 2_research.py first.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(input_path)
    if df.empty:
        print("No contacts to generate emails for.")
        df.to_csv(OUTPUT_DIR / "emails.csv", index=False)
        return

    print(f"Generating 2-email sequences for {len(df)} contacts...")

    subjects_1, bodies_1, bodies_2 = [], [], []

    for contact_idx, (_, row) in enumerate(df.iterrows()):
        first_name = str(row.get("first_name", "") or "")
        account_name = str(row.get("account_name", "") or "")
        position = str(row.get("position", "") or "")
        target_market = str(row.get("target_market", "") or "")
        target_titles = str(row.get("target_titles", "") or "")
        industry = str(row.get("company_industry", "") or "")

        print(f"[{contact_idx+1}/{len(df)}] {first_name} {row.get('last_name', '')} @ {account_name}", flush=True)

        s1, b1, b2 = generate_emails(first_name, account_name, position, target_market, target_titles, industry, contact_index=contact_idx)
        subjects_1.append(s1)
        bodies_1.append(b1)
        bodies_2.append(b2)

    df["subject_1"] = subjects_1
    df["body_1"] = bodies_1
    df["body_2"] = bodies_2

    output_path = OUTPUT_DIR / "emails.csv"
    df.to_csv(output_path, index=False)
    print(f"\nDone. {len(df)} rows written to {output_path}")


if __name__ == "__main__":
    run()
