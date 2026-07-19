#!/usr/bin/env python3
"""
US Creative Ideas Campaign — Generate 3 ideas per company.
Input:  campaigns/us/creative-ideas/input/*.csv
Output: campaigns/us/creative-ideas/output/ideas_<timestamp>.csv
"""
import argparse
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

INPUT_DIR = Path("campaigns/us/creative-ideas/input")
OUTPUT_DIR = Path("campaigns/us/creative-ideas/output")
OUTPUT_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COMPETITOR_NAMES = [
    "zoominfo", "apollo", "lusha", "hunter", "cognism",
    "leadiq", "snov", "seamless", "contactout", "rocketreach",
]

CLASSIFY_SYSTEM = """\
You are a B2B market analyst specialising in US SMB companies. Classify a company \
into a vertical and identify the two main buyer personas they target — the people \
they are trying to sell to.

Verticals (pick exactly one):
Recruitment | SaaS Software | IT MSP | Construction Trade | Financial Services |
Accounting Advisory | BD Agencies | Training Bodies | Other B2B

Rules:
- Default to Other B2B if no vertical fits clearly. Never force.
- Financial Services: mortgage brokers, insurance brokers, RIAs, wealth advisors, specialty finance.
- BD Agencies: companies that build prospect lists or run outbound on behalf of other companies.
- persona_1 and persona_2 are the job titles or roles of the people this company sells to. \
  Write them as short role labels, 2-4 words max. \
  Examples: "store owners", "HR directors", "compliance officers", "IT managers", "CFOs". \
  They should be distinct but related — the two most common buyer types at this company's target accounts.\
"""

GENERATE_SYSTEM = """\
You are a senior outbound copywriter at Firmable, a B2B data platform expanding from \
Australia into the US market. Write a cold email body showing 2-3 personalised ideas \
for how Firmable can help the recipient find and reach their buyers, plus a short TLDR.

FORMATTING RULES (non-negotiable):
- Never use em dashes (—). Use commas or full stops instead.
- Never use bold markdown. Write all text plainly.
- Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, \
  seamless, empower, synergy, game-changing, pivotal.
- Never reference ANZ, APAC, or Australia in the ideas. Only in the TLDR.
- Never compare Firmable database size to ZoomInfo. Never cite connect rate percentages.
- Each idea must be exactly 1-2 SHORT sentences. No trailing clauses, no extra build-up. \
  Slot C format: Start with "Find [personas] who have stepped into a new role in the last 90 days." \
    Then add a natural reason — either as a second sentence OR folded in as a trailing clause on the same sentence. \
    Vary the structure row to row. Examples: \
      Two-sentence: "Find compliance officers who have stepped into a new role in the last 90 days. That tends to be when they start reviewing their vendor and tool relationships." \
      Trailing clause: "Find pharma executives who have stepped into a new role in the last 90 days, usually when advisory and market access decisions get revisited." \
      Trailing clause: "Find marketing directors who have stepped into a new role in the last 90 days, a natural point when they start shopping around for a new agency partner." \
    Pick whichever sounds more natural for the specific context. Mix it up row to row. \
  Slot B format: "Filter for [companies] actively using [Tool] through dual-source detection, so you are only targeting accounts where the appropriate tech stack is already present." \
    Do NOT explain what dual-source detection means. Do NOT add a second sentence. \
  Slot D format: Convey this meaning: reach the decision-maker on their direct mobile or verified email, not the main switchboard, verified every week. \
    Vary the phrasing naturally row to row. Examples: \
      "Contact them directly through direct mobile numbers or emails that are verified weekly, not the main office line or general email." \
      "Reach them on a verified direct mobile or email, not the switchboard." \
      "Get straight to the decision-maker with direct numbers and emails, verified every week." \
      "Skip the main line and reach out on a verified direct mobile or email instead." \
    One sentence only. Never repeat persona names here. Always the last idea. \
  Never say "Firmable tracks", "Firmable surfaces", "Firmable flags", "Firmable can find". \
  Frame as what the prospect does — Find, Filter for, Contact, Reach, Get to — not what Firmable does.

WHAT FIRMABLE DOES:
1. Weekly-verified direct mobile numbers and email addresses for decision-makers. Not office \
   numbers or switchboards — direct contact details for the actual person, verified each week.
2. Technographic filters using dual-source detection: website analysis plus job description \
   scanning. Stronger than tools using only one method. Finds companies using a specific tool.
3. Buying signals: job change, hiring surge, M&A, new product launch, leadership change, \
   funding, business expansion.
4. ICP filtering: industry, company size, location, sales team size, multi-location count.
5. Early customer benefit: Firmable's first US clients work directly with the data team to \
   build the exact dataset their ICP needs. Not a fixed catalogue — a collaborative build. \
   Most valuable when the ICP is niche and unlikely to be well-covered in standard databases.

SLOT FRAMEWORK:

Slot C — Person-level timing signal (use for idea_1):
  Job change: "Find [personas] who have stepped into a new role in the last 90 days. [varied closing reason]"
  Vary the closing reason naturally — see FORMATTING RULES above for examples.
  EXCEPTION: if ICP is founders/owners, use a company-level signal instead (they do not change companies).

Slot C2 — Company-level signal (use for idea_2 when Slot B does not apply):
  Pick the signal that makes sense for what the target company sells. \
  Use a natural reason — either as a second sentence OR as a trailing clause on the same sentence. \
  Vary the structure row to row. Do NOT always use the same two-sentence pattern. \
  M&A or restructuring examples: \
    "Find companies that have recently gone through M&A or a restructuring, which tends to shake up advisory and comms relationships." \
    "Find companies that have recently gone through M&A or a restructuring. Those tend to be the accounts reviewing their advisory relationships." \
  New c-suite appointment examples: \
    "Find companies that have recently appointed a new [CEO/CFO/CCO], usually when vendor and partner decisions get reset." \
    "Find companies that have recently appointed a new [CEO/CFO/CCO]. That is usually when they start evaluating their advisory partners." \
  Hiring surge examples: \
    "Filter for companies actively expanding their [compliance / investment / comms] teams, a sign that budget is moving and decisions are being made." \
    "Filter for companies actively expanding their [compliance] teams. That is usually a signal that regulatory pressure is building." \
  Funding round / headcount growth examples: \
    "Filter for companies that have recently raised a funding round or are scaling headcount, usually when they start shopping for new tools and partners." \
    "Filter for companies that have recently raised a funding round or are in active headcount growth. These are usually the accounts looking for new tools." \
  Business expansion / new locations examples: \
    "Find companies opening new locations or scaling operations, usually when facilities and service vendors get reviewed." \
    "Find companies opening new locations or scaling operations. That is usually when they start reviewing their facilities vendors."

Slot B — Technographic (use for idea_2 only when a clearly relevant tool exists):
  ONLY use when the ICP is defined by a specific recognisable tool.
  Good fits: SaaS (Salesforce/HubSpot/Stripe), ecommerce (Shopify/Klaviyo), \
    IT MSPs (Microsoft 365/Azure), construction (Procore), property management (Yardi/AppFolio), \
    HR/L&D (Workday/BambooHR), recruitment (Bullhorn/JobAdder).
  DO NOT use for investment firms, PR/comms agencies, pharma advisory, compliance/risk, \
    sovereign wealth funds, or any Other B2B where no tool is obviously relevant. \
    Use Slot C2 instead.
  Format: "Filter for [companies] actively using [SpecificTool] through dual-source detection, \
    so you are only targeting accounts where the appropriate tech stack is already present."

Slot D — Direct access (always LAST, varied wording):
  Convey: reach the decision-maker on a verified direct mobile or email, not the main switchboard, \
  verified every week. Vary the phrasing — see FORMATTING RULES above for examples. \
  One sentence only. Never repeat persona names.

SLOT SELECTION:
- idea_1 and idea_2 must be genuinely different signals. If both would resolve to the same \
  underlying reason (e.g. both are "timing when [X] decisions get made"), replace one with a \
  different signal type entirely — technographic, a different company event, or a different \
  person-level trigger. Never say the same "why" twice in different words.
- Vary the order: do not always lead with the job change signal. Sometimes put the company-level \
  signal first and the person-level signal second. Mix it up across rows.
- idea_3: always Slot D (direct access), fixed wording.
- If only two ideas genuinely apply, leave idea_3 empty and use Slot D as idea_2.
- Never force a third idea.

ROUTING BY VERTICAL:
SaaS Software: C (job change), B (Salesforce/HubSpot/Stripe/Shopify — name the most relevant), D last.
IT MSP: C (job change for IT managers), B (Microsoft 365/Azure), D last.
Construction Trade: C (hiring surge), B (Procore if relevant), D last.
Financial Services — investment/wealth/sovereign: C (new CIO/allocator role), \
  C2 (hiring surge in investment team = AUM scaling), D last. Never use Slot B.
Financial Services — brokers: C (job change), B (relevant CRM if applicable), D last.
Accounting Advisory: C (M&A, new c-suite, or headcount growth — pick the one that fits \
  their advisory focus), D last. Two ideas only if B does not apply.
BD Agencies: C (job change for their ICP), B (tech stack signal for their client base), D last.
PR/Comms/Advisory (Other B2B): C (new CCO/CEO in role), \
  C2 (M&A or restructuring = when advisory relationships get reviewed), D last.
Pharma/Biotech advisory (Other B2B): C (new exec in role), \
  C2 (hiring surge in clinical or commercial function), D last.
Compliance/Risk/Legal: C (new compliance officer in role), \
  C2 (hiring surge in compliance/risk function = regulatory pressure building), D last.
Training Bodies / L&D: C (hiring surge or new HR lead), B (Workday/BambooHR if relevant), D last.
Other B2B — energy/facilities/services: C (new facilities/ops lead in role), \
  C2 (business expansion or new locations), D last.
Other B2B — general: C + whichever of B or C2 genuinely fits the ICP, D last.

BRIDGE LINE RULES:
- Format exactly: "A few ideas for how Firmable could help the [normalized_name] team get \
  more conversations with [persona_1] or [persona_2]:"
- If has_sales_team = No: "A few ideas for how Firmable could help [normalized_name] get \
  more conversations with [persona_1] or [persona_2]:"
- Must mention Firmable by name. Must use normalized_name — never a personal name.
- One sentence ending with a colon.
- Do NOT vary this structure — the format is fixed.

TLDR RULES:
- Always exactly ONE sentence. No persona names. No "Worth checking us out?". \
- If uses_competitor contains ZoomInfo (or any competitor): \
  "The Firmable platform provides the same contact data as ZoomInfo, but also includes \
  signals like these in our packages for a fraction of the price, helping you surface \
  warmer leads and drive more conversations with potential clients and partners." \
- If no competitor detected: \
  "The Firmable platform combines contact data and signals like these to help you surface \
  warmer leads and drive more conversations with potential clients and partners."

NOTE ON COMPETITORS: Do not run a separate displacement track. All companies get the same \
creative ideas treatment regardless of what tools they use. If uses_competitor is set, \
only use it to adjust the TLDR wording — the ideas themselves stay the same.\
"""


def detect_competitors(raw: str) -> str:
    if not raw or not raw.strip():
        return ""
    lower = raw.lower()
    found = [("ZoomInfo" if n == "zoominfo" else n.title()) for n in COMPETITOR_NAMES if n in lower]
    return ", ".join(found) if found else raw.strip()


def _call_with_retry(fn, retries=3, backoff=5):
    for attempt in range(retries):
        try:
            return fn()
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                raise


def classify(company_name: str, description: str) -> dict:
    resp = _call_with_retry(lambda: client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=CLASSIFY_SYSTEM,
        tools=[{
            "name": "classify_company",
            "description": "Classify the company and identify its two target buyer personas",
            "input_schema": {
                "type": "object",
                "properties": {
                    "vertical": {
                        "type": "string",
                        "enum": [
                            "Recruitment", "SaaS Software", "IT MSP", "Construction Trade",
                            "Financial Services", "Accounting Advisory", "BD Agencies",
                            "Training Bodies", "Other B2B",
                        ],
                    },
                    "persona_1": {"type": "string"},
                    "persona_2": {"type": "string"},
                },
                "required": ["vertical", "persona_1", "persona_2"],
            },
        }],
        tool_choice={"type": "tool", "name": "classify_company"},
        messages=[{"role": "user", "content": f"Company: {company_name}\nDescription: {description}"}],
    ))
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"vertical": "Other B2B", "persona_1": "", "persona_2": ""}


def generate_ideas(normalized_name: str, vertical: str, persona_1: str, persona_2: str,
                   campaign_track: str, uses_competitor: str, has_sales_team: str) -> dict:
    user_msg = json.dumps({
        "task": "Write the email body using the company context below.",
        "normalized_name": normalized_name,
        "vertical": vertical,
        "persona_1": persona_1,
        "persona_2": persona_2,
        "campaign_track": campaign_track,
        "uses_competitor": uses_competitor,
        "has_sales_team": has_sales_team,
    })
    resp = _call_with_retry(lambda: client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=700,
        system=GENERATE_SYSTEM,
        tools=[{
            "name": "write_email",
            "description": "Write bridge line, 2-3 ideas, and TLDR",
            "input_schema": {
                "type": "object",
                "properties": {
                    "bridge_line": {"type": "string"},
                    "idea_1": {"type": "string"},
                    "idea_2": {"type": "string"},
                    "idea_3": {"type": "string"},
                    "tldr": {"type": "string"},
                },
                "required": ["bridge_line", "idea_1", "idea_2", "idea_3", "tldr"],
            },
        }],
        tool_choice={"type": "tool", "name": "write_email"},
        messages=[{"role": "user", "content": user_msg}],
    ))
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"bridge_line": "", "idea_1": "", "idea_2": "", "idea_3": "", "tldr": ""}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Process only first N rows")
    args = parser.parse_args()

    input_files = sorted(INPUT_DIR.glob("*.csv"))
    if not input_files:
        print("No CSV found in input/")
        return
    input_path = input_files[0]
    print(f"Reading: {input_path.name}")

    with open(input_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if args.limit:
        rows = rows[:args.limit]
    print(f"Loaded {len(rows)} rows\n")

    output_rows = []
    errors = []

    for i, row in enumerate(rows, 1):
        company_name = row.get("Company name", "").strip()
        normalized_name = row.get("Normalized Company Name (2)", company_name).strip()
        description = row.get("DESCRIPTION", "").strip()
        sales_team_raw = row.get("US_SALES_TEAM_SIZE", "0").strip() or "0"
        competitor_raw = row.get("Competitor Tools Used", "").strip()

        uses_competitor = detect_competitors(competitor_raw)
        campaign_track = "displacement" if uses_competitor else "creative_ideas"

        try:
            size = int(float(sales_team_raw))
        except (ValueError, TypeError):
            size = 0
        has_sales_team = f"Yes – {size} reps" if size >= 1 else "No"

        track_label = f"[DISPLACE: {uses_competitor}]" if uses_competitor else "[ideas]"
        print(f"  [{i:3d}/{len(rows):3d}] {company_name[:45]:<45} {track_label}")

        try:
            clf = classify(company_name, description)
        except Exception as e:
            print(f"    CLASSIFY ERROR: {e}")
            clf = {"vertical": "Other B2B", "persona_1": "", "persona_2": ""}
            errors.append((i, company_name, "classify", str(e)))
        time.sleep(0.3)

        vertical = clf.get("vertical", "Other B2B")
        persona_1 = clf.get("persona_1", "")
        persona_2 = clf.get("persona_2", "")

        try:
            ideas = generate_ideas(
                normalized_name, vertical, persona_1, persona_2,
                campaign_track, uses_competitor, has_sales_team,
            )
        except Exception as e:
            print(f"    GENERATE ERROR: {e}")
            ideas = {"bridge_line": "", "idea_1": "", "idea_2": "", "idea_3": "", "tldr": ""}
            errors.append((i, company_name, "generate", str(e)))
        time.sleep(0.3)

        output_rows.append({
            **row,
            "normalized_name": normalized_name,
            "vertical": vertical,
            "persona_1": persona_1,
            "persona_2": persona_2,
            "uses_competitor": uses_competitor,
            "campaign_track": campaign_track,
            "has_sales_team": has_sales_team,
            "bridge_line": ideas.get("bridge_line", ""),
            "idea_1": ideas.get("idea_1", ""),
            "idea_2": ideas.get("idea_2", ""),
            "idea_3": ideas.get("idea_3", ""),
            "tldr": ideas.get("tldr", ""),
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = OUTPUT_DIR / f"ideas_{timestamp}.csv"
    fieldnames = list(output_rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nOutput: {output_path}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for row_i, name, stage, msg in errors:
            print(f"  Row {row_i} ({name}) — {stage}: {msg}")
    else:
        print("No errors.")


if __name__ == "__main__":
    main()
