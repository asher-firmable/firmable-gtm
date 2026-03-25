"""
Step 1: Find sales contacts at exhibitor companies using Firmable People Search.

Reads a companies CSV (output from 0_scrape_exhibitors.py) and for each company
makes two Firmable People Search calls (no size cap — returns all available):
  - Seniority 4 (VP/Director): returns top 5 with contact info
  - Seniority 3 (C-Suite):     returns top 2 with contact info

Within each pass, contacts are prioritised: phone+email > phone only > email only.
Contacts with neither phone nor email are excluded.

Usage:
    PYTHONPATH=. python3 projects/slack-bots/event-scraper/scripts/1_find_contacts.py \
      --input data/output/b2b_marketing_leaders_sydney.csv \
      --output data/output/contacts_b2b_marketing_leaders_sydney.csv
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path

from scripts.firmable_api import FirmableClient


SEARCH_PASSES = [
    {"seniority": 4, "cap": 5, "label": "VP/Director Sales"},
    {"seniority": 3, "cap": 2, "label": "C-Suite Sales"},
]

# Use a high size to effectively return all available results
_SEARCH_SIZE = 100

# Priority order for sorting: lower number = higher priority
_CONTACT_PRIORITY = {
    (True, True): 0,   # phone + email
    (True, False): 1,  # phone only
    (False, True): 2,  # email only
    (False, False): 3, # neither — excluded
}


def extract_work_email(person: dict) -> str:
    # API returns {"work": [{"value": "..."}], "personal": [...]}
    emails = person.get("emails", {})
    if isinstance(emails, dict):
        for entry in emails.get("work", []):
            val = entry.get("value", "")
            if val:
                return val
    return ""


def extract_phone(person: dict) -> str:
    # API returns [{"value": "+61...", "is_dnd": false}]
    for entry in person.get("phones", []):
        if not entry.get("is_dnd", True) and entry.get("value"):
            return entry["value"]
    return ""


def _linkedin_url(slug: str) -> str:
    if not slug:
        return ""
    if slug.startswith("http"):
        return slug
    return f"https://www.linkedin.com/in/{slug}"


def _contact_priority(row: dict) -> int:
    return _CONTACT_PRIORITY.get((bool(row["phone"]), bool(row["work_email"])), 3)


def _enrich_and_filter(client: FirmableClient, summaries: list[dict],
                        company_name: str, domain: str, company_id: str,
                        cap: int) -> list[dict]:
    """Enrich summaries, filter those with no contact info, sort by priority, cap."""
    # Pre-sort by API flags so we enrich best candidates first
    summaries.sort(key=lambda s: (
        0 if (s.get("has_phone") or s.get("has_mobile")) and s.get("has_email") else
        1 if (s.get("has_phone") or s.get("has_mobile")) else
        2 if s.get("has_email") else 3
    ))

    rows = []
    for summary in summaries:
        if len(rows) >= cap:
            break
        person_id = summary.get("person_id", "")
        if not person_id:
            continue
        try:
            person = client.get_person(id=person_id)
            work_email = extract_work_email(person)
            phone = extract_phone(person)

            if not work_email and not phone:
                print(f"    [skip] {person.get('name', person_id)}: no email or phone")
                continue

            rows.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "full_name": person.get("name", ""),
                "person_id": person_id,
                "position": person.get("position", summary.get("position", "")),
                "work_email": work_email,
                "phone": phone,
                "linkedin_url": _linkedin_url(person.get("linkedin", "")),
                "company_name": company_name,
                "domain": domain,
                "firmable_company_id": company_id,
            })
            contact_info = " | ".join(filter(None, [phone, work_email]))
            print(f"    {person.get('name', person_id)}: {rows[-1]['position']} [{contact_info}]")
        except Exception as e:
            print(f"    [person-error] {person_id}: {e}")

    rows.sort(key=_contact_priority)
    return rows


def find_contacts_for_company(client: FirmableClient, company: dict,
                               countries: list = None) -> list[dict]:
    if not countries:
        countries = ["AU"]
    company_id = company["firmable_company_id"]
    company_name = company["company_name"]
    domain = company["domain"]

    all_rows = []
    seen_ids = set()

    for country in countries:
        for p in SEARCH_PASSES:
            try:
                results = client.find_contacts(
                    company_id=company_id,
                    seniority=p["seniority"],
                    department=2,
                    country=country,
                    size=_SEARCH_SIZE,
                )
                summaries = [r for r in (results or []) if r.get("person_id") not in seen_ids]
                seen_ids.update(r["person_id"] for r in summaries if r.get("person_id"))
                print(f"  [{country}][{p['label']}] {len(summaries)} candidates → capping at {p['cap']}")
                rows = _enrich_and_filter(client, summaries, company_name, domain, company_id, cap=p["cap"])
                for row in rows:
                    if row["person_id"] not in {r["person_id"] for r in all_rows}:
                        all_rows.append(row)
            except Exception as e:
                print(f"  [{country}][{p['label']}] search error: {e}")

    return all_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to companies CSV")
    parser.add_argument(
        "--output",
        default=f"data/output/contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        help="Path to output contacts CSV",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, newline="", encoding="utf-8") as f:
        companies = [r for r in csv.DictReader(f) if r.get("firmable_company_id")]

    print(f"Loaded {len(companies)} companies from {input_path}")

    client = FirmableClient()

    # ── Pre-flight: fetch sales team sizes ───────────────────────────────────
    print("\nFetching sales team sizes from Firmable OS API...")
    company_sizes = {}  # firmable_company_id -> {au, nz, sea, total}
    for company in companies:
        cid = company["firmable_company_id"]
        try:
            sizes = client.get_sales_team_size(cid)
            company_sizes[cid] = sizes
            print(f"  {company['company_name']}: total={sizes['total_sales_team_size']}")
        except Exception as e:
            print(f"  [size-error] {company['company_name']}: {e}")
            company_sizes[cid] = {
                "au_sales_team_size": None,
                "nz_sales_team_size": None,
                "sea_sales_team_size": None,
                "total_sales_team_size": None,
            }

    # Print summary table
    print(f"\n{'Company':<42} {'AU':>4} {'NZ':>4} {'SEA':>5} {'Total':>6}")
    print("─" * 62)
    for company in companies:
        s = company_sizes[company["firmable_company_id"]]
        au    = "-" if s["au_sales_team_size"]    is None else str(s["au_sales_team_size"])
        nz    = "-" if s["nz_sales_team_size"]    is None else str(s["nz_sales_team_size"])
        sea   = "-" if s["sea_sales_team_size"]   is None else str(s["sea_sales_team_size"])
        total = "-" if s["total_sales_team_size"] is None else str(s["total_sales_team_size"])
        print(f"  {company['company_name']:<40} {au:>4} {nz:>4} {sea:>5} {total:>6}")

    # Prompt for threshold
    threshold_str = input("\nMinimum total_sales_team_size to include (0 = include all): ").strip()
    threshold = int(threshold_str) if threshold_str.isdigit() else 0

    if threshold > 0:
        included = [c for c in companies if (company_sizes[c["firmable_company_id"]]["total_sales_team_size"] or 0) >= threshold]
        excluded = [c for c in companies if (company_sizes[c["firmable_company_id"]]["total_sales_team_size"] or 0) < threshold]
        if excluded:
            print(f"\nSkipping {len(excluded)} companies (total_sales < {threshold}):")
            for c in excluded:
                t = company_sizes[c["firmable_company_id"]]["total_sales_team_size"]
                print(f"  {c['company_name']} (total={t})")
        companies = included

    if not companies:
        print("\nNo companies left after filtering. Aborting.")
        return

    confirm = input(f"\nFind contacts for {len(companies)} companies? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("Aborted.")
        return

    # ── Contact finding ──────────────────────────────────────────────────────
    all_rows = []

    for company in companies:
        print(f"\n{company['company_name']} ({company['firmable_company_id']})")
        rows = find_contacts_for_company(client, company)
        # Carry sales team size columns onto each contact row
        sizes = company_sizes[company["firmable_company_id"]]
        for row in rows:
            row.update(sizes)
        all_rows.extend(rows)

    if not all_rows:
        print("\nNo contacts found.")
        return

    fieldnames = [
        "first_name", "last_name", "full_name", "person_id", "position",
        "work_email", "phone", "linkedin_url", "company_name", "domain",
        "firmable_company_id",
        "au_sales_team_size", "nz_sales_team_size", "sea_sales_team_size", "total_sales_team_size",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    total = len(all_rows)
    with_both = sum(1 for r in all_rows if r["work_email"] and r["phone"])
    with_phone_only = sum(1 for r in all_rows if r["phone"] and not r["work_email"])
    with_email_only = sum(1 for r in all_rows if r["work_email"] and not r["phone"])

    print(f"\n{'='*50}")
    print(f"Total contacts:       {total}")
    print(f"  phone + email:      {with_both}")
    print(f"  phone only:         {with_phone_only}")
    print(f"  email only:         {with_email_only}")
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
