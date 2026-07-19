"""
Scrape Black Hat US 2026 event sponsor list.

Page: https://blackhat.com/us-26/event-sponsors.html
  - Protected by Cloudflare; requires Playwright (headless Chromium) to render.
  - Sponsors are grouped under h2 tier headings (Titanium, Diamond, Platinum, etc.).
  - Each tier is followed by a table.exhibitorList. Each row has:
      img[alt]  → company name
      hidden div #{id}  → contains a "Website" link with the external URL

Steps:
  1. Load page with Playwright (Cloudflare bypass via full browser render).
  2. Walk h2 headings → find next table.exhibitorList → parse each row:
       company name from img[alt], website from hidden detail div.
  3. Normalize href to a bare domain.
  4. Look up Firmable ID via FirmableClient.lookup_company(domain).
  5. Write output/exhibitors.csv.

Output: campaigns/us/events-outbound/blackhat-us-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py

    # Dump rendered HTML for inspection without running Firmable lookups:
    PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py --debug
"""

import argparse
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scripts.firmable_api import FirmableClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PAGE_URL    = "https://blackhat.com/us-26/event-sponsors.html"
OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"
DEBUG_FILE  = OUTPUT_DIR / "page_debug.html"

MAX_WORKERS = 5

# ---------------------------------------------------------------------------
# Playwright: load page
# ---------------------------------------------------------------------------

def load_page(url):
    print(f"Loading {url} with Playwright ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=90000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] Page load: {e} — continuing with whatever rendered")
        time.sleep(4)
        html = page.content()
        browser.close()
    print(f"Page loaded — {len(html):,} bytes")
    return html


# ---------------------------------------------------------------------------
# Parse sponsor tiers + companies
# ---------------------------------------------------------------------------

def _website_from_detail_div(detail_div):
    """Extract external website URL from the hidden detail div."""
    if not detail_div:
        return ""
    # Find the <strong>Website</strong> tag, then get the next <a>
    strong = detail_div.find("strong", string="Website")
    if not strong:
        return ""
    a = strong.find_next("a", href=True)
    if not a:
        return ""
    href = a.get("href", "").strip()
    # Skip social links (facebook, linkedin, twitter, x.com)
    skip = ("facebook.com", "linkedin.com", "twitter.com", "x.com", "instagram.com")
    if any(s in href for s in skip):
        return ""
    return href


def parse_sponsors(html):
    soup = BeautifulSoup(html, "html.parser")
    sponsors = []
    seen = set()  # (name_lower, tier_lower) dedup

    tier_headings = soup.find_all("h2")
    for h2 in tier_headings:
        tier_name = h2.get_text(strip=True)
        if not tier_name:
            continue

        # The exhibitor table immediately follows the h2
        table = h2.find_next_sibling("table", class_="exhibitorList")
        if not table:
            # Some h2s may not have a table (e.g. page navigation headings)
            continue

        print(f"  [tier] {tier_name}")
        rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")

        for row in rows:
            # Company name from img alt
            img = row.find("img", class_="exhibitor-logo")
            if not img:
                img = row.find("img", alt=True)
            if not img or not img.get("alt", "").strip():
                continue
            company_name = img["alt"].strip()

            # Website from the hidden detail div
            # The div id is referenced by the onclick attribute: showhide('{id}')
            onclick_a = row.find("a", onclick=True)
            detail_div = None
            if onclick_a:
                m = re.search(r"showhide\('([^']+)'\)", onclick_a.get("onclick", ""))
                if m:
                    div_id = m.group(1)
                    detail_div = soup.find("div", id=div_id)
            raw_url = _website_from_detail_div(detail_div)

            key = (company_name.lower(), tier_name.lower())
            if key in seen:
                continue
            seen.add(key)

            sponsors.append({
                "company_name": company_name,
                "raw_url": raw_url,
                "sponsor_type": tier_name,
            })

    print(f"\nFound {len(sponsors)} unique sponsor entries across all tiers")
    return sponsors


# ---------------------------------------------------------------------------
# Domain normalisation
# ---------------------------------------------------------------------------

def normalize_domain(url):
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc
    return re.sub(r"^www\.", "", netloc)


# ---------------------------------------------------------------------------
# Firmable lookup
# ---------------------------------------------------------------------------

def enrich_firmable(sponsors):
    client = FirmableClient()
    domain_cache = {}

    def enrich_one(row):
        domain = row.get("domain", "")
        if not domain:
            return dict(row, firmable_id="")
        if domain not in domain_cache:
            try:
                company = client.lookup_company(domain)
                domain_cache[domain] = (company or {}).get("id", "") or ""
            except Exception as e:
                print(f"[warn] Firmable {domain}: {e}")
                domain_cache[domain] = ""
        return dict(row, firmable_id=domain_cache.get(domain, ""))

    total = len(sponsors)
    results = []
    print(f"Looking up Firmable IDs for {total} sponsors ...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(enrich_one, row) for row in sponsors]
        for done, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if done % 25 == 0:
                print(f"  {done}/{total} lookups done")

    print(f"Firmable lookups complete — {sum(1 for r in results if r['firmable_id'])} IDs found")
    return results


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_sorted = sorted(rows, key=lambda r: (r["sponsor_type"].lower(), r["company_name"].lower()))
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "domain", "sponsor_type", "firmable_id"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows_sorted)
    print(f"\nSaved {len(rows)} rows → {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="Dump rendered HTML to output/page_debug.html and exit (no Firmable lookups)")
    parser.add_argument("--from-cache", action="store_true",
                        help="Skip Playwright load; parse from existing output/page_debug.html")
    args = parser.parse_args()

    if args.from_cache:
        html = DEBUG_FILE.read_text(encoding="utf-8")
        print(f"Using cached HTML from {DEBUG_FILE} ({len(html):,} bytes)")
    else:
        html = load_page(PAGE_URL)

    if args.debug:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        DEBUG_FILE.write_text(html, encoding="utf-8")
        print(f"HTML dumped to {DEBUG_FILE}")
        sys.exit(0)

    sponsors = parse_sponsors(html)
    if not sponsors:
        print("[error] No sponsors found. Run with --debug to inspect the rendered HTML.")
        sys.exit(1)

    for row in sponsors:
        row["domain"] = normalize_domain(row.get("raw_url", ""))

    enriched = enrich_firmable(sponsors)

    with_domain   = sum(1 for r in enriched if r["domain"])
    with_firmable = sum(1 for r in enriched if r["firmable_id"])
    print(f"\nSummary: {len(enriched)} sponsors | {with_domain} with domain | {with_firmable} with Firmable ID")

    write_csv(enriched)


if __name__ == "__main__":
    main()
