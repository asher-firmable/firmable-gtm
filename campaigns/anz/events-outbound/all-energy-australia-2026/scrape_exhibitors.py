"""
Scrape All-Energy Australia 2026 exhibitor directory.

The directory (https://www.all-energy.com.au/en-gb/exhibitor-directory.html#/)
is an RX (Reed Exhibitions) single-page app backed by a public, search-only
Algolia index. The page's own JS queries that index, so we query it directly
with the same app ID / search key and filters — no browser needed. One request
with hitsPerPage=1000 returns every exhibitor for the event edition.

Columns:
- name        exhibitorName (display name), falls back to companyName
- domain      bare domain from the exhibitor's website field
- stand       standReference (e.g. "M113")
- categories  product categories from ppsAnswers, "; "-joined
              (named "categories", not "category", so hubspot_check.py does
              not mistake it for the tier column)
- country     countryName
- is_new      YES if flagged as a first-time exhibitor

Output: campaigns/anz/events-outbound/all-energy-australia-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/all-energy-australia-2026/scrape_exhibitors.py
"""

import csv
from pathlib import Path
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ALGOLIA_APP_ID = "XD0U5M6Y4R"
ALGOLIA_SEARCH_KEY = "d5cd7d4ec26134ff4a34d736a7f9ad47"  # public search-only key embedded in the directory page
ALGOLIA_INDEX = "evt-3d59e8cb-29a1-4f3e-b4a6-f1ea8e984f76-index"
EVENT_EDITION_ID = "eve-7563bade-5112-4c5c-9b48-2460fe1ec0ff"

QUERY_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

FIELDS = ["name", "domain", "stand", "categories", "country", "is_new"]

# Exhibitors with no website in the directory, looked up manually (Oct 2026).
# The remaining blanks (mostly Shaanxi pavilion manufacturers) had no verifiable site.
DOMAIN_OVERRIDES = {
    "LONGi Green Energy Technology Co., Ltd.": "longi.com",
    "REC Traders": "rectraders.com.au",
}


def to_domain(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    netloc = urlparse(url).netloc.lower().split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def fetch_exhibitors() -> list:
    filters = (
        f"recordType:exhibitor AND locale:en-gb AND eventEditionId:{EVENT_EDITION_ID}"
    )
    resp = requests.post(
        QUERY_URL,
        headers={
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY,
        },
        json={"params": f"query=&page=0&hitsPerPage=1000&filters={requests.utils.quote(filters)}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("hits", [])
    if len(hits) != data.get("nbHits"):
        raise RuntimeError(f"Got {len(hits)} hits but nbHits={data.get('nbHits')} — pagination needed")
    return hits


def main():
    hits = fetch_exhibitors()
    rows, seen = [], set()
    for h in hits:
        if h["id"] in seen:
            continue
        seen.add(h["id"])
        name = (h.get("exhibitorName") or h.get("companyName") or "").strip()
        rows.append({
            "name": name,
            "domain": to_domain(h.get("website", "")) or DOMAIN_OVERRIDES.get(name, ""),
            "stand": (h.get("standReference") or "").strip(),
            "categories": "; ".join(h.get("ppsAnswers") or []),
            "country": h.get("countryName", ""),
            "is_new": "YES" if h.get("isNew") else "",
        })
    rows.sort(key=lambda r: r["name"].lower())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    missing = [r["name"] for r in rows if not r["domain"]]
    print(f"Wrote {len(rows)} exhibitors to {OUTPUT_FILE}")
    print(f"{len(missing)} without a website: {', '.join(missing)}")


if __name__ == "__main__":
    main()
