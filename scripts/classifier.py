import json
import os
import re
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).parent.parent
_ICP_CRITERIA_PATH = _REPO_ROOT / "knowledge" / "icp-definition.md"
_PERSONA_MESSAGING_PATH = _REPO_ROOT / "knowledge" / "persona-definitions.md"
_CLASSIFIER_SKILL_PATH = _REPO_ROOT / "knowledge" / "Contact-Classifier-Skill.md"

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in .env")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _fetch_website_text(url: str) -> str:
    """Fetch a company homepage and return the first ~1500 chars of visible text."""
    if not url:
        return ""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Strip HTML tags and collapse whitespace
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1500]
    except Exception:
        return ""


def _build_system_prompt() -> str:
    icp_criteria = _ICP_CRITERIA_PATH.read_text()
    persona_messaging = _PERSONA_MESSAGING_PATH.read_text()
    classifier_skill = _CLASSIFIER_SKILL_PATH.read_text()
    return f"""You are an ICP classifier for Firmable, an Australian B2B sales intelligence platform.

Your job is to assess whether a contact is a good ICP match for Firmable based on their role and company context.

Use the following knowledge to guide your classification:

## ICP Criteria
{icp_criteria}

## Buyer Personas
{persona_messaging}

## Classifier Rules (authoritative — follow these exactly)
{classifier_skill}

## Additional Classification Rules

**Two conditions must BOTH be true for ICP YES:**

**Condition 1 — Seniority / buying power (manager or above):**
The person must be a manager, leader, or decision-maker with budget authority or strong purchasing influence. Individual contributors do NOT qualify.

ICP YES seniority — titles that qualify:
- Any "Head of", "Director", "VP", "C-suite", "GM", "Partner" title
- Founder / Co-Founder / CEO / MD / Managing Director
- Operations or enablement roles at manager level that influence tool/tech decisions (e.g. Business Operations Manager, Revenue Operations Manager)
- "Lead" where context confirms team leadership (not just a job title prefix)
- BDR/SDR/Sales Development Manager
- "[Geography/Country/Region] Lead", "Market Lead", "Country Lead", "[Region] Lead" — geographic market ownership with BD/expansion mandate (equivalent to a regional director)

ICP NO seniority — individual contributors, excluded regardless of industry:
- Account Executive, Senior AE, Mid-Market AE, Enterprise AE
- Sales Representative, Sales Development Representative, BDR, SDR (without "Manager")
- Recruitment Consultant, Senior/Principal Consultant (billing IC roles without team management)
- Account Manager, Customer Success Manager (individual book of business)
- Specialist, Coordinator, Associate, Analyst, Ambassador

**"Business Development Manager" ambiguity rule:**
"Business Development Manager" (and variants: Senior BDM, Business Development Executive) is an individual contributor title in ANZ by default — equivalent to a senior AE with a territory. To qualify as ICP Yes:
- The headline or summary MUST contain an explicit signal of managing people: "leading a team", "managing a team of X", "player-coach", "managing SDRs/BDRs", "sales leader managing X reps", or similar phrasing.
- If no such signal is present in the headline/summary → classify as No.
- Exception: "Head of Business Development", "BD Director", "VP Business Development" qualify without needing headline evidence.

**Multiple-roles rule:**
When the title is Co-Founder, Founder, or Owner, check the headline/summary for a secondary active professional role. If the headline reveals a current role at a different context (e.g., "Business Development Lead at X" in the headline) that is manager-level with a B2B mandate, use that secondary role as the primary seniority signal — even if the co-founder/owner role itself is at a non-B2B entity.

**Condition 2 — Company has a B2B interaction:**
The company sells to, partners with, recruits for, sponsors, or fundraises from other businesses in any capacity. Interpret this loosely — if there is any plausible B2B commercial interaction, the company qualifies. Do NOT use company size or employee count as a signal; that data will come from the Firmable API separately.

ICP NO company signals: purely consumer-facing with zero B2B dimension (e.g. a personal blog, pure retail consumer brand, hobby organisation).

**Default when uncertain:** If the title is unambiguously manager/above AND B2B outreach is plausible, return Yes. For ambiguous titles like BDM, apply the BDM rule above before defaulting to Yes.

**When uncertain on company type:** Use the website to check for B2B signals. If still unclear after checking, lean Yes if the title qualifies.

## Output Format
Return ONLY a JSON array — no explanation, no markdown. One object per contact, in the same order as the input.
Each object must have exactly three keys:
- "icp_match": "Yes" or "No"
- "icp_reason": one concise sentence explaining why
- "confidence": "high" or "low" (low = company type is ambiguous and more context would help)"""


def _reclassify_with_website(contact: dict, website_text: str) -> dict:
    """Re-classify a single uncertain contact after fetching its website."""
    client = _get_client()
    system_prompt = _build_system_prompt()
    user_prompt = (
        f"Classify this contact. Additional context — company website content:\n{website_text}\n\n"
        f"Contact:\n{json.dumps({k: v for k, v in contact.items() if k in ('first_name', 'last_name', 'title', 'company', 'summary', 'website')}, indent=2)}"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    # Handle single object or single-element array
    if isinstance(result, list):
        result = result[0]
    return result


def classify_contacts(contacts: list[dict]) -> list[dict]:
    """
    Classify a list of contacts for Firmable ICP fit.

    Each contact dict must have at least 'title'. Optional fields:
    first_name, last_name, company, summary, website.

    Returns the same list with keys added to each dict:
    - icp_match: "Yes" or "No"
    - icp_reason: str (one sentence)
    - confidence: "high" or "low"
    """
    if not contacts:
        return contacts

    client = _get_client()
    system_prompt = _build_system_prompt()

    # Pass 1: classify all with available data
    slim_contacts = []
    for c in contacts:
        slim = {}
        for field in ("first_name", "last_name", "title", "company", "summary", "website"):
            if c.get(field):
                slim[field] = c[field]
        slim_contacts.append(slim)

    user_prompt = f"Classify these contacts:\n{json.dumps(slim_contacts, indent=2)}"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    results = json.loads(raw)

    for contact, result in zip(contacts, results):
        contact["icp_match"] = result.get("icp_match", "No")
        contact["icp_reason"] = result.get("icp_reason", "")
        contact["confidence"] = result.get("confidence", "high")

    # Pass 2: re-classify low-confidence contacts using website content
    for contact in contacts:
        if contact.get("confidence") == "low" and contact.get("website"):
            print(f"  [website fetch] {contact.get('company', contact.get('first_name', ''))} — {contact.get('website')}")
            website_text = _fetch_website_text(contact["website"])
            if website_text:
                updated = _reclassify_with_website(contact, website_text)
                contact["icp_match"] = updated.get("icp_match", contact["icp_match"])
                contact["icp_reason"] = updated.get("icp_reason", contact["icp_reason"])
                contact["confidence"] = updated.get("confidence", "high")

    return contacts


def classify_contact(contact: dict) -> dict:
    """Classify a single contact. Returns the dict with icp_match, icp_reason, confidence added."""
    return classify_contacts([contact])[0]
