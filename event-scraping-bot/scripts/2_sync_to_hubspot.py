"""
Step 2: Sync contacts to HubSpot and create a named contact list (segment).

For each contact in the input CSV:
- Upserts the contact (search by email first, phone fallback)
- Upserts the associated Company record and links the contact to it
- Creates a named static HubSpot list and adds all contacts to it
- Prints the direct HubSpot URL to the list

Usage:
    PYTHONPATH=. python3 workflows/event_outbound/2_sync_to_hubspot.py \
      --input data/output/contacts_b2b_marketing_leaders_sydney.csv

    # Or with list name pre-filled (non-interactive):
    PYTHONPATH=. python3 workflows/event_outbound/2_sync_to_hubspot.py \
      --input data/output/contacts_b2b_marketing_leaders_sydney.csv \
      --list-name "B2B Marketing Leaders Sydney 2026"
"""

import argparse
import csv
import re
import requests
from pathlib import Path

from applications.hubspot import HubSpotClient


def _normalise_phone(phone: str) -> str:
    """Strip spaces/dashes/parens to match HubSpot's stored format."""
    return re.sub(r"[\s\-\(\)]", "", phone)


# ── Property helpers ────────────────────────────────────────────────────────

def _contact_properties(row: dict) -> dict:
    props = {}
    if row.get("first_name"):
        props["firstname"] = row["first_name"]
    if row.get("last_name"):
        props["lastname"] = row["last_name"]
    if row.get("position"):
        props["jobtitle"] = row["position"]
    if row.get("work_email"):
        props["email"] = row["work_email"]
    if row.get("phone"):
        props["phone"] = row["phone"]
    if row.get("linkedin_url"):
        props["linkedin_profile"] = row["linkedin_url"]
    return props


def _company_properties(row: dict) -> dict:
    props = {}
    if row.get("company_name"):
        props["name"] = row["company_name"]
    if row.get("domain"):
        props["domain"] = row["domain"]
    return props


# ── Upsert helpers ──────────────────────────────────────────────────────────

def upsert_company(hs: HubSpotClient, row: dict):
    """Find or create a Company record. Returns hs_object_id or None on error."""
    domain = row.get("domain", "")
    if not domain:
        return None
    try:
        existing = hs.search_companies(domain)
        props = _company_properties(row)
        if existing:
            company_id = existing[0]["id"]
            hs.update_company(company_id, props)
            print(f"  [company:updated] {row['company_name']} (id={company_id})")
            return company_id
        else:
            result = hs.create_company(props)
            company_id = result["id"]
            print(f"  [company:created] {row['company_name']} (id={company_id})")
            return company_id
    except requests.HTTPError as e:
        print(f"  [company:error] {row.get('company_name')}: {e.response.status_code} {e.response.text[:120]}")
        return None


def upsert_contact(hs: HubSpotClient, row: dict):
    """Find or create a Contact record. Returns hs_object_id or None on error/skip."""
    email = row.get("work_email", "")
    phone = row.get("phone", "")
    full_name = row.get("full_name") or f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()

    if not email and not phone:
        print(f"  [contact:skip] {full_name}: no email or phone")
        return None

    props = _contact_properties(row)

    try:
        # Match by email first
        if email:
            matches = hs.search_contacts("email", email)
            if matches:
                contact_id = matches[0]["id"]
                hs.update_contact(contact_id, props)
                print(f"  [contact:updated] {full_name} (email match, id={contact_id})")
                return contact_id
            else:
                result = hs.create_contact(props)
                contact_id = result["id"]
                print(f"  [contact:created] {full_name} (id={contact_id})")
                return contact_id

        # Phone-only fallback
        matches = hs.search_contacts("phone", _normalise_phone(phone))
        if matches:
            contact_id = matches[0]["id"]
            hs.update_contact(contact_id, props)
            print(f"  [contact:updated] {full_name} (phone match, id={contact_id})")
            return contact_id
        else:
            result = hs.create_contact(props)
            contact_id = result["id"]
            print(f"  [contact:created] {full_name} (phone only, id={contact_id})")
            return contact_id

    except requests.HTTPError as e:
        print(f"  [contact:error] {full_name}: {e.response.status_code} {e.response.text[:120]}")
        return None


# ── Preview (read-only HubSpot lookups) ────────────────────────────────────

def preview(hs: HubSpotClient, contacts: list) -> dict:
    """
    Search HubSpot for each contact and company without writing anything.
    Returns a summary dict and lookup maps for use in the execute phase.
    """
    # Companies
    company_existing = {}   # domain -> existing hs_object_id
    company_new = []        # domains that will be created

    seen_domains = set()
    for row in contacts:
        domain = row.get("domain", "")
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        try:
            matches = hs.search_companies(domain)
            if matches:
                company_existing[domain] = matches[0]["id"]
            else:
                company_new.append(domain)
        except requests.HTTPError as e:
            print(f"  [preview:company:error] {domain}: {e.response.status_code}")

    # Contacts
    contact_existing = {}   # person_id -> existing hs_object_id
    contact_new = []        # person_ids that will be created
    contact_skipped = []    # person_ids with no email or phone

    for row in contacts:
        person_id = row.get("person_id", "")
        email = row.get("work_email", "")
        phone = row.get("phone", "")
        full_name = row.get("full_name") or f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()

        if not email and not phone:
            contact_skipped.append(person_id)
            continue
        try:
            matches = hs.search_contacts("email", email) if email else hs.search_contacts("phone", _normalise_phone(phone))
            if matches:
                contact_existing[person_id] = matches[0]["id"]
            else:
                contact_new.append(person_id)
        except requests.HTTPError as e:
            print(f"  [preview:contact:error] {full_name}: {e.response.status_code}")

    return {
        "company_existing": company_existing,
        "company_new": company_new,
        "contact_existing": contact_existing,
        "contact_new": contact_new,
        "contact_skipped": contact_skipped,
    }


# ── Execute (writes to HubSpot) ─────────────────────────────────────────────

def execute(hs: HubSpotClient, contacts: list, list_name: str, preview_data: dict):
    """Upsert companies + contacts, create list, print URL."""
    seen_domains = {}

    # Companies
    for row in contacts:
        domain = row.get("domain", "")
        if not domain or domain in seen_domains:
            continue
        company_id = upsert_company(hs, row)
        seen_domains[domain] = company_id

    # Contacts
    contact_ids = []
    for row in contacts:
        contact_id = upsert_contact(hs, row)
        if contact_id:
            contact_ids.append(contact_id)
            company_id = seen_domains.get(row.get("domain", ""))
            if company_id:
                try:
                    hs.associate_contact_to_company(contact_id, company_id)
                except requests.HTTPError as e:
                    print(f"    [assoc:error] {e.response.status_code} {e.response.text[:80]}")

    if not contact_ids:
        print("\nNo contacts were synced. Skipping list creation.")
        return

    # Create static list
    print(f"\n--- Creating list: '{list_name}' ---")
    try:
        list_result = hs.create_static_list(list_name)
        list_id = list_result.get("listId") or list_result.get("id") or list_result.get("list", {}).get("listId")
        print(f"List created (id={list_id})")
    except requests.HTTPError as e:
        print(f"[list:error] {e.response.status_code} {e.response.text[:200]}")
        return

    hs.add_contacts_to_list(str(list_id), contact_ids)
    print(f"Added {len(contact_ids)} contacts to list")

    try:
        portal_id = hs.get_portal_id()
        print(f"\nHubSpot list URL:")
        print(f"  https://app-ap1.hubspot.com/contacts/{portal_id}/objectLists/{list_id}/")
    except Exception as e:
        print(f"[portal:error] Could not fetch portal ID: {e}")
        print(f"  List ID: {list_id} — find it in HubSpot > Contacts > Lists")

    print(f"\nDone. {len(contact_ids)}/{len(contacts)} contacts synced.")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to contacts CSV (from 1_find_contacts.py)")
    parser.add_argument("--list-name", default="", help="HubSpot list name (prompted if not provided)")
    args = parser.parse_args()

    input_path = Path(args.input)
    with open(input_path, newline="", encoding="utf-8") as f:
        contacts = [r for r in csv.DictReader(f) if r.get("person_id")]

    if not contacts:
        print("No contacts found in input CSV.")
        return

    # Step 1: Ask for list name before anything else
    list_name = args.list_name.strip()
    if not list_name:
        list_name = input("\nWhat would you like to name this HubSpot list? ").strip()
    if not list_name:
        print("No list name provided. Aborting.")
        return
    print(f"\nList name: \"{list_name}\"")

    hs = HubSpotClient()

    # Step 2: Read-only preview — check what already exists in HubSpot
    print("Checking HubSpot for existing records...")
    data = preview(hs, contacts)

    n_company_existing = len(data["company_existing"])
    n_company_new      = len(data["company_new"])
    n_contact_existing = len(data["contact_existing"])
    n_contact_new      = len(data["contact_new"])
    n_contact_skipped  = len(data["contact_skipped"])

    print(f"""
─────────────────────────────
  List name : {list_name}

  Companies
    existing : {n_company_existing}
    new      : {n_company_new}

  Contacts
    existing : {n_contact_existing}  (will be updated)
    new      : {n_contact_new}  (will be created)
    skipped  : {n_contact_skipped}  (no email or phone)
─────────────────────────────""")

    # Step 3: Ask for explicit permission before touching HubSpot
    confirm = input("Proceed and sync to HubSpot? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("Aborted. Nothing was written to HubSpot.")
        return

    print()
    execute(hs, contacts, list_name, data)


if __name__ == "__main__":
    main()
