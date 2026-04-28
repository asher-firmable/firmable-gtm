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


def fetch_fathom_from_meetings(hs: HubSpotClient, contact_to_info: dict) -> dict:
    """
    PULL approach: contact → associated meetings → hs_internal_meeting_notes.
    contact_to_info: {contact_id: {"company_name": str, "close_date_ms": int}}
    Returns: {company_name: [{"url", "ts", "title", "pre_close"}, ...]}
    Only keeps fathom.video/share/ links (invite/ links require login and break for external viewers).
    Results are sorted: pre-close first, then by timestamp ascending.
    """
    from collections import defaultdict

    all_contact_ids = list(contact_to_info.keys())
    print(f"Fetching meetings for {len(all_contact_ids)} contacts...")

    # Step 1: get meeting IDs associated with each contact
    contact_meeting_ids: dict = {}
    for cid in all_contact_ids:
        r = with_retry(lambda c=cid: hs._get(f"/crm/v4/objects/contacts/{c}/associations/meetings"))
        mids = [str(t["toObjectId"]) for t in r.get("results", [])]
        if mids:
            contact_meeting_ids[cid] = mids

    all_meeting_ids = list({mid for mids in contact_meeting_ids.values() for mid in mids})
    print(f"  {len(all_meeting_ids)} unique meetings — reading internal notes...")

    # Step 2: batch read meeting properties
    meeting_data: dict = {}
    for i in range(0, len(all_meeting_ids), 100):
        chunk = all_meeting_ids[i:i + 100]
        r = with_retry(lambda c=chunk: hs._post(
            "/crm/v3/objects/meetings/batch/read",
            {"inputs": [{"id": x} for x in c],
             "properties": ["hs_internal_meeting_notes", "hs_timestamp", "hs_meeting_title", "hs_createdate"]}
        ))
        for m in r.get("results", []):
            meeting_data[m["id"]] = m.get("properties", {})
        time.sleep(0.05)

    # Step 3: extract share/ links only, keyed by company
    company_fathom: dict = defaultdict(list)
    for cid, mids in contact_meeting_ids.items():
        info = contact_to_info[cid]
        cname = info["company_name"]
        close_ms = info["close_date_ms"]
        for mid in mids:
            props = meeting_data.get(mid, {})
            notes = props.get("hs_internal_meeting_notes", "") or ""
            all_urls = [normalize_fathom_url(u) for u in FATHOM_RE.findall(notes)]
            share_urls = [u for u in all_urls if "/share/" in u]
            if not share_urls:
                continue
            ts_ms = ts_to_ms(props.get("hs_timestamp") or props.get("hs_createdate"))
            title = (props.get("hs_meeting_title") or "").strip()
            pre_close = bool(close_ms and ts_ms and ts_ms < close_ms)
            for url in share_urls:
                company_fathom[cname].append({
                    "url": url, "ts": ts_ms, "title": title, "pre_close": pre_close,
                })

    # Step 4: deduplicate and sort (pre-close first, then earliest)
    for cname in company_fathom:
        seen, unique = set(), []
        for l in sorted(company_fathom[cname], key=lambda x: (0 if x["pre_close"] else 1, x["ts"])):
            if l["url"] not in seen:
                seen.add(l["url"])
                unique.append(l)
        company_fathom[cname] = unique

    return dict(company_fathom)


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

    # ── 7. Fetch Fathom links (PULL via contact-associated meetings) ──────────
    print(f"\n{'='*105}")
    print("Pulling Fathom recordings from contact-associated meetings (share/ links only)...")
    print(f"{'='*105}\n")

    # Use ALL contacts at qualifying deals (not just senior) — the AE may have run the call
    qualifying_deal_ids = {r["deal_id"] for r in rows}
    contact_to_info: dict = {}
    for deal_id in qualifying_deal_ids:
        deal_entry = next((e for e in anz_deals if e["deal_id"] == deal_id), None)
        if not deal_entry:
            continue
        for cid in deal_to_contacts.get(deal_id, []):
            contact_to_info[cid] = {
                "company_name": deal_entry["company_name"],
                "close_date_ms": deal_entry["close_date_ms"],
            }

    company_fathom = fetch_fathom_from_meetings(hs, contact_to_info)

    # ── 8. Company-grouped output (pre-close recordings preferred) ────────────
    company_view: dict = {}
    for r in rows:
        cname = r["company_name"]
        if cname not in company_view:
            company_view[cname] = {
                "contacts": [],
                "links": company_fathom.get(cname, []),  # sorted: pre-close first, then by ts
                "close_date": r["close_date"],
            }
        contact_label = f"{r['name']} — {r['title']}"
        if contact_label not in company_view[cname]["contacts"]:
            company_view[cname]["contacts"].append(contact_label)

    print(f"\n{'='*120}")
    print("FINAL OUTPUT — share/ links only, pre-close preferred, with meeting title")
    print(f"{'='*120}")

    companies_with_links = 0

    for cname, cv in company_view.items():
        links = cv["links"]
        pre = [l for l in links if l["pre_close"]]
        post = [l for l in links if not l["pre_close"]]
        chosen = pre[:2]
        if len(chosen) < 2:
            chosen += post[:2 - len(chosen)]

        if chosen:
            companies_with_links += 1

        print(f"\n{'─'*120}")
        print(f"  Company   : {cname}  (closed {cv['close_date']})")
        for c in cv["contacts"]:
            print(f"  Contact   : {c}")

        if chosen:
            for i, l in enumerate(chosen):
                flag = "[pre-close]" if l["pre_close"] else "[post-close]"
                title_str = (l["title"] or "—")[:50]
                print(f"  Recording {i+1}: {flag}  {title_str}")
                print(f"               {l['url']}")
        else:
            print("  Recordings: No share/ Fathom links found")

    print(f"\n{'='*120}")
    print(f"Companies with share/ Fathom recordings: {companies_with_links} / {len(company_view)}")
    print(f"{'='*120}\n")


if __name__ == "__main__":
    main()
