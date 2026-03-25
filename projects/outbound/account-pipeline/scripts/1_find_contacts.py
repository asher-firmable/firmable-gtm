"""
Step 1: Find decision-maker contacts at each account using Firmable.

Searches General Management (dept 1) and Sales (dept 2) departments.
Keeps contacts with seniority codes 1–4 (C-Suite, VP, Director, Manager) that have a work email.

Prompts for country selection interactively, or accepts --countries AU,NZ on the CLI.

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/1_find_contacts.py
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/1_find_contacts.py --countries AU,NZ
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from scripts.firmable_api import FirmableClient

# Delay between Firmable API calls to avoid 429 rate limiting
API_CALL_DELAY = 0.5

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Seniority keywords to keep (from get_person() seniority text field)
KEEP_SENIORITY_KEYWORDS = [
    "c-suite", "c-level", "vp", "vice president", "director",
    "head of", "manager", "chief", "partner", "founder",
    "managing director", "general manager", "president",
]
EXCLUDE_SENIORITY_KEYWORDS = [
    "individual contributor", "intern", "entry level", "junior",
    "associate", "coordinator", "analyst", "specialist",
]

# Departments to search: 1=General Management, 2=Sales
DEPARTMENTS = [1, 2]

# Seniority codes to request from Firmable API
# 1=Board/Director, 2=Owner/Founder, 3=C-Suite, 4=VP/Director, 5=Manager
SENIORITY_CODES = [1, 2, 3, 4, 5]

COUNTRY_OPTIONS = [
    ("AU", ["AU"]),
    ("NZ", ["NZ"]),
    ("SG", ["SG"]),
    ("AU, NZ", ["AU", "NZ"]),
    ("AU, NZ, SG", ["AU", "NZ", "SG"]),
    ("All APAC  (AU, NZ, SG, MY, HK, PH, ID)", ["AU", "NZ", "SG", "MY", "HK", "PH", "ID"]),
    ("Custom  (enter your own codes, e.g. AU,NZ,SG)", None),
]


def prompt_countries() -> list[str]:
    """Interactive country selection. Returns a list of ISO country codes."""
    print("\nWhich countries should we search for contacts?")
    for i, (label, _) in enumerate(COUNTRY_OPTIONS, 1):
        print(f"  {i}. {label}")
    print()

    while True:
        raw = input("Choice [1-7]: ").strip()
        try:
            choice = int(raw)
        except ValueError:
            print("  Enter a number between 1 and 7.")
            continue

        if not 1 <= choice <= len(COUNTRY_OPTIONS):
            print(f"  Enter a number between 1 and {len(COUNTRY_OPTIONS)}.")
            continue

        _, codes = COUNTRY_OPTIONS[choice - 1]

        if codes is None:
            # Custom entry
            custom = input("  Enter country codes (comma-separated): ").strip()
            codes = [c.strip().upper() for c in custom.split(",") if c.strip()]
            if not codes:
                print("  No codes entered, try again.")
                continue

        print(f"  -> Searching: {', '.join(codes)}\n")
        return codes


def extract_work_email(emails_field) -> str:
    """Extract the first work email from the emails field (list of dicts or raw value)."""
    if not emails_field:
        return ""
    if isinstance(emails_field, list):
        for e in emails_field:
            if isinstance(e, dict):
                return e.get("email", "") or ""
            if isinstance(e, str):
                return e
    if isinstance(emails_field, str):
        return emails_field
    return ""


def get_company_details(client: FirmableClient, company_id: str) -> dict:
    """Fetch company details by Firmable ID. Returns key fields or empty dict on error."""
    try:
        company = client.lookup_company_by_id(company_id)
        if not company:
            return {}
        return {
            "company_domain": company.get("fqdn") or company.get("domain", ""),
            "company_website": company.get("website", ""),
            "company_description": company.get("description", ""),
            "company_industry": company.get("industry", ""),
            "company_employee_count": company.get("employee_count", ""),
        }
    except Exception as e:
        print(f"  [WARN] Could not fetch company {company_id}: {e}", flush=True)
        return {}


def _is_qualifying_seniority(seniority_text: str, position: str) -> bool:
    """Return True if the person is Manager level or above."""
    combined = (seniority_text + " " + position).lower()
    for kw in EXCLUDE_SENIORITY_KEYWORDS:
        if kw in combined:
            return False
    for kw in KEEP_SENIORITY_KEYWORDS:
        if kw in combined:
            return True
    return False


def find_contacts_for_company(
    client: FirmableClient, company_id: str, countries: list[str]
) -> list[dict]:
    """Two-pass Firmable search (GM + Sales). Calls get_person() for full details.
    Filters by seniority (Manager+) and country (from get_person response). Returns deduplicated contacts."""
    seen_ids = set()
    candidates = []

    # Pass 1: collect all candidates with has_email=True across both departments.
    # Pass selectedCountry if provided — API filters server-side; no Python country filter.
    api_country = countries[0] if countries else None

    for dept in DEPARTMENTS:
        time.sleep(API_CALL_DELAY)
        try:
            results = client.find_contacts(
                company_id=company_id,
                department=dept,
                country=api_country,
                size=25,
            )
        except Exception as e:
            print(f"  [WARN] find_contacts failed for {company_id} (dept {dept}): {e}", flush=True)
            results = []

        for person in results:
            person_id = person.get("person_id") or person.get("id", "")
            if person_id in seen_ids:
                continue
            if not person.get("has_email", False):
                continue
            seen_ids.add(person_id)
            candidates.append(person)

    # Pass 2: enrich each candidate via get_person() to get seniority, country, email
    contacts = []
    for person in candidates:
        person_id = person.get("person_id") or person.get("id", "")
        time.sleep(API_CALL_DELAY)
        try:
            full = client.get_person(id=person_id)
        except Exception as e:
            print(f"  [WARN] get_person failed for {person_id}: {e}", flush=True)
            continue

        seniority_text = str(full.get("seniority") or "")
        position = str(full.get("position") or person.get("position") or "")
        if not _is_qualifying_seniority(seniority_text, position):
            continue

        contact_country = str(full.get("country") or "").upper()

        work_email = ""
        emails_field = full.get("emails", {})
        if isinstance(emails_field, dict):
            work_list = emails_field.get("work", [])
            if work_list:
                work_email = work_list[0].get("value", "")
        if not work_email:
            continue

        contacts.append({
            "person_id": person_id,
            "first_name": full.get("first_name", ""),
            "last_name": full.get("last_name", ""),
            "position": position,
            "seniority": seniority_text,
            "contact_country": contact_country,
            "work_email": work_email,
            "linkedin_url": full.get("linkedin") or full.get("linkedin_url", ""),
            "has_phone": bool(full.get("phones")),
            "has_mobile": person.get("has_mobile", False),
        })

    return contacts


def run(countries: list[str] = None):
    input_path = OUTPUT_DIR / "filtered_accounts.csv"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run 0_filter.py first.", file=sys.stderr)
        sys.exit(1)

    if countries is None:
        countries = prompt_countries()

    df = pd.read_csv(input_path)
    accounts = df.to_dict(orient="records")
    print(f"Finding contacts for {len(accounts)} accounts in: {', '.join(countries)}")

    client = FirmableClient()
    rows = []

    for i, account in enumerate(accounts):
        company_id = str(account.get("firmable_company_id", "")).strip()
        account_name = account.get("account_name") or account.get("company_name", "")
        print(f"[{i+1}/{len(accounts)}] {account_name} ({company_id})", flush=True)

        if not company_id:
            print(f"  [SKIP] No firmable_company_id", flush=True)
            continue

        company_details = get_company_details(client, company_id)
        contacts = find_contacts_for_company(client, company_id, countries)

        if not contacts:
            print(f"  [INFO] No qualifying contacts found", flush=True)
            continue

        for contact in contacts:
            row = {
                "firmable_company_id": company_id,
                "account_name": account_name,
            }
            row.update(company_details)
            row.update(contact)
            rows.append(row)

        print(f"  -> {len(contacts)} contacts", flush=True)

    output_path = OUTPUT_DIR / "contacts.csv"
    if rows:
        pd.DataFrame(rows).to_csv(output_path, index=False)
    else:
        pd.DataFrame().to_csv(output_path, index=False)

    print(f"\nDone. {len(rows)} contacts written to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--countries",
        help="Comma-separated ISO country codes to search (e.g. AU,NZ). If omitted, you will be prompted.",
    )
    args = parser.parse_args()
    countries = (
        [c.strip().upper() for c in args.countries.split(",") if c.strip()]
        if args.countries
        else None
    )
    run(countries=countries)
