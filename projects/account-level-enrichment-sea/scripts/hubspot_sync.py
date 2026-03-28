"""
HubSpot Company Sync — ICP Match (SEA) + SEA Owner Update
-----------------------------------------------------------
For each company in an enriched accounts CSV:
  - Customers             → skip entirely
  - Active Trial accounts → update ICP Match (SEA) always;
                            set Company owner (SEA) only if currently empty
  - All others            → update ICP Match (SEA) + Company owner (SEA)

Rules:
  - Never touch hubspot_owner_id (AE/company owner field)

ICP Match (SEA) tiers (based on SEA Sales Team Size in enrichment_note):
  0–4   → SMB       (API value: true)
  5–9   → Medium    (API value: false)
  10–24 → High
  25+   → Very High

Usage:
  PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/hubspot_sync.py \
    --input "projects/account-level-enrichment-sea/output/enriched_<timestamp>.csv"
"""

import argparse
import re

from scripts.hubspot_client import HubSpotClient
from scripts.utils import load_csv


def _domain_matches_company(company_name: str, domain: str) -> bool:
    """
    Returns True if the domain root plausibly belongs to the company.
    Handles country-code TLDs like .com.au, .co.nz, .com.sg by checking
    whether parts[-2] is a generic label ('com', 'co', 'net', etc.) and if so
    stepping back one more level.
    """
    GENERIC_SECOND_LEVEL = {"com", "co", "net", "org", "gov", "edu"}
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in GENERIC_SECOND_LEVEL:
        root = parts[-3]
    elif len(parts) >= 2:
        root = parts[-2]
    else:
        root = domain

    # Clean company name to lowercase words (3+ chars)
    name_words = re.findall(r"[a-z]{3,}", company_name.lower())

    # Match if root is in any name word, or any name word is in root
    return any(word in root or root in word for word in name_words)

DARCY_OWNER_ID = "554860379"

ICP_TIERS = [
    (25, "Very High"),
    (10, "High"),
    (5,  "false"),   # Medium
    (0,  "true"),    # SMB
]


def _normalise_domain(raw: str) -> str:
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _search_by_additional_domain(hs: HubSpotClient, domain: str) -> list:
    payload = {
        "filterGroups": [{"filters": [{"propertyName": "hs_additional_domains", "operator": "CONTAINS_TOKEN", "value": domain}]}],
        "properties": ["hs_object_id", "name", "domain"],
        "limit": 5,
    }
    result = hs._post("/crm/v3/objects/companies/search", payload)
    return result.get("results", [])


def _get_company_props(hs: HubSpotClient, company_id: str) -> dict:
    result = hs._get(
        f"/crm/v3/objects/companies/{company_id}",
        params={"properties": "lifecyclestage,trial_status,company_owner_sea,about_us"}
    )
    return result.get("properties", {})


def _icp_value(sea_size: int) -> str:
    for threshold, value in ICP_TIERS:
        if sea_size >= threshold:
            return value
    return "true"  # fallback to SMB


def _parse_sea_size(note: str) -> int:
    m = re.search(r"SEA Sales Team Size:\s*(\d+)", note or "")
    return int(m.group(1)) if m else 0


def _icp_label(api_value: str) -> str:
    return {"true": "SMB", "false": "Medium"}.get(api_value, api_value)


def _text_to_html(text: str) -> str:
    paragraphs = text.split("\n\n")
    parts = [p.strip().replace("\n", "<br>") for p in paragraphs if p.strip()]
    return "<br><br>".join(parts)


def _create_company_note(hs: HubSpotClient, company_id: str, body: str) -> None:
    from datetime import datetime, timezone
    result = hs._post("/crm/v3/objects/notes", {
        "properties": {
            "hs_note_body": _text_to_html(body),
            "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hubspot_owner_id": DARCY_OWNER_ID,
        }
    })
    note_id = result["id"]
    hs._post("/crm/v4/associations/notes/companies/batch/associate/default", {
        "inputs": [{"from": {"id": note_id}, "to": {"id": company_id}}]
    })


def sync(input_path: str) -> None:
    hs = HubSpotClient()
    portal_id = hs.get_portal_id()
    df = load_csv(input_path)

    total = len(df)
    updated = []
    skipped = []
    errors = []
    created = []
    needs_review = []

    for i, row in df.iterrows():
        company_name = row.get("company", row.get("name", f"row {i+1}"))
        raw_domain = str(row.get("website", row.get("Website", ""))).strip()
        note = str(row.get("enrichment_note", ""))

        if not raw_domain or raw_domain.lower() in ("nan", ""):
            print(f"[{i+1}/{total}] {company_name} — SKIP (no domain)")
            skipped.append((company_name, "no domain"))
            continue

        domain = _normalise_domain(raw_domain)

        # --- Find company in HubSpot ---
        try:
            matches = hs.search_companies(domain) or _search_by_additional_domain(hs, domain)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR (lookup): {e}")
            errors.append((company_name, domain, str(e)))
            continue

        if not matches:
            # --- Consistency check before creating ---
            if not _domain_matches_company(company_name, domain):
                print(f"[{i+1}/{total}] {company_name} ({domain}) — SKIPPED (domain mismatch, needs review)")
                needs_review.append((company_name, domain))
                continue

            # --- Create new company ---
            sea_size = _parse_sea_size(note)
            icp_value = _icp_value(sea_size)
            icp_label = _icp_label(icp_value)
            new_props = {
                "domain": domain,
                "name": company_name,
                "icp_match_sea": icp_value,
                "sea_sales_team_size": sea_size,
                "company_owner_sea": DARCY_OWNER_ID,
                "hubspot_owner_id": DARCY_OWNER_ID,
                "about_us": "Darcy",
            }
            try:
                result = hs.create_company(new_props)
                new_id = result["id"]
                hs_url = f"https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{new_id}"
                _create_company_note(hs, new_id, note)
                print(f"[{i+1}/{total}] {company_name} ({domain}) → CREATED (ICP: {icp_label})")
                print(f"         {hs_url}")
                created.append((company_name, domain, icp_label, new_id))
            except Exception as e:
                print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR (create): {e}")
                errors.append((company_name, domain, str(e)))
            continue

        hs_id = matches[0]["id"]
        hs_url = f"https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{hs_id}"

        # --- Fetch current properties ---
        try:
            props = _get_company_props(hs, hs_id)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR (fetch props): {e}")
            errors.append((company_name, domain, str(e)))
            continue

        lifecycle = props.get("lifecyclestage") or ""
        trial = props.get("trial_status") or ""
        current_sea_owner = props.get("company_owner_sea") or ""
        current_about = props.get("about_us") or ""

        # --- Rule: skip customers ---
        if lifecycle == "customer":
            print(f"[{i+1}/{total}] {company_name} ({domain}) → SKIPPED (existing customer)")
            skipped.append((company_name, "customer"))
            continue

        # --- Compute ICP tier ---
        sea_size = _parse_sea_size(note)
        icp_value = _icp_value(sea_size)
        icp_label = _icp_label(icp_value)

        # --- Build update payload ---
        update_props = {"icp_match_sea": icp_value, "sea_sales_team_size": sea_size}
        if "Darcy" not in current_about:
            update_props["about_us"] = (current_about + "\n\nDarcy").strip()

        is_active_trial = trial == "Active Trial"
        sea_owner_set = False

        if is_active_trial:
            # Only set SEA owner if currently unassigned
            if not current_sea_owner:
                update_props["company_owner_sea"] = DARCY_OWNER_ID
                sea_owner_set = True
        else:
            update_props["company_owner_sea"] = DARCY_OWNER_ID
            sea_owner_set = True

        # --- Apply update ---
        try:
            hs.update_company(hs_id, update_props)
        except Exception as e:
            print(f"[{i+1}/{total}] {company_name} ({domain}) — ERROR (update): {e}")
            errors.append((company_name, domain, str(e)))
            continue

        # --- Create enrichment note ---
        try:
            _create_company_note(hs, hs_id, note)
        except Exception as e:
            print(f"  ! note creation failed: {e}")

        sea_note = "SEA owner: Darcy Jack" if sea_owner_set else "SEA owner: kept existing"
        trial_note = " [active trial]" if is_active_trial else ""
        print(f"[{i+1}/{total}] {company_name} ({domain}) → UPDATED (ICP: {icp_label}, {sea_note}{trial_note})")
        print(f"         {hs_url}")
        updated.append((company_name, domain, icp_label, hs_id, sea_owner_set))

    # --- Summary ---
    print(f"\n{'─'*70}")
    print(f"Summary: {len(updated)} updated, {len(created)} created, {len(skipped)} skipped, {len(needs_review)} needs review, {len(errors)} errors")
    if skipped:
        for name, reason in skipped:
            print(f"  Skipped: {name} ({reason})")
    if errors:
        for name, domain, err in errors:
            print(f"  Error: {name} ({domain}): {err}")
    if needs_review:
        print(f"\nNeeds manual review (domain doesn't match company name — not created):")
        for name, domain in needs_review:
            print(f"  {name}: {domain}")
    if updated:
        print(f"\nUpdated — HubSpot links:")
        for name, domain, icp, hs_id, _ in updated:
            print(f"  {name}: https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{hs_id}")
    if created:
        print(f"\nCreated — HubSpot links:")
        for name, domain, icp, hs_id in created:
            print(f"  {name}: https://app-ap1.hubspot.com/contacts/{portal_id}/record/0-2/{hs_id}")
    print(f"{'─'*70}")


def main():
    parser = argparse.ArgumentParser(description="Sync enriched accounts to HubSpot.")
    parser.add_argument("--input", required=True, help="Path to enriched accounts CSV")
    args = parser.parse_args()
    sync(args.input)


if __name__ == "__main__":
    main()
