"""
Black Hat US 2026 — generate the 2-email sequence per contact.

Reads the output of 1_classify_use_case.py (newest 1_classified_*.csv in
output/) and generates, per contact, an LLM-written 2-email sequence:

  Email 1 (send Day 0): hook built off the user's 3 source angles (Cut
  Through the Noise / David vs Goliath / What Happens After), personalized
  with that company's example_detections. Makes explicit that this signal
  is backend/infrastructure-level — not visible on their website or in a
  job posting.

  Email 2 (send +3-5 days, a reply in the same thread as Email 1 — no
  separate subject line): "how we actually get this" — OSINT explanation,
  one legitimacy line, booth ask reinforced. P.S. line only: 50% more
  phone/mobile coverage than major B2B databases (US-specific claim, valid
  for this US audience). Does NOT use the 22% connect-rate stat.

Does NOT use knowledge/messaging-frameworks.md or persona-definitions.md —
per explicit user direction, copy is built from the 3 supplied angles only.

The LLM writes each email with inline spintax ({option1|option2|...}) for wording
variety, then resolve_spintax() immediately picks one option per block at random —
the CSV that gets written out is clean, final text with no visible spintax markup,
ready to paste straight into SmartLead.

Run:
  PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/2_generate_copy.py [--limit N]
"""

import argparse
import glob
import json
import os
import random
import re
import sys
from typing import Optional

import pandas as pd

from scripts.ai import ask_claude
from scripts.utils import ensure_dirs, save_csv, timestamp

CAMPAIGN_DIR = "campaigns/us/events-outbound/blackhat-us-2026"
OUTPUT_DIR = f"{CAMPAIGN_DIR}/output"

SOURCE_ANGLES = """
Angle 1: What happens after the booth
Subject: The booth ends Thursday. Outbound doesn't.
Hey {{firstname}}, exhibiting at Black Hat gets you visibility for a few days, but after the event, the daily prospecting grind continues.
You can keep doing the typical cold email or cold outreach and hope someone bites, or work with Firmable, which gives you OSINT data telling you which prospects are companies with actual exposure or infrastructure risk reports. Instead of another generic outreach, your team is reaching out already knowing something real about that company's environment.
As an added note, we give you 50% more phone number coverage than the major B2B contact databases out there.
My team and I will actually be at the show. Mind if I drop by your booth to share more?

Angle 2: David vs Goliath
Subject: Cisco has the budget. You have the edge.
Hey {{firstname}}, Red Hat, Cisco, AWS, Microsoft, they'll have the biggest booths at Black Hat. You might not have the same budget as them, but here's how you get an edge instead.
Firmable gives you OSINT signals, exposure data, breach history, infrastructure risk, layered right into your prospecting, so you know which companies might need you.
On top of that, we give you emails and phone numbers for the CIOs and decision makers you're targeting, with 50% more phone coverage than the big vendors.
My team and I will be at the show. Mind if I drop by your booth to share more?

Angle 3: What happens after?
Subject: What's after Black Hat?
Hey {{firstname}}, once Black Hat wraps, you'll have a list of attendees. Any B2B sales intelligence platform can enrich that list with an email and phone number.
Firmable takes it one step further, giving you OSINT data on the companies themselves, exposure signals, breach history, infrastructure risk, so you can reach out with details that actually matter.
On top of that, we give you 50% more phone coverage than the major contact databases.
I'll be there at the show. Mind if I drop by your booth to share more?
""".strip()

HARD_RULES = """
- Max ~100 words per email body.
- Exactly one CTA per email (the booth-visit ask).
- Never open with "I" or "We".
- No filler/hype words: leverage, synergy, best-in-class, industry-leading, cutting-edge.
- US English spelling.
- Personalize with the contact's first name and, where natural, their company name.
""".strip()

SPINTAX_INSTRUCTIONS = """
Write using standard spintax notation so each send is textually unique: wrap any phrase, greeting,
transition, or sentence structure that could reasonably vary in SINGLE curly braces with
pipe-separated options — exactly this format: {Hey|Hi|Hello there}. Use single braces only, every
time, with no exceptions and no double-brace variants. Do not use spintax around the contact's
actual name or company name (those are already fixed per-contact, not templated).
Include at least 15 distinct spintax blocks combined across Email 1 and Email 2 (aim for 7-8+ in
each). Options within a block must be genuinely different phrasings or sentence structures, not
just single-word synonyms — vary word choice AND structure. Good candidates: the greeting, the
opening line, sentence connectors, how the tech names are introduced, the booth-visit CTA phrasing,
and the P.S. lead-in.
Every option inside the same block MUST keep the same grammatical number and tense as every other
option in that block (e.g. if one option is singular, all options in that block must be singular)
so the sentence reads correctly no matter which option gets picked — a spintax block is only valid
if every option can drop into the surrounding fixed sentence and still be grammatically correct.
Always refer to the contact in second person ("you"/"your team") — never refer to them by name in
the third person (e.g. never write "show Jordan's team", write "show your team" instead).
Example of correct format: "{Hey|Hi} Jordan, {here's the thing|worth knowing}: ..."
""".strip()


def find_col(df: pd.DataFrame, candidates: list) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


IC_TITLE_KEYWORDS = [
    "account executive", " ae ", "sales rep", "sales representative",
    "sdr", "bdr", "business development rep", "business development representative",
    "sales development rep",
]

LEADER_TITLE_KEYWORDS = [
    "manager", "director", "vp", "vice president", "head of", "chief",
    "founder", "co-founder", "president", "cro", "ceo", "coo", "managing director",
]


def classify_seniority(title: str) -> str:
    """Return 'ic', 'leader', or 'uncertain' based on job title keywords."""
    t = f" {title.lower()} "
    for kw in IC_TITLE_KEYWORDS:
        if kw in t:
            return "ic"
    for kw in LEADER_TITLE_KEYWORDS:
        if kw in t:
            return "leader"
    return "uncertain"


SENIORITY_GUIDANCE = {
    "ic": (
        "This contact is an individual-contributor seller (e.g. Account Executive, SDR/BDR). "
        "Speak to THEM directly — their own prospecting, prepping for their own calls, walking "
        "into their own meetings already armed with account context. Do not say 'your team'."
    ),
    "leader": (
        "This contact manages a sales team (e.g. Sales Manager, VP, Head of Sales). Speak to "
        "what their TEAM could do — their account executives, their SDRs/reps — before a call "
        "or meeting. Use language like 'your team' or 'your reps', not 'you personally'."
    ),
    "uncertain": (
        "Seniority is unclear from the title. Keep phrasing neutral — reference 'your team' in "
        "a way that reads fine whether this person is an IC or a manager."
    ),
}


def load_classified() -> pd.DataFrame:
    files = glob.glob(f"{OUTPUT_DIR}/1_classified_*.csv")
    if not files:
        print(f"No classified file found in {OUTPUT_DIR}/. Run 1_classify_use_case.py first.")
        sys.exit(1)
    input_path = sorted(files)[-1]
    print(f"Loading {input_path}")
    df = pd.read_csv(input_path)
    print(f"  {len(df)} rows")
    return df


SPINTAX_BLOCK_RE = re.compile(r"\{([^{}]+)\}")


def resolve_spintax(text: str) -> str:
    """Randomly resolve {opt1|opt2|...} spintax blocks to a single option, so the
    final copy is clean, plain text ready to paste straight into SmartLead."""
    if not text:
        return text

    def pick(match):
        options = match.group(1).split("|")
        return random.choice(options).strip()

    prev = None
    while prev != text:
        prev = text
        text = SPINTAX_BLOCK_RE.sub(pick, text)
    return re.sub(r" {2,}", " ", text)


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


ANGLE_LABELS = [
    "Angle 1: What happens after the booth",
    "Angle 2: David vs Goliath",
    "Angle 3: What happens after?",
]


def generate_emails(first_name: str, company_name: str, buyer: str, example_detections: str, title: str = "", angle_index: int = 0) -> dict:
    empty = {"email_1_subject": "", "email_1_body": "", "email_2_body": ""}

    if not example_detections:
        print(f"  [SKIP] No example_detections for {company_name} — needs classification first")
        return empty

    seniority = classify_seniority(title)
    seniority_note = SENIORITY_GUIDANCE[seniority]
    assigned_angle = ANGLE_LABELS[angle_index % len(ANGLE_LABELS)]

    prompt = f"""You are writing a 2-email cold outreach sequence for a Firmable sales rep attending Black Hat US 2026, targeting exhibitor/sponsor companies to book booth meetings.

Contact: {first_name} ({title or "title unknown"}) at {company_name} (a vendor selling to: {buyer})
Technologies Firmable can show this company are running at their target prospects: {example_detections}

Seniority framing for this contact: {seniority_note}

Below are three example angles the rep already uses — this is the template for the game being played here: the rep is targeting people who will DEFINITELY be exhibiting at Black Hat, so calling out "Black Hat" by name (not just "the show"), the booth, and the event context is the whole point, not incidental. Use them as style/tone reference — do NOT copy them verbatim.

For THIS contact, anchor specifically on: {assigned_angle}. Rotating the anchor angle across contacts is intentional — use only this one, do not blend in the other two. Swap in the specific technologies above wherever the original mentions generic tech names or "exposure/infrastructure risk."

{SOURCE_ANGLES}

Write:

EMAIL 1 (send today, has its own subject line): Anchor on ONE of the three angles above. Say "Black Hat" explicitly at least once (not only "the show"). Personalize using the specific technologies listed above — name 2-3 of them naturally. Make it explicit that this is backend/infrastructure-level signal: something NOT visible on a company's public website and NOT something you'd find in a job posting, unlike what most tools surface. Phrase any capability as an offer/suggestion ("we could show you...", "happy to show you...") rather than a flat assertion ("you can see..."). Apply the seniority framing above. End with the booth-visit ask, referencing that the rep will be at the show.

EMAIL 2 (send in 3-5 days, still before the show — this is a reply in the SAME email thread as Email 1, so it does NOT get its own subject line, just a body): Explain HOW Firmable actually gets this data. Use the term OSINT (open-source intelligence) explicitly. Make the point that Firmable looks into OSINT data and surfaces the platforms and technographics that are typically NOT found in job postings or front-end code — that's the gap other tools miss. Add one short line on legitimacy (publicly observable signals, nothing accessed via login or breach). Reinforce the booth ask. End with a P.S. line only (not in the main body) mentioning Firmable has 50% more phone/mobile coverage than major B2B databases — keep this as a by-the-way, not the main pitch. Do not mention any connect-rate percentage stat.

{SPINTAX_INSTRUCTIONS}

Hard rules for both emails:
{HARD_RULES}
- Never use the phrase "behind a firewall" or "behind a paywall" (or any spintax variant of them) anywhere in either email, including the subject line — say the signal is "not found in job postings or front-end code" instead.
- Do not invent or include a sign-off name (no "Cheers, [name]" / "Best, [name]" etc.) — sender identity is added separately at send time. End each email body on the CTA question itself (Email 2 ends on the P.S. line instead).
- The reference angles use the literal placeholder "{{{{firstname}}}}" — this is a token from the ORIGINAL templates only. In your output, always write the contact's actual first name ("{first_name}") directly. Never output the literal string "{{{{firstname}}}}" — that is not a spintax block (it has no pipe) and must not appear in your answer.

Return ONLY a JSON object, no markdown, no explanation:
{{
  "email_1_subject": "...",
  "email_1_body": "...",
  "email_2_body": "... (include the P.S. line at the end, prefixed 'P.S.')"
}}"""

    try:
        raw = ask_claude(prompt)
        result = parse_json_response(raw)
        return {
            "email_1_subject": resolve_spintax(result.get("email_1_subject", "")),
            "email_1_body": resolve_spintax(result.get("email_1_body", "")),
            "email_2_body": resolve_spintax(result.get("email_2_body", "")),
        }
    except Exception as e:
        print(f"  [WARN] Copy generation failed for {company_name}: {e}")
        return empty


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only generate copy for the first N contacts (for sample-batch review)")
    args = parser.parse_args()

    ensure_dirs(OUTPUT_DIR)
    df = load_classified()

    first_name_col = find_col(df, ["final_first_name", "first_name", "contact_first_name", "firstname"])
    last_name_col = find_col(df, ["last_name", "contact_last_name", "lastname"])
    company_col = find_col(df, ["company_name", "company", "account_name"])
    email_col = find_col(df, ["primary_work_email", "email", "contact_email", "email_address"])
    title_col = find_col(df, ["position", "title", "job_title", "contact_title"])

    missing = [n for n, c in [("first_name", first_name_col), ("company_name", company_col), ("email", email_col)] if c is None]
    if missing:
        print(f"Could not find required columns: {missing}. Available: {list(df.columns)}")
        sys.exit(1)

    if args.limit:
        df = df.head(args.limit)
        print(f"Sample mode: generating copy for first {args.limit} contacts only")

    rows = []
    generated_count = 0
    for i, row in enumerate(df.itertuples(index=False), 1):
        first_name = str(getattr(row, first_name_col, "") or "").strip()
        last_name = str(getattr(row, last_name_col, "") or "").strip() if last_name_col else ""
        company_name = str(getattr(row, company_col, "") or "").strip()
        email = str(getattr(row, email_col, "") or "").strip()
        title = str(getattr(row, title_col, "") or "").strip() if title_col else ""
        buyer = str(getattr(row, "buyer", "") or "").strip()
        example_detections = str(getattr(row, "example_detections", "") or "").strip()
        primary_use_case_name = str(getattr(row, "primary_use_case_name", "") or "").strip()

        print(f"[{i}/{len(df)}] {first_name} {last_name} @ {company_name} ({classify_seniority(title)})")
        emails = generate_emails(first_name, company_name, buyer, example_detections, title, angle_index=i - 1)

        generated = bool(emails["email_1_body"])
        if generated:
            generated_count += 1

        rows.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "title": title,
            "company_name": company_name,
            "primary_use_case": primary_use_case_name,
            "example_detections": example_detections,
            "needs_enrichment": not generated,
            **emails,
        })

    out_df = pd.DataFrame(rows)
    out_path = os.path.join(OUTPUT_DIR, f"2_copy_{timestamp()}.csv")
    save_csv(out_df, out_path)

    print(f"\nOutput: {out_path}")
    print(f"  Total contacts:   {len(out_df)}")
    print(f"  Copy generated:   {generated_count}")
    print(f"  Needs enrichment: {len(out_df) - generated_count} (missing example_detections — check classification step)")


if __name__ == "__main__":
    main()
