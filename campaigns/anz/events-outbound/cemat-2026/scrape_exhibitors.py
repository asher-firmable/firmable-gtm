"""
Scrape CEMAT 2026 exhibitor list.

Page structure (confirmed via DOM inspection):
  Listing page: https://www.cemat.com.au/2026-exhibitor-list
    - Each exhibitor card has two <a> tags sharing the same openRemoteModal() href:
      one wrapping the logo image, one containing the company name text.
    - Slug is embedded as the first argument: openRemoteModal('exhibitors-backend/{slug}',...)
  Detail page: https://www.cemat.com.au/exhibitors-backend/{slug}
    - Contains: <a href="https://..." target="_blank">Visit website (opens in a new tab)</a>

Steps:
  1. Load listing page with Playwright (JS-rendered)
  2. Extract slug + company name pairs via BeautifulSoup
  3. Fetch each detail page with requests (concurrent, ThreadPoolExecutor)
  4. Parse website URL from "Visit website" link
  5. Normalize to bare domain
  6. Look up Firmable ID via FirmableClient.lookup_company(domain)
  7. Write output/exhibitors.csv

Output: campaigns/anz/events-outbound/cemat-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/cemat-2026/scrape_exhibitors.py
"""

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scripts.firmable_api import FirmableClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LISTING_URL = "https://www.cemat.com.au/2026-exhibitor-list"
DETAIL_BASE = "https://www.cemat.com.au/exhibitors-backend"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

MAX_WORKERS = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SLUG_RE = re.compile(r"openRemoteModal\('(exhibitors-backend/[^']+)'")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return re.sub(r"^www\.", "", urlparse(url).netloc)


# ---------------------------------------------------------------------------
# Step 1: load listing page with Playwright
# ---------------------------------------------------------------------------

def load_listing(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()
        print(f"Loading {url} ...")
        try:
            page.goto(url, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] Page load: {e} — continuing")
        time.sleep(3)
        html = page.content()
        browser.close()
        print(f"Listing loaded — {len(html):,} bytes")
        return html


# ---------------------------------------------------------------------------
# Step 2: extract slug + company name from listing HTML
# ---------------------------------------------------------------------------

def extract_exhibitors(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    exhibitors = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        m = SLUG_RE.search(href)
        if not m:
            continue
        slug = m.group(1).split("/", 1)[-1]  # strip 'exhibitors-backend/' prefix
        name = a.get_text(strip=True)
        if not name or slug in seen:
            continue
        seen.add(slug)
        exhibitors.append({"slug": slug, "company_name": name})

    print(f"Found {len(exhibitors)} unique exhibitors on listing page")
    return exhibitors


# ---------------------------------------------------------------------------
# Step 3: fetch detail page + extract website URL
# ---------------------------------------------------------------------------

def fetch_website(slug: str) -> str:
    url = f"{DETAIL_BASE}/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if "Visit website" in a.get_text():
                return a["href"]
    except Exception as e:
        print(f"[warn] {slug}: {e}")
    return ""


def fetch_all_details(exhibitors: list) -> list:
    total = len(exhibitors)
    results = [None] * total

    def fetch_one(idx, ex):
        website = fetch_website(ex["slug"])
        return idx, {**ex, "domain": normalize_domain(website)}

    print(f"Fetching detail pages for {total} exhibitors ...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, i, ex): i for i, ex in enumerate(exhibitors)}
        for done, future in enumerate(as_completed(futures), 1):
            i, result = future.result()
            results[i] = result
            if done % 25 == 0:
                print(f"  {done}/{total} detail pages fetched")

    print("All detail pages fetched")
    return results


# ---------------------------------------------------------------------------
# Step 4: Firmable domain → ID lookup
# ---------------------------------------------------------------------------

def enrich_firmable(exhibitors: list) -> list:
    client = FirmableClient()
    domain_cache = {}

    def enrich_one(ex):
        domain = ex.get("domain", "")
        if not domain:
            return {**ex, "firmable_id": ""}
        if domain not in domain_cache:
            try:
                company = client.lookup_company(domain)
                domain_cache[domain] = (company or {}).get("id", "") or ""
            except Exception as e:
                print(f"[warn] Firmable {domain}: {e}")
                domain_cache[domain] = ""
        return {**ex, "firmable_id": domain_cache.get(domain, "")}

    total = len(exhibitors)
    results = []
    print(f"Looking up Firmable IDs for {total} exhibitors ...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(enrich_one, ex) for ex in exhibitors]
        for done, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if done % 25 == 0:
                print(f"  {done}/{total} Firmable lookups done")

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_sorted = sorted(rows, key=lambda r: r["company_name"].lower())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "domain", "firmable_id"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows_sorted)
    print(f"Saved {len(rows)} rows → {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    html = load_listing(LISTING_URL)

    exhibitors = extract_exhibitors(html)
    if not exhibitors:
        print("No exhibitors found — check page structure.")
        return

    with_details = fetch_all_details(exhibitors)
    final = enrich_firmable(with_details)

    with_domain   = sum(1 for r in final if r["domain"])
    with_firmable = sum(1 for r in final if r["firmable_id"])
    print(f"\nSummary: {len(final)} exhibitors | {with_domain} with domain | {with_firmable} with Firmable ID")

    write_csv(final)


if __name__ == "__main__":
    main()
