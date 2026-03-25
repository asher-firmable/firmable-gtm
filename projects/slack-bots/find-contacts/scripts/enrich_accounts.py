"""
enrich_accounts.py — Batch account enrichment from a CSV of Firmable IDs.

For each account:
  1. Finds up to 2 Singapore-based Sales contacts (no seniority filter — ranked by title)
  2. Fetches APAC / SEA / ANZ sales team sizes via Firmable OS API
  3. Researches the company via Firecrawl + Claude (personas, problems, solution)

Usage:
    PYTHONPATH=. python3 find-contacts/scripts/enrich_accounts.py <input_csv>

Input CSV must have columns: "Firmable ID", "Company", "Website"
Output: find-contacts/output/<timestamp>_enriched_accounts.csv
"""

import csv
import json
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from scripts.firmable_api import FirmableClient
from scripts.ai import ask_claude

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"

SALES_DEPT = 2
COUNTRY = "SG"
MAX_CONTACTS = 2
SEARCH_SIZE = 100
WEBSITE_CHAR_LIMIT = 4000

# ICP exclusion keywords (case-insensitive substring match on padded title)
# Excludes: IC roles, indirect/channel/support roles
# Note: "sales development" is intentionally NOT excluded — VP/Head of Sales Development
# is a valid direct acquisition role. IC-level SDRs/BDRs are caught by " sdr" / " bdr".
ICP_EXCLUDE_KEYWORDS = [
    # IC / non-acquisition roles
    "account executive",
    " ae ",
    "sales rep",
    "sales representative",
    " sdr",
    " bdr",
    "account manager",
    "customer success",
    " csm",
    "brand ambassador",
    "coordinator",
    "associate",
    " analyst",
    "specialist",
    "recruitment consultant",
    # Indirect / channel / support roles
    "channel",
    "alliance",       # catches both "alliance" and "alliances"
    "partnership",    # catches "VP of Partnerships", "Partnership Executive", etc.
    "partner sales",
    "partner success",
    "partner demand",
    "sales partner",
    "pre-sales",
    "presales",
    "sales engineer",
    "solutions engineer",
    "sales enablement",
    "enablement",
]

OUTPUT_COLUMNS = [
    "firmable_id",
    "company_name",
    "website",
    "contact_name",
    "contact_title",
    "contact_email",
    "contact_phone",
    "contact_linkedin",
    "apac_sales_team_size",
    "sea_sales_team_size",
    "anz_sales_team_size",
    "target_personas",
    "problems_solved",
    "solution_approach",
]


def is_icp_title(title: str) -> bool:
    """Return True if title is ICP-valid (not an individual contributor)."""
    if not title:
        return True
    t = f" {title.lower()} "
    return not any(kw in t for kw in ICP_EXCLUDE_KEYWORDS)


def title_rank(title: str) -> int:
    """Infer seniority from job title. Lower = higher seniority.
    Ranks >= 3 are below the VP/Director/Head Of minimum and are excluded from output.
    Used because Firmable leaves seniority=None on most SG contacts."""
    if not title:
        return 99
    t = f" {title.lower()} "
    # Rank 0 — C-Suite / Founder / Owner
    if any(kw in t for kw in (" chief ", "ceo", "coo", "cro", "cso", " president",
                               "founder", "owner", "managing director", "managing partner",
                               " md ")):
        return 0
    # Rank 1 — VP / Director / GM
    if any(kw in t for kw in ("vp", "vice president", "director",
                               "general manager", " gm ")):
        return 1
    # Rank 2 — Head Of / Lead (department head level)
    if any(kw in t for kw in ("head of", "head,", " lead ")):
        return 2
    # Rank 3+ — Manager and below (does not meet minimum seniority bar)
    return 3


def contact_quality(c: dict) -> int:
    """Lower value = better contact data. Prioritise phone+email, then phone, then email."""
    has_email = c.get("has_email") or c.get("has_personal_email")
    has_phone = c.get("has_phone") and not c.get("has_dnd_phone")
    if has_email and has_phone:
        return 0
    if has_phone:
        return 1
    if has_email:
        return 2
    return 3


def fetch_contacts(firmable: FirmableClient, company_id: str) -> list:
    """Fetch all SG Sales contacts in a single call (no seniority filter).
    Ranks by title seniority then contact data quality. Returns up to MAX_CONTACTS."""
    results = []
    for attempt in range(3):
        try:
            results = firmable.find_contacts(
                company_id=company_id,
                department=SALES_DEPT,
                country=COUNTRY,
                size=SEARCH_SIZE,
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 15 * (attempt + 1)
                print(f"  [RATE LIMIT] Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                print(f"  [WARN] Contact search failed: {e}")
                break

    # 1. Exclude IC / indirect / channel roles by title keywords
    candidates = [c for c in results if is_icp_title(c.get("position", ""))]
    # 2. Enforce VP / Director / Head Of minimum (rank >= 3 = Manager and below)
    candidates = [c for c in candidates if title_rank(c.get("position", "")) <= 2]
    # 3. Exclude contacts with no contact data at all
    candidates = [c for c in candidates if contact_quality(c) < 3]
    # 4. Sort: highest seniority first, then best contact data first
    candidates.sort(key=lambda c: (title_rank(c.get("position", "")), contact_quality(c)))
    return candidates[:MAX_CONTACTS]


def enrich_contact(firmable: FirmableClient, person_id: str) -> dict:
    """Fetch full contact details for email, phone, and linkedin."""
    try:
        p = firmable.get_person(id=person_id)
        if not isinstance(p, dict):
            print(f"  [WARN] Unexpected response for {person_id}: {repr(p)[:120]}")
            return {"name": "", "title": "", "email": "", "phone": "", "linkedin": ""}

        # emails: {"work": [{"value": "..."}], "personal": [...]}
        emails_obj = p.get("emails") or {}
        if isinstance(emails_obj, dict):
            work_emails = emails_obj.get("work") or []
            other_emails = [e for k, v in emails_obj.items() if k != "work" for e in (v or [])]
        else:
            # fallback: list format {"type": ..., "email": ...}
            work_emails = [{"value": e.get("email", "")} for e in emails_obj if e.get("type") == "work"]
            other_emails = [{"value": e.get("email", "")} for e in emails_obj if e.get("type") != "work"]

        work_email = next(
            (e.get("value", "") for e in work_emails if e.get("value")),
            next((e.get("value", "") for e in other_emails if e.get("value")), ""),
        )

        # phones: [{"value": "+65...", "is_dnd": null}]
        phones = p.get("phones") or []
        phone = next(
            (ph.get("value", "") for ph in phones if not ph.get("is_dnd") and ph.get("value")),
            "",
        )
        linkedin = p.get("linkedin", "")
        if linkedin and not linkedin.startswith("http"):
            linkedin = f"https://www.linkedin.com/in/{linkedin}"

        return {
            "name": p.get("name", ""),
            "title": p.get("position", ""),
            "email": work_email,
            "phone": phone,
            "linkedin": linkedin,
        }
    except Exception as e:
        print(f"  [WARN] Could not enrich person {person_id}: {e}")
        return {"name": "", "title": "", "email": "", "phone": "", "linkedin": ""}


def get_team_sizes(firmable: FirmableClient, company_id: str) -> dict:
    """Return APAC / SEA / ANZ sales team sizes."""
    try:
        sizes = firmable.get_sales_team_size(company_id)
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        return {
            "apac_sales_team_size": sizes.get("total_sales_team_size"),
            "sea_sales_team_size": sizes.get("sea_sales_team_size"),
            "anz_sales_team_size": (au + nz) or None,
        }
    except Exception as e:
        print(f"  [WARN] Could not fetch sales team sizes: {e}")
        return {"apac_sales_team_size": None, "sea_sales_team_size": None, "anz_sales_team_size": None}


def fetch_website_markdown(url: str) -> str:
    """Scrape a URL via Firecrawl and return markdown content."""
    if not FIRECRAWL_API_KEY:
        raise ValueError("FIRECRAWL_API_KEY is not set in .env")
    if not url.startswith("http"):
        url = f"https://{url}"
    resp = requests.post(
        FIRECRAWL_SCRAPE_URL,
        headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown"]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    markdown = data.get("data", {}).get("markdown", "")
    return markdown[:WEBSITE_CHAR_LIMIT]


def research_company(website: str, company_name: str) -> dict:
    """Fetch company page via Firecrawl and ask Claude for structured B2B research."""
    empty = {"target_personas": "", "problems_solved": "", "solution_approach": ""}
    try:
        content = fetch_website_markdown(website)
        if not content:
            print(f"  [WARN] Firecrawl returned empty content for {website}")
            return empty
    except Exception as e:
        print(f"  [WARN] Firecrawl failed for {website}: {e}")
        return empty

    prompt = f"""You are a B2B sales researcher. Based on the company webpage content below for "{company_name}", answer in a B2B context only.

Return ONLY a JSON object with these three keys (no markdown, no explanation):
{{
  "target_personas": "One sentence listing the job titles/roles this company sells to (e.g. Head of Sales, VP Marketing, CFO)",
  "problems_solved": "1-2 sentences describing the business problems they solve for those personas",
  "solution_approach": "1-2 sentences on how their product or service solves those problems in a B2B context"
}}

If the company does both B2B and B2C, focus only on the B2B side.

Webpage content:
{content}"""

    try:
        raw = ask_claude(prompt)
        # Strip markdown code block if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        return {
            "target_personas": result.get("target_personas", ""),
            "problems_solved": result.get("problems_solved", ""),
            "solution_approach": result.get("solution_approach", ""),
        }
    except Exception as e:
        print(f"  [WARN] Claude extraction failed: {e}")
        return empty


def resolve_website(firmable: FirmableClient, company_id: str, csv_website: str) -> str:
    """Return website from CSV if available, else look it up via Firmable."""
    if csv_website and csv_website.strip():
        w = csv_website.strip()
        return w if w.startswith("http") else f"https://{w}"
    try:
        company = firmable.lookup_company_by_id(company_id)
        fqdn = company.get("fqdn") or company.get("website", "")
        if fqdn:
            return f"https://{fqdn}" if not fqdn.startswith("http") else fqdn
    except Exception as e:
        print(f"  [WARN] Could not resolve website from Firmable: {e}")
    return ""


def process_account(firmable: FirmableClient, row: dict) -> list:
    """Process one account row. Returns a list of output dicts (1–2 per company)."""
    company_id = row.get("Firmable ID", "").strip()
    company_name = row.get("Company", "").strip()
    csv_website = row.get("Website", "").strip()

    if not company_id:
        print(f"  [SKIP] Missing Firmable ID for row: {company_name}")
        return []

    print(f"\n[{company_name}] ({company_id})")

    # Step 1: contacts
    contacts = fetch_contacts(firmable, company_id)
    print(f"  Found {len(contacts)} contact(s)")

    # Enrich contact details
    enriched_contacts = []
    for c in contacts:
        pid = c.get("person_id")
        details = enrich_contact(firmable, pid) if pid else {}
        # Fall back to summary fields if enrichment is empty
        enriched_contacts.append({
            "contact_name": details.get("name") or c.get("name", ""),
            "contact_title": details.get("title") or c.get("position", ""),
            "contact_email": details.get("email", ""),
            "contact_phone": details.get("phone", ""),
            "contact_linkedin": details.get("linkedin", ""),
        })
        time.sleep(0.5)

    # Step 2: sales team sizes
    sizes = get_team_sizes(firmable, company_id)
    print(f"  APAC={sizes['apac_sales_team_size']} SEA={sizes['sea_sales_team_size']} ANZ={sizes['anz_sales_team_size']}")

    # Step 3: company research
    website = resolve_website(firmable, company_id, csv_website)
    if website:
        print(f"  Researching {website}")
        research = research_company(website, company_name)
    else:
        print("  [WARN] No website available — skipping research")
        research = {"target_personas": "", "problems_solved": "", "solution_approach": ""}

    # Build output rows (one per contact; at least one row per company)
    base = {
        "firmable_id": company_id,
        "company_name": company_name,
        "website": website,
        **sizes,
        **research,
    }

    if not enriched_contacts:
        return [{**base, "contact_name": "", "contact_title": "", "contact_email": "",
                 "contact_phone": "", "contact_linkedin": ""}]

    return [{**base, **c} for c in enriched_contacts]


def main():
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. python find-contacts/scripts/enrich_accounts.py <input_csv>")
        sys.exit(1)

    input_path = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{timestamp}_enriched_accounts.csv")

    firmable = FirmableClient()

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} accounts from {input_path}")

    all_output = []
    for i, row in enumerate(rows, 1):
        print(f"\n--- Account {i}/{len(rows)} ---")
        try:
            output_rows = process_account(firmable, row)
            all_output.extend(output_rows)
        except Exception as e:
            print(f"  [ERROR] Unhandled exception for row {i}: {e}")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(all_output)

    print(f"\nDone. {len(all_output)} rows written to {output_path}")


if __name__ == "__main__":
    main()
