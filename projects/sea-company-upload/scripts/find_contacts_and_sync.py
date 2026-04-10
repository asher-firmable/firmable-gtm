"""
Find Contacts & Sync to HubSpot — Viable Companies (SEA)
----------------------------------------------------------
For each company in 'Viable Companies.csv':
  1. Search Firmable for SDR/BDR/Sales contacts in SG (10 search combinations)
  2. Enrich each candidate with get_person() — only keep contacts with both phone + email
  3. Stop when 2 qualified contacts are found per company
  4. Check HubSpot — if contact email exists, skip; if not, create and associate to company
  5. Save a summary CSV

Phase 1 results are saved to contact_candidates.csv so Firmable is never queried twice.
Use --from-cache to skip Phase 1 entirely and go straight to HubSpot sync.

Usage:
  # Full run (Phase 1 + Phase 2):
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/find_contacts_and_sync.py \
    --owner-id <hubspot_owner_id> [--country SG]

  # Re-run Phase 2 only from cached results:
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/find_contacts_and_sync.py \
    --owner-id <hubspot_owner_id> --from-cache
"""

import argparse
import csv
import json
import time
from pathlib import Path

from scripts.firmable_api import FirmableClient
from scripts.hubspot_client import HubSpotClient

VIABLE_CSV       = Path("projects/sea-company-upload/output/Viable Companies.csv")
HS_ID_CSV        = Path("projects/sea-company-upload/output/viable_in_hubspot.csv")
OUTPUT_CSV       = Path("projects/sea-company-upload/output/contact_summary.csv")
CANDIDATES_CSV   = Path("projects/sea-company-upload/output/contact_candidates.csv")

SEARCH_COMBOS = [
    ("Sales Development",    4),
    ("Sales",                4),
    ("SDR",                  4),
    ("BDR",                  4),
    ("Business Development", 4),
    ("Sales Development",    5),
    ("Sales",                5),
    ("SDR",                  5),
    ("BDR",                  5),
    ("Business Development", 5),
]

OUTPUT_FIELDS = [
    "Company Name",
    "Domain/Website",
    "HubSpot Company Link",
    "Contact 1 Link",
    "Contact 1 Already in CRM",
    "Contact 2 Link",
    "Contact 2 Already in CRM",
]

# Columns saved to / loaded from the candidates cache CSV
CANDIDATE_FIELDS = [
    "company_name",
    "domain",
    "firmable_id",
    "hs_company_id",
    "hs_company_url",
    "email",
    "phone",
    "first_name",
    "last_name",
    "existing_hs_contact_id",
    "existing_hs_contact_url",
]


def _build_hs_company_url(portal_id: str, company_id: str) -> str:
    return f"https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{company_id}"


def _build_hs_contact_url(portal_id: str, contact_id: str) -> str:
    return f"https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-1/{contact_id}"


def _get_email(person: dict) -> str:
    """Extract first work email from a Firmable get_person response.
    emails = {"work": [{"value": "..."}], "personal": [...]}
    """
    emails = person.get("emails", {})
    if isinstance(emails, dict):
        for entry in emails.get("work", []):
            v = entry.get("value", "") if isinstance(entry, dict) else entry
            if v:
                return v
        # fallback: any type
        for entries in emails.values():
            for entry in entries:
                v = entry.get("value", "") if isinstance(entry, dict) else entry
                if v:
                    return v
    elif isinstance(emails, list):
        for e in emails:
            if isinstance(e, dict):
                v = e.get("value") or e.get("email") or ""
                if v:
                    return v
            elif isinstance(e, str) and e:
                return e
    return ""


def _get_phone(person: dict) -> str:
    """Extract first non-DND phone from a Firmable get_person response.
    phones = [{"value": "+65...", "is_dnd": null}]
    """
    for p in person.get("phones", []):
        if isinstance(p, dict):
            v = p.get("value") or p.get("number") or ""
            dnd = p.get("is_dnd") or p.get("dnd") or False
            if v and not dnd:
                return v
        elif isinstance(p, str) and p:
            return p
    # fallback: any phone even if dnd
    for p in person.get("phones", []):
        if isinstance(p, dict):
            v = p.get("value") or p.get("number") or ""
            if v:
                return v
    return ""


def _name_parts(person: dict) -> tuple:
    first = person.get("first_name") or ""
    last  = person.get("last_name") or ""
    if not first and not last:
        full  = person.get("name") or ""
        parts = full.strip().split(" ", 1)
        first = parts[0] if parts else ""
        last  = parts[1] if len(parts) > 1 else ""
    return first, last


def _save_candidates(staged_results: list, portal_id: str):
    """Flatten staged_results into rows and save to CANDIDATES_CSV."""
    rows = []
    for s in staged_results:
        for fc in s["contacts"]:
            rows.append({
                "company_name":           s["company_name"],
                "domain":                 s["domain"],
                "firmable_id":            s["firmable_id"],
                "hs_company_id":          s["hs_company_id"],
                "hs_company_url":         s["hs_company_url"],
                "email":                  fc["email"],
                "phone":                  fc["phone"],
                "first_name":             fc["person"].get("first_name", ""),
                "last_name":              fc["person"].get("last_name", ""),
                "existing_hs_contact_id": fc["existing_id"],
                "existing_hs_contact_url": fc["existing_url"],
            })
        # If a company had 0 contacts, still write a placeholder row so
        # we know it was processed (no contacts = empty email row)
        if not s["contacts"]:
            rows.append({
                "company_name":           s["company_name"],
                "domain":                 s["domain"],
                "firmable_id":            s["firmable_id"],
                "hs_company_id":          s["hs_company_id"],
                "hs_company_url":         s["hs_company_url"],
                "email":                  "",
                "phone":                  "",
                "first_name":             "",
                "last_name":              "",
                "existing_hs_contact_id": "",
                "existing_hs_contact_url": "",
            })

    CANDIDATES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows)} rows → {CANDIDATES_CSV}")


def _load_candidates(portal_id: str) -> list:
    """Load CANDIDATES_CSV back into staged_results format."""
    with open(CANDIDATES_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Group rows by (company_name, domain)
    from collections import OrderedDict
    groups: dict = OrderedDict()
    for row in rows:
        key = (row["company_name"], row["domain"])
        if key not in groups:
            groups[key] = {
                "company_name":  row["company_name"],
                "domain":        row["domain"],
                "firmable_id":   row["firmable_id"],
                "hs_company_id": row["hs_company_id"],
                "hs_company_url": row["hs_company_url"],
                "contacts": [],
            }
        if row["email"]:
            groups[key]["contacts"].append({
                "person":       {"first_name": row["first_name"], "last_name": row["last_name"]},
                "email":        row["email"],
                "phone":        row["phone"],
                "existing_id":  row["existing_hs_contact_id"],
                "existing_url": row["existing_hs_contact_url"],
            })

    return list(groups.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id",   required=True, help="HubSpot owner ID for new contacts")
    parser.add_argument("--country",    default="SG",  help="Country filter for Firmable search (default: SG)")
    parser.add_argument("--from-cache", action="store_true",
                        help="Skip Firmable search and load Phase 1 results from contact_candidates.csv")
    args = parser.parse_args()

    hs        = HubSpotClient()
    portal_id = hs.get_portal_id()

    # ── PHASE 1: Firmable search (or load from cache) ─────────────────────
    if args.from_cache:
        if not CANDIDATES_CSV.exists():
            print(f"ERROR: --from-cache specified but {CANDIDATES_CSV} does not exist.")
            print("Run without --from-cache first to generate it.")
            return
        print(f"Loading Phase 1 results from cache: {CANDIDATES_CSV}")
        staged_results = _load_candidates(portal_id)
        total = len(staged_results)
        print(f"Loaded {total} companies from cache.\n")
    else:
        firm = FirmableClient()

        # ── Load viable companies ──────────────────────────────────────────
        with open(VIABLE_CSV, newline="", encoding="utf-8-sig") as f:
            viable = list(csv.DictReader(f))

        # ── Build domain → HubSpot company ID map ─────────────────────────
        hs_id_map = {}
        if HS_ID_CSV.exists():
            with open(HS_ID_CSV, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    domain = row.get("domain", "").strip()
                    hs_id  = row.get("hubspot_id", "").strip()
                    if domain and hs_id:
                        hs_id_map[domain] = hs_id

        total = len(viable)
        print(f"PHASE 1 — Searching contacts for {total} companies (country: {args.country})")
        print(f"No HubSpot writes yet.\n")

        staged_results = []

        for i, row in enumerate(viable, 1):
            company_name = row.get("Company Name", f"Row {i}").strip()
            domain       = row.get("Domain/Website", "").strip()
            firmable_id  = row.get("Firmable Company ID", "").strip()

            # HubSpot company ID — from map or look up by domain
            hs_company_id = hs_id_map.get(domain, "")
            if not hs_company_id:
                try:
                    matches = hs.search_companies(domain)
                    if matches:
                        hs_company_id = matches[0]["id"]
                    time.sleep(0.1)
                except Exception:
                    pass

            hs_company_url = _build_hs_company_url(portal_id, hs_company_id) if hs_company_id else ""
            print(f"[{i}/{total}] {company_name} ({domain})")

            if not firmable_id:
                print(f"  SKIP — no Firmable ID")
                staged_results.append({
                    "company_name": company_name, "domain": domain,
                    "firmable_id": firmable_id, "hs_company_id": hs_company_id,
                    "hs_company_url": hs_company_url, "contacts": [],
                })
                continue

            # ── Search Firmable ────────────────────────────────────────────
            found_contacts = []
            seen_ids = set()

            for position, seniority in SEARCH_COMBOS:
                if len(found_contacts) >= 2:
                    break
                try:
                    candidates = firm.find_contacts(
                        company_id=firmable_id,
                        seniority=seniority,
                        country=args.country,
                        position=position,
                        size=10,
                    )
                    time.sleep(1.0)
                except Exception as e:
                    if "429" in str(e):
                        print(f"  rate limit — sleeping 5s ({position}, s{seniority})")
                        time.sleep(5.0)
                    else:
                        print(f"  search error ({position}, s{seniority}): {e}")
                    continue

                for candidate in candidates:
                    if len(found_contacts) >= 2:
                        break
                    cid = candidate.get("id") or candidate.get("person_id") or ""
                    if not cid or cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    if not (candidate.get("has_email") and candidate.get("has_phone")):
                        continue
                    try:
                        person = firm.get_person(id=cid)
                        time.sleep(1.0)
                    except Exception as e:
                        if "429" in str(e):
                            print(f"  rate limit on enrich — sleeping 5s")
                            time.sleep(5.0)
                        else:
                            print(f"  enrich error (id={cid}): {e}")
                        continue

                    email = _get_email(person)
                    phone = _get_phone(person)
                    if not email or not phone:
                        continue

                    # ── HubSpot existence check (read-only) ────────────────
                    existing_id  = ""
                    existing_url = ""
                    try:
                        existing = hs.get_contact_by_email(email)
                        time.sleep(0.1)
                        if existing:
                            existing_id  = existing["id"]
                            existing_url = _build_hs_contact_url(portal_id, existing_id)
                            print(f"  Found (in CRM): {person.get('first_name', '')} {person.get('last_name', '')} | {email}")
                        else:
                            print(f"  Found (new):    {person.get('first_name', '')} {person.get('last_name', '')} | {email}")
                    except Exception as e:
                        print(f"  HubSpot lookup error ({email}): {e}")

                    found_contacts.append({
                        "person":       person,
                        "email":        email,
                        "phone":        phone,
                        "existing_id":  existing_id,
                        "existing_url": existing_url,
                    })

            staged_results.append({
                "company_name":   company_name,
                "domain":         domain,
                "firmable_id":    firmable_id,
                "hs_company_id":  hs_company_id,
                "hs_company_url": hs_company_url,
                "contacts":       found_contacts,
            })

        # ── Save candidates cache ──────────────────────────────────────────
        print(f"\nSaving Phase 1 results to cache...")
        _save_candidates(staged_results, portal_id)

    # ── PHASE 1 SUMMARY ───────────────────────────────────────────────────
    total_found    = sum(len(s["contacts"]) for s in staged_results)
    two_contacts   = sum(1 for s in staged_results if len(s["contacts"]) == 2)
    one_contact    = sum(1 for s in staged_results if len(s["contacts"]) == 1)
    zero_contacts  = sum(1 for s in staged_results if len(s["contacts"]) == 0)
    already_in_crm = sum(1 for s in staged_results for c in s["contacts"] if c["existing_id"])
    new_to_create  = sum(1 for s in staged_results for c in s["contacts"] if not c["existing_id"])

    sep = "=" * 60
    print(f"\n{sep}")
    print("CONTACT SEARCH SUMMARY")
    print(sep)
    print(f"  Total contacts found          : {total_found}")
    print(f"  Companies with 2 contacts     : {two_contacts}")
    print(f"  Companies with 1 contact      : {one_contact}")
    print(f"  Companies with 0 contacts     : {zero_contacts}")
    print(f"  Already in CRM (will skip)    : {already_in_crm}")
    print(f"  New contacts to create        : {new_to_create}")
    print(sep)

    if new_to_create == 0:
        print("\nNo new contacts to create. Saving summary CSV.")
    else:
        print(f"\nReady to create {new_to_create} new contact(s) in HubSpot. Proceeding...")

    # ── PHASE 2: Write to HubSpot ─────────────────────────────────────────
    if new_to_create > 0:
        print(f"\nPHASE 2 — Creating {new_to_create} new contacts in HubSpot...\n")

    results = []
    for s in staged_results:
        contact_data = []
        for fc in s["contacts"]:
            if fc["existing_id"]:
                print(f"  → Skipping (already in CRM): {fc['email']}")
                contact_data.append({"url": fc["existing_url"], "existed": "True"})
            else:
                first = fc["person"].get("first_name", "")
                last  = fc["person"].get("last_name", "")
                if not first and not last:
                    first, last = _name_parts(fc["person"])
                props = {
                    "email":                 fc["email"],
                    "firstname":             first,
                    "lastname":              last,
                    "phone":                 fc["phone"],
                    "hs_lead_status":        "NEW",
                    "contact_source":        "Outbound Prospecting",
                    "contact_source_detail": "List Upload [Allocated accounts]",
                    "hubspot_owner_id":      args.owner_id,
                }
                try:
                    created    = hs.create_contact(props)
                    contact_id = created["id"]
                    time.sleep(0.1)
                    if s["hs_company_id"]:
                        hs.associate_contact_to_company(contact_id, s["hs_company_id"])
                        time.sleep(0.1)
                    contact_url = _build_hs_contact_url(portal_id, contact_id)
                    print(f"  → Created: {fc['email']} (id={contact_id})")
                    contact_data.append({"url": contact_url, "existed": "False"})
                except Exception as e:
                    print(f"  → Create error ({fc['email']}): {e}")
                    contact_data.append({"url": "", "existed": "Error"})

        while len(contact_data) < 2:
            contact_data.append({"url": "", "existed": ""})

        results.append({
            "Company Name":              s["company_name"],
            "Domain/Website":            s["domain"],
            "HubSpot Company Link":      s["hs_company_url"],
            "Contact 1 Link":            contact_data[0]["url"],
            "Contact 1 Already in CRM":  contact_data[0]["existed"],
            "Contact 2 Link":            contact_data[1]["url"],
            "Contact 2 Already in CRM":  contact_data[1]["existed"],
        })

    # ── Save output CSV ────────────────────────────────────────────────────
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    created_count = sum(1 for r in results if "False" in (r["Contact 1 Already in CRM"], r["Contact 2 Already in CRM"]))
    print(f"\n{'─'*60}")
    print(f"Done. {created_count} new contact(s) created.")
    print(f"Saved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
