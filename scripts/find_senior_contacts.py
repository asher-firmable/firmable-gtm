"""
find_senior_contacts.py

Finds closed-won ANZ deals (Oct 2025–Mar 2026), extracts senior sales/revenue contacts,
and surfaces Fathom recording links — preferring pre-close (Discovery/Demo) calls.
Target: ≥15 companies with recordings.

Usage:
    PYTHONPATH=. python3 find_senior_contacts.py
"""

import re
import time
from datetime import datetime, timezone

from scripts.hubspot_client import HubSpotClient

# ── Title matching ─────────────────────────────────────────────────────────────

SENIOR_PATTERNS = [
    r'\bvp\b.{0,10}sales',
    r'vice.?president.{0,10}sales',
    r'head of sales',
    r'director.{0,10}sales',
    r'sales director',
    r'chief sales officer',
    r'\bcso\b',
    r'chief revenue officer',
    r'\bcro\b',
    r'head of (gtm|growth|revenue|go.to.market)',
    r'(vp|vice president|director|head).{0,10}(revenue|gtm|growth|go.to.market)',
    r'\bvp\b.{0,10}revenue',
    r'director.{0,10}revenue',
    r'head.{0,10}revenue',
]


def is_senior(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(re.search(p, t) for p in SENIOR_PATTERNS)


# ── Resilient HTTP helper ──────────────────────────────────────────────────────

def with_retry(fn, retries=3, backoff=2.0):
    """Call fn(), retrying on 5xx or connection errors with exponential backoff."""
    import requests
    for attempt in range(retries):
        try:
            return fn()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (429, 500, 502, 503, 504):
                wait = backoff ** attempt
                print(f"  [retry {attempt+1}/{retries}] HTTP {e.response.status_code} — waiting {wait:.0f}s")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff ** attempt
                print(f"  [retry {attempt+1}/{retries}] {e} — waiting {wait:.0f}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


# ── Deal search ────────────────────────────────────────────────────────────────

def fetch_closed_won_deals(hs: HubSpotClient, start_ms: int, end_ms: int) -> list:
    deals, after = [], None
    while True:
        payload = {
            "filterGroups": [{
                "filters": [
                    {"propertyName": "dealstage", "operator": "EQ", "value": "closedwon"},
                    {"propertyName": "closedate", "operator": "GTE", "value": str(start_ms)},
                    {"propertyName": "closedate", "operator": "LTE", "value": str(end_ms)},
                ]
            }],
            "properties": ["dealname", "closedate"],
            "limit": 100,
        }
        if after:
            payload["after"] = after
        result = with_retry(lambda p=payload: hs._post("/crm/v3/objects/deals/search", p))
        deals.extend(result.get("results", []))
        after = result.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return deals


# ── Batch association lookup (deals → companies or contacts) ───────────────────

def batch_get_associations(hs: HubSpotClient, from_type: str, to_type: str, from_ids: list) -> dict:
    """
    Returns a dict: {from_id: [to_id, ...]} for all given from_ids.
    Uses the v4 batch associations endpoint.
    """
    mapping = {fid: [] for fid in from_ids}
    for i in range(0, len(from_ids), 100):
        chunk = from_ids[i:i + 100]
        payload = {"inputs": [{"id": fid} for fid in chunk]}
        result = with_retry(
            lambda p=payload: hs._post(
                f"/crm/v4/associations/{from_type}/{to_type}/batch/read", p
            )
        )
        for item in result.get("results", []):
            from_id = str(item["from"]["id"])
            to_ids = [str(t["toObjectId"]) for t in item.get("to", [])]
            mapping[from_id] = to_ids
        time.sleep(0.1)  # light throttle
    return mapping


# ── Fathom links ───────────────────────────────────────────────────────────────

FATHOM_RE = re.compile(r'https?://(?:app\.)?fathom\.video/[^\s<>"\')]+', re.IGNORECASE)


def extract_fathom_links(text: str) -> list:
    return [u.rstrip('.,);') for u in FATHOM_RE.findall(text or "")]


def ts_to_ms(ts) -> int:
    """Convert HubSpot timestamp (ISO string or ms int) to milliseconds int."""
    if not ts:
        return 0
    try:
        return int(ts)
    except (ValueError, TypeError):
        pass
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def normalize_fathom_url(url: str) -> str:
    """Strip query params and unescape HTML entities to get a canonical recording URL."""
    import html
    url = html.unescape(url)
    return url.split("?")[0].split("#")[0]


def fetch_all_fathom_links(hs: HubSpotClient, anz_deal_ids: set, contact_to_deal: dict) -> dict:
    """
    Portal-wide search for Fathom links in notes and calls.
    Checks BOTH deal associations and contact associations (Fathom often logs on contact).
    Returns {deal_id: [{"url": ..., "ts": ms_int}, ...]} (2 earliest per deal).
    """
    deal_fathom: dict = {did: [] for did in anz_deal_ids}
    qualifying_contact_ids = set(contact_to_deal.keys())

    search_targets = [
        ("notes", "hs_note_body"),
        ("calls", "hs_call_body"),
    ]

    for obj_type, body_prop in search_targets:
        print(f"  Searching {obj_type} for 'fathom' links...")
        after = None
        page = 0
        while True:
            payload = {
                "filterGroups": [{
                    "filters": [{
                        "propertyName": body_prop,
                        "operator": "CONTAINS_TOKEN",
                        "value": "fathom",
                    }]
                }],
                "properties": [body_prop, "hs_timestamp", "hs_createdate"],
                "limit": 100,
            }
            if after:
                payload["after"] = after

            try:
                result = with_retry(
                    lambda p=payload, ot=obj_type: hs._post(f"/crm/v3/objects/{ot}/search", p)
                )
            except Exception as e:
                print(f"  [warn] {obj_type} search failed: {e}")
                break

            items = result.get("results", [])
            page += 1
            print(f"    page {page}: {len(items)} {obj_type}")

            for item in items:
                obj_id = item["id"]
                props = item.get("properties", {})
                body = props.get(body_prop, "") or ""
                urls = [normalize_fathom_url(u) for u in extract_fathom_links(body)]
                if not urls:
                    continue

                raw_ts = props.get("hs_timestamp") or props.get("hs_createdate")
                ts_ms = ts_to_ms(raw_ts)

                matched_deals = set()

                # Check deal associations
                try:
                    assoc = with_retry(
                        lambda oid=obj_id, ot=obj_type: hs._get(
                            f"/crm/v4/objects/{ot}/{oid}/associations/deals"
                        )
                    )
                    for r in assoc.get("results", []):
                        did = str(r["toObjectId"])
                        if did in anz_deal_ids:
                            matched_deals.add(did)
                except Exception:
                    pass

                # Check contact associations (Fathom often logs against contact, not deal)
                if qualifying_contact_ids:
                    try:
                        assoc = with_retry(
                            lambda oid=obj_id, ot=obj_type: hs._get(
                                f"/crm/v4/objects/{ot}/{oid}/associations/contacts"
                            )
                        )
                        for r in assoc.get("results", []):
                            cid = str(r["toObjectId"])
                            if cid in qualifying_contact_ids:
                                matched_deals.add(contact_to_deal[cid])
                    except Exception:
                        pass

                for did in matched_deals:
                    for url in urls:
                        deal_fathom[did].append({"url": url, "ts": ts_ms})

            after = result.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

    # Deduplicate and keep up to 5 earliest per deal (caller will apply pre-close filter)
    for did in deal_fathom:
        seen, unique = set(), []
        for l in sorted(deal_fathom[did], key=lambda x: x["ts"]):
            if l["url"] not in seen:
                seen.add(l["url"])
                unique.append(l)
        deal_fathom[did] = unique[:5]

    return deal_fathom


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    hs = HubSpotClient()

    start_ms = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms   = int(datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

    # ── 1. Fetch closed-won deals ─────────────────────────────────────────────
    print("Fetching closed-won deals (Oct 2025–Mar 2026)...")
    all_deals = fetch_closed_won_deals(hs, start_ms, end_ms)
    print(f"  → {len(all_deals)} closed-won deals total")

    deal_ids = [d["id"] for d in all_deals]
    deal_map = {d["id"]: d for d in all_deals}

    # ── 2. Batch: deal → companies ────────────────────────────────────────────
    print("Batch-fetching company associations...")
    deal_to_companies = batch_get_associations(hs, "deals", "companies", deal_ids)

    all_company_ids = list({cid for ids in deal_to_companies.values() for cid in ids})
    print(f"  → {len(all_company_ids)} unique companies — fetching properties...")

    # Batch read company properties
    companies_raw = []
    for i in range(0, len(all_company_ids), 100):
        chunk = all_company_ids[i:i + 100]
        payload = {"inputs": [{"id": cid} for cid in chunk], "properties": ["name", "market"]}
        result = with_retry(lambda p=payload: hs._post("/crm/v3/objects/companies/batch/read", p))
        companies_raw.extend(result.get("results", []))
        time.sleep(0.1)

    company_props = {c["id"]: c.get("properties", {}) for c in companies_raw}

    # ── 3. Filter ANZ deals ───────────────────────────────────────────────────
    anz_deals = []
    for deal_id, company_ids in deal_to_companies.items():
        for cid in company_ids:
            props = company_props.get(cid, {})
            if "anz" in (props.get("market") or "").lower():
                deal = deal_map[deal_id]
                raw_close = deal["properties"].get("closedate") or ""
                close_date_str = raw_close[:10]  # YYYY-MM-DD
                close_date_ms = ts_to_ms(raw_close)
                anz_deals.append({
                    "deal_id": deal_id,
                    "deal_name": deal["properties"].get("dealname", ""),
                    "close_date": close_date_str,
                    "close_date_ms": close_date_ms,
                    "company_id": cid,
                    "company_name": props.get("name", "Unknown"),
                })
                break

    print(f"  → {len(anz_deals)} ANZ closed-won deals")

    if not anz_deals:
        print("\nNo ANZ deals found. Check that the Company 'market' property contains 'ANZ'.")
        return

    # ── 4. Batch: deal → contacts ─────────────────────────────────────────────
    print("Batch-fetching contact associations...")
    anz_deal_ids = [e["deal_id"] for e in anz_deals]
    deal_to_contacts = batch_get_associations(hs, "deals", "contacts", anz_deal_ids)

    all_contact_ids = list({cid for ids in deal_to_contacts.values() for cid in ids})
    print(f"  → {len(all_contact_ids)} unique contacts — fetching properties...")

    contacts_raw = []
    for i in range(0, len(all_contact_ids), 100):
        chunk = all_contact_ids[i:i + 100]
        payload = {"inputs": [{"id": cid} for cid in chunk],
                   "properties": ["firstname", "lastname", "email", "jobtitle"]}
        result = with_retry(lambda p=payload: hs._post("/crm/v3/objects/contacts/batch/read", p))
        contacts_raw.extend(result.get("results", []))
        time.sleep(0.1)

    contact_props = {c["id"]: c.get("properties", {}) for c in contacts_raw}

    # ── 5. Filter senior titles ───────────────────────────────────────────────
    rows = []
    for entry in anz_deals:
        deal_id = entry["deal_id"]
        contact_ids = deal_to_contacts.get(deal_id, [])
        for cid in contact_ids:
            p = contact_props.get(cid, {})
            title = p.get("jobtitle", "") or ""
            if is_senior(title):
                rows.append({
                    **entry,
                    "contact_id": cid,
                    "name": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
                    "email": p.get("email", ""),
                    "title": title,
                    "fathom_links": [],
                })

    if not rows:
        print("\nNo senior sales/revenue contacts found in ANZ closed-won deals.")
        print("Titles checked: VP/Head/Director of Sales, CSO, CRO, Head of GTM/Growth/Revenue")
        return

    # ── 6. Show titles for review ─────────────────────────────────────────────
    print(f"\n{'='*105}")
    print(f"SENIOR CONTACTS FOUND ({len(rows)} total) — review titles below")
    print(f"{'='*105}")
    print(f"{'#':<3}  {'Company':<28}  {'Contact':<22}  {'Title':<38}  {'Close':<12}")
    print(f"{'─'*3}  {'─'*28}  {'─'*22}  {'─'*38}  {'─'*12}")
    for i, r in enumerate(rows, 1):
        print(
            f"{i:<3}  {r['company_name'][:28]:<28}  {r['name'][:22]:<22}  "
            f"{r['title'][:38]:<38}  {r['close_date']:<12}"
        )

    # ── 7. Fetch Fathom links (portal-wide note/call search) ─────────────────
    print(f"\n{'='*105}")
    print("Searching portal for Fathom recording links (notes + calls)...")
    print(f"{'='*105}\n")

    qualifying_deal_ids = {r["deal_id"] for r in rows}
    # Map contact_id → deal_id so Fathom notes on contacts can be traced back to deals
    contact_to_deal = {r["contact_id"]: r["deal_id"] for r in rows}
    fathom_by_deal = fetch_all_fathom_links(hs, qualifying_deal_ids, contact_to_deal)

    for r in rows:
        r["fathom_links"] = fathom_by_deal.get(r["deal_id"], [])
        r["close_date_ms"] = next(
            (e["close_date_ms"] for e in anz_deals if e["deal_id"] == r["deal_id"]), 0
        )

    # ── 8. Company-grouped output (pre-close recordings preferred) ────────────
    # Build per-company view
    company_view = {}
    for r in rows:
        cname = r["company_name"]
        if cname not in company_view:
            company_view[cname] = {
                "contacts": [],
                "links_pre": [],   # before deal close (Discovery/Demo)
                "links_post": [],  # after deal close (onboarding etc.)
                "close_date": r["close_date"],
            }
        entry = company_view[cname]
        contact_label = f"{r['name']} — {r['title']}"
        if contact_label not in entry["contacts"]:
            entry["contacts"].append(contact_label)

        close_ms = r["close_date_ms"]
        for link in r.get("fathom_links", []):
            bucket = "links_pre" if (close_ms and link["ts"] < close_ms) else "links_post"
            if link not in entry[bucket]:
                entry[bucket].append(link)

    # Deduplicate links within each company
    for cname, cv in company_view.items():
        for bucket in ("links_pre", "links_post"):
            seen, unique = set(), []
            for l in sorted(cv[bucket], key=lambda x: x["ts"]):
                if l["url"] not in seen:
                    seen.add(l["url"])
                    unique.append(l)
            cv[bucket] = unique

    print(f"\n{'='*110}")
    print("FINAL OUTPUT — grouped by company, pre-close recordings preferred")
    print(f"{'='*110}")

    companies_with_links = 0
    pad = " " * 92

    for cname, cv in company_view.items():
        pre = cv["links_pre"]
        post = cv["links_post"]

        # Prefer 2 pre-close; fill with post-close if needed
        chosen = pre[:2]
        post_used = []
        if len(chosen) < 2:
            extras = post[:2 - len(chosen)]
            post_used = extras
            chosen += extras

        has_links = bool(chosen)
        if has_links:
            companies_with_links += 1

        print(f"\n{'─'*110}")
        print(f"  Company   : {cname}  (closed {cv['close_date']})")
        for c in cv["contacts"]:
            print(f"  Contact   : {c}")

        if chosen:
            for i, l in enumerate(chosen):
                flag = " [post-close]" if l in post_used else ""
                label = f"  Recording {i+1}: "
                print(f"{label}{l['url']}{flag}")
        else:
            print("  Recordings: No Fathom links found")

    print(f"\n{'='*110}")
    print(f"Companies with Fathom recordings: {companies_with_links} / {len(company_view)}")
    print(f"{'='*110}\n")


if __name__ == "__main__":
    main()
