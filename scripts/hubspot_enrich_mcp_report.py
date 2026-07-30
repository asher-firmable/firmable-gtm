"""
hubspot_enrich_mcp_report.py

For each company in the MCP signal report, look up:
- HubSpot company ID → company URL
- HubSpot company owner
- Most relevant deal (open/recent) → deal URL
- Deal owner

Output: JSON printed to stdout, ready to embed in the artifact.

Usage:
    PYTHONPATH=. python3 scripts/hubspot_enrich_mcp_report.py
"""

import json
import time
from scripts.hubspot_client import HubSpotClient

PORTAL_ID = 24160926
BASE = f"https://app-ap1.hubspot.com/contacts/{PORTAL_ID}"

COMPANIES = [
    "Tech Data Australia",
    "PitchBook",
    "Intellect",
    "YORA",
    "Eftsure",
    "Termina",
    "Deel",
    "Supermetrics",
    "DigitalMaas",
    "Majorsgroup",
    "Grw AI",
    "Ilaria",
    "SYDCO Technology",
    "Affinda",
    "Remote",
    "Fusion5",
    "Vodafone Business Centre",
    "First AML",
    "Precision Sourcing",
    "Cevo Australia",
    "Visory",
    "Callable",
    "Mainpac",
    "Zudello",
    "Caruso",
    "Biztech Lawyers",
    "BackPro AI",
    "PRX Vault",
    "Infinity22",
    "The Hatchery",
    "alldemand",
    "DevRev",
    "Impala Talent",
    "Smartly",
    "Mivada",
    "HammerTech",
    "Spotto",
    "Tecala Group",
    "Carta",
    "Fireworks AI",
    "iCumulus",
    "Colobbo",
    "Inductive Automation",
    "TenClub",
    "Fulcrum Solutions",
    "Demand Consulting",
]

STAGE_ORDER = {
    "closedwon": 0,
    "contractsent": 1,
    "decisionmakerboughtin": 2,
    "presentationscheduled": 3,
    "qualifiedtobuy": 4,
    "appointmentscheduled": 5,
    "closedlost": 6,
}


def with_retry(fn, retries=3, backoff=2.0):
    import requests
    for attempt in range(retries):
        try:
            return fn()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (429, 500, 502, 503, 504):
                wait = backoff ** attempt
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def search_company(hs, name):
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "name", "operator": "EQ", "value": name}
        ]}],
        "properties": ["name", "hubspot_owner_id"],
        "limit": 3,
    }
    r = with_retry(lambda: hs._post("/crm/v3/objects/companies/search", payload))
    results = r.get("results", [])
    if results:
        return results[0]

    # Fallback: text search
    payload2 = {
        "filterGroups": [{"filters": [
            {"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": name.split()[0]}
        ]}],
        "properties": ["name", "hubspot_owner_id"],
        "limit": 5,
    }
    r2 = with_retry(lambda: hs._post("/crm/v3/objects/companies/search", payload2))
    for res in r2.get("results", []):
        if name.lower() in (res.get("properties", {}).get("name") or "").lower():
            return res
    return None


def get_company_deals(hs, company_id):
    r = with_retry(lambda: hs._get(
        f"/crm/v4/objects/companies/{company_id}/associations/deals"
    ))
    return [str(t["toObjectId"]) for t in r.get("results", [])]


def get_deals(hs, deal_ids):
    if not deal_ids:
        return []
    payload = {
        "inputs": [{"id": did} for did in deal_ids],
        "properties": ["dealname", "dealstage", "closedate", "hubspot_owner_id", "amount"],
    }
    r = with_retry(lambda: hs._post("/crm/v3/objects/deals/batch/read", payload))
    return r.get("results", [])


def pick_best_deal(deals):
    if not deals:
        return None
    def score(d):
        stage = (d.get("properties", {}).get("dealstage") or "").lower()
        return STAGE_ORDER.get(stage, 99)
    return sorted(deals, key=score)[0]


def get_owner_name(hs, owner_id):
    if not owner_id:
        return ""
    try:
        r = with_retry(lambda: hs._get(f"/crm/v3/owners/{owner_id}"))
        fn = r.get("firstName") or ""
        ln = r.get("lastName") or ""
        return f"{fn} {ln}".strip()
    except Exception:
        return ""


def main():
    hs = HubSpotClient()
    results = {}

    # Collect all unique owner IDs so we can batch-resolve names
    owner_cache = {}

    def resolve_owner(owner_id):
        if not owner_id:
            return ""
        if owner_id not in owner_cache:
            owner_cache[owner_id] = get_owner_name(hs, owner_id)
        return owner_cache[owner_id]

    for name in COMPANIES:
        print(f"  Looking up: {name}", flush=True)
        company = search_company(hs, name)

        if not company:
            results[name] = {
                "companyId": None, "companyUrl": None, "companyOwner": None,
                "dealId": None, "dealName": None, "dealUrl": None, "dealOwner": None,
                "dealStage": None,
            }
            time.sleep(0.1)
            continue

        company_id = company["id"]
        props = company.get("properties", {})
        company_owner_id = props.get("hubspot_owner_id")
        company_owner = resolve_owner(company_owner_id)
        company_url = f"{BASE}/company/{company_id}"

        deal_ids = get_company_deals(hs, company_id)
        deals = get_deals(hs, deal_ids)
        best = pick_best_deal(deals)

        deal_id = deal_name = deal_url = deal_owner = deal_stage = None
        deal_amount = None
        if best:
            deal_id = best["id"]
            dp = best.get("properties", {})
            deal_name = dp.get("dealname") or ""
            deal_stage = dp.get("dealstage") or ""
            deal_owner_id = dp.get("hubspot_owner_id")
            deal_owner = resolve_owner(deal_owner_id)
            deal_url = f"{BASE}/deal/{deal_id}"
            raw_amount = dp.get("amount")
            try:
                deal_amount = float(raw_amount) if raw_amount else None
            except (ValueError, TypeError):
                deal_amount = None

        results[name] = {
            "companyId": company_id,
            "companyUrl": company_url,
            "companyOwner": company_owner,
            "dealId": deal_id,
            "dealName": deal_name,
            "dealUrl": deal_url,
            "dealOwner": deal_owner,
            "dealStage": deal_stage,
            "dealAmount": deal_amount,
        }
        time.sleep(0.15)

    print("\n\n=== HUBSPOT DATA (copy into artifact) ===\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
