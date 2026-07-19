"""
search_fathom_mcp.py

Search HubSpot meetings, notes, and calls from 2026 for any mention of "MCP"
(Model Context Protocol). Extracts Fathom recording links, resolves associated
companies and contacts, then uses Claude to summarise why the prospect wanted MCP
and what their intended use case was.

Usage:
    PYTHONPATH=. python3 scripts/search_fathom_mcp.py
"""

import re
import time
import html
from datetime import datetime, timezone
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from scripts.hubspot_client import HubSpotClient
from scripts.ai import ask_claude

# ── Fathom URL utilities (mirrored from find_senior_contacts.py) ───────────────

FATHOM_RE = re.compile(r'https?://(?:app\.)?fathom\.video/[^\s<>"\')]+', re.IGNORECASE)
MCP_RE = re.compile(r'\bMCP\b|model context protocol|model contact protocol', re.IGNORECASE)

START_MS = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
END_MS   = int(datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)


def normalize_fathom_url(url: str) -> str:
    return html.unescape(url).split("?")[0].split("#")[0]


def extract_fathom_share_links(text: str) -> list:
    urls = [normalize_fathom_url(u.rstrip('.,);')) for u in FATHOM_RE.findall(text or "")]
    return [u for u in urls if "/share/" in u]


def ts_to_ms(ts) -> int:
    if not ts:
        return 0
    try:
        return int(ts)
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def ms_to_date(ms: int) -> str:
    if not ms:
        return "unknown"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


# ── HubSpot retry wrapper ──────────────────────────────────────────────────────

def with_retry(fn, retries=3, backoff=2.0):
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


# ── Search HubSpot objects for MCP ────────────────────────────────────────────

def search_objects_for_mcp(hs: HubSpotClient, obj_type: str, body_prop: str) -> list:
    """
    Returns list of dicts: {id, body, ts_ms, title}
    Searches for "MCP" token in body_prop, filtered to 2026.
    """
    results, after = [], None
    page = 0
    while True:
        payload = {
            "filterGroups": [{
                "filters": [
                    {"propertyName": body_prop, "operator": "CONTAINS_TOKEN", "value": "MCP"},
                    {"propertyName": "hs_createdate", "operator": "GTE", "value": str(START_MS)},
                    {"propertyName": "hs_createdate", "operator": "LTE", "value": str(END_MS)},
                ]
            }],
            "properties": [body_prop, "hs_timestamp", "hs_createdate", "hs_meeting_title"],
            "limit": 100,
        }
        if after:
            payload["after"] = after

        try:
            r = with_retry(lambda p=payload: hs._post(f"/crm/v3/objects/{obj_type}/search", p))
        except Exception as e:
            print(f"  [warn] {obj_type} search failed: {e}")
            break

        items = r.get("results", [])
        page += 1
        print(f"    page {page}: {len(items)} {obj_type} with 'MCP'")

        for item in items:
            props = item.get("properties", {})
            body = props.get(body_prop) or ""
            if not MCP_RE.search(body):
                continue  # skip if "MCP" is only a substring (e.g. SMTP)
            ts_ms = ts_to_ms(props.get("hs_timestamp") or props.get("hs_createdate"))
            title = (props.get("hs_meeting_title") or "").strip()
            results.append({"id": item["id"], "obj_type": obj_type, "body": body, "ts_ms": ts_ms, "title": title})

        after = r.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

    return results


# ── Resolve company + contact for each matching record ────────────────────────

def resolve_associations(hs: HubSpotClient, records: list) -> list:
    """
    For each record, fetch associated company name and primary contact.
    Adds "company", "contact_name", "contact_title" to each record dict.
    """
    by_type = defaultdict(list)
    for r in records:
        by_type[r["obj_type"]].append(r)

    for obj_type, group in by_type.items():
        print(f"  Resolving associations for {len(group)} {obj_type}...")
        for rec in group:
            obj_id = rec["id"]
            company_name, contact_name, contact_title = "Unknown", "", ""

            # Company association
            try:
                assoc = with_retry(lambda oid=obj_id, ot=obj_type: hs._get(
                    f"/crm/v4/objects/{ot}/{oid}/associations/companies"
                ))
                company_ids = [str(r["toObjectId"]) for r in assoc.get("results", [])]
                if company_ids:
                    cid = company_ids[0]
                    c = with_retry(lambda cid=cid: hs._get(f"/crm/v3/objects/companies/{cid}?properties=name"))
                    company_name = c.get("properties", {}).get("name") or "Unknown"
            except Exception:
                pass

            # Contact association
            try:
                assoc = with_retry(lambda oid=obj_id, ot=obj_type: hs._get(
                    f"/crm/v4/objects/{ot}/{oid}/associations/contacts"
                ))
                contact_ids = [str(r["toObjectId"]) for r in assoc.get("results", [])]
                if contact_ids:
                    cid = contact_ids[0]
                    c = with_retry(lambda cid=cid: hs._get(
                        f"/crm/v3/objects/contacts/{cid}?properties=firstname,lastname,jobtitle"
                    ))
                    p = c.get("properties", {})
                    contact_name = f"{p.get('firstname', '')} {p.get('lastname', '')}".strip()
                    contact_title = p.get("jobtitle") or ""
            except Exception:
                pass

            rec["company"] = company_name
            rec["contact_name"] = contact_name
            rec["contact_title"] = contact_title
            time.sleep(0.1)

    return records


# ── Deduplicate by Fathom URL ─────────────────────────────────────────────────

def deduplicate_by_fathom_url(records: list) -> list:
    """
    Extract Fathom share/ links from each record's body. Deduplicate by URL,
    keeping the record with the longest body (most context for summarisation).
    Returns list of dicts with "fathom_url" added.
    """
    url_to_record: dict = {}

    for rec in records:
        links = extract_fathom_share_links(rec["body"])
        if not links:
            # No Fathom link found — still include the record with a blank URL
            # so the MCP mention is surfaced even without a recording
            placeholder = f"__no_fathom_{rec['id']}"
            if placeholder not in url_to_record or len(rec["body"]) > len(url_to_record[placeholder]["body"]):
                rec["fathom_url"] = ""
                url_to_record[placeholder] = rec
        else:
            for url in links:
                if url not in url_to_record or len(rec["body"]) > len(url_to_record[url]["body"]):
                    rec["fathom_url"] = url
                    url_to_record[url] = rec

    return list(url_to_record.values())


# ── Claude summarisation ───────────────────────────────────────────────────────

def summarise_mcp_mention(body: str) -> tuple:
    """
    Returns (why_they_want_mcp, use_case_end_goal) as short strings.
    """
    prompt = f"""Below is a note or transcript excerpt from a sales call. A prospect mentioned MCP (Model Context Protocol).

Extract two things:
1. WHY they want MCP — what pain or need are they expressing? (1-2 sentences)
2. USE CASE / END GOAL — what do they intend to do with it, or what outcome are they trying to achieve? (1-2 sentences)

If the content does not make it clear, say "Not clear from the notes."

Respond in this exact format:
WHY: <answer>
USE CASE: <answer>

---
{body[:4000]}
"""
    try:
        response = ask_claude(prompt)
        why, use_case = "", ""
        for line in response.splitlines():
            if line.startswith("WHY:"):
                why = line[4:].strip()
            elif line.startswith("USE CASE:"):
                use_case = line[9:].strip()
        return why or "Not extracted.", use_case or "Not extracted."
    except Exception as e:
        return f"[Claude error: {e}]", ""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    hs = HubSpotClient()

    search_targets = [
        ("meetings", "hs_internal_meeting_notes"),
        ("notes",    "hs_note_body"),
        ("calls",    "hs_call_body"),
    ]

    all_records = []
    for obj_type, body_prop in search_targets:
        print(f"\nSearching {obj_type} for 'MCP' in 2026...")
        found = search_objects_for_mcp(hs, obj_type, body_prop)
        print(f"  → {len(found)} {obj_type} matched (word-boundary filtered)")
        all_records.extend(found)

    if not all_records:
        print("\nNo HubSpot records found mentioning MCP in 2026.")
        print("Consider broadening search or checking Fathom directly via the API.")
        return

    print(f"\nTotal raw matches: {len(all_records)} — resolving company/contact associations...")
    all_records = resolve_associations(hs, all_records)

    print(f"\nDeduplicating by Fathom URL...")
    unique = deduplicate_by_fathom_url(all_records)
    print(f"  → {len(unique)} unique recordings/mentions")

    print(f"\nSummarising each mention with Claude...\n")

    results_with_links = [r for r in unique if r.get("fathom_url")]
    results_no_links   = [r for r in unique if not r.get("fathom_url")]

    print("=" * 110)
    print(f"MCP MENTIONS IN 2026 FATHOM CALLS — {len(results_with_links)} with recording, {len(results_no_links)} without")
    print("=" * 110)

    for rec in sorted(results_with_links, key=lambda x: x["ts_ms"]):
        why, use_case = summarise_mcp_mention(rec["body"])
        contact_str = rec["contact_name"]
        if rec["contact_title"]:
            contact_str += f" ({rec['contact_title']})"
        date_str = ms_to_date(rec["ts_ms"])
        title_str = f"  Title   : {rec['title']}\n" if rec.get("title") else ""

        print(f"\n{'─' * 110}")
        print(f"  Company : {rec['company']}")
        print(f"  Contact : {contact_str or '—'}")
        print(f"  Date    : {date_str}")
        print(title_str, end="")
        print(f"  Fathom  : {rec['fathom_url']}")
        print(f"  Why MCP : {why}")
        print(f"  Use case: {use_case}")

    if results_no_links:
        print(f"\n{'─' * 110}")
        print(f"MENTIONS WITHOUT A FATHOM LINK ({len(results_no_links)} records):")
        for rec in results_no_links:
            why, use_case = summarise_mcp_mention(rec["body"])
            contact_str = rec["contact_name"]
            if rec["contact_title"]:
                contact_str += f" ({rec['contact_title']})"
            print(f"\n  Company : {rec['company']}  |  Contact : {contact_str or '—'}  |  Date: {ms_to_date(rec['ts_ms'])}")
            print(f"  Why MCP : {why}")
            print(f"  Use case: {use_case}")

    print(f"\n{'=' * 110}")
    print(f"Done. {len(results_with_links)} calls with Fathom links, {len(results_no_links)} without.")
    print(f"{'=' * 110}\n")


if __name__ == "__main__":
    main()
