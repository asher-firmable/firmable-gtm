"""
Scrape Salesforce World Tour Melbourne 2026 sponsor list.

Page structure (confirmed via DOM inspection):
  a[data-analytics-name="view-booth"]
    aria-label = "View Booth {Company Name}"

  .rf-tile-wrapper[data-test="rf-tile-exhibitor-{exhibitorId}"]
    — one tile per sponsor

  Clicking "View Booth" navigates to:
    .../sponsors/page/sponsorcatalog/exhibitor/{exhibitorId}
    — which renders an external link to the company website

Strategy:
  1. Load catalog, dismiss OneTrust overlay
  2. Extract company names from aria-labels + exhibitor IDs from data-test
  3. Navigate each /exhibitor/{id} page, extract first external non-Salesforce link
  4. Write output/exhibitors.csv

Output: campaigns/anz/events-outbound/salesforce-world-tour-melbourne-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/salesforce-world-tour-melbourne-2026/scrape_exhibitors.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CATALOG_URL  = "https://reg.salesforce.com/flow/plus/wtmelbourne26/sponsors/page/sponsorcatalog"
EXHIBITOR_URL = CATALOG_URL + "/exhibitor/{exhibitor_id}"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

EXCLUDE_DOMAINS = {
    "salesforce.com", "reg.salesforce.com",
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com", "onetrust.com",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bare_domain(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def is_company_url(href: str) -> bool:
    if not href or not href.startswith("http"):
        return False
    domain = bare_domain(href)
    return bool(domain) and not any(
        domain == ex or domain.endswith("." + ex) for ex in EXCLUDE_DOMAINS
    )


def dismiss_onetrust(page) -> None:
    try:
        page.evaluate("document.getElementById('onetrust-consent-sdk')?.remove()")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Catalog — extract company names + exhibitor IDs
# ---------------------------------------------------------------------------

def get_exhibitors(page) -> list[dict]:
    """Return list of {name, exhibitor_id} from catalog page."""
    # Get names from aria-labels of "View Booth" buttons
    aria_labels = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[data-analytics-name="view-booth"]'))
                   .map(a => a.getAttribute('aria-label') || '')
    """)

    # Get exhibitor IDs from tile wrapper data-test attributes
    # Format: "rf-tile-exhibitor-{id}"
    exhibitor_ids = page.evaluate("""
        () => Array.from(document.querySelectorAll('[data-test^="rf-tile-exhibitor-"]'))
                   .map(el => el.getAttribute('data-test').replace('rf-tile-exhibitor-', ''))
    """)

    if len(aria_labels) != len(exhibitor_ids):
        print(f"[warn] aria-label count ({len(aria_labels)}) != tile count ({len(exhibitor_ids)}) — zipping by min")

    exhibitors = []
    for label, eid in zip(aria_labels, exhibitor_ids):
        name = label.replace("View Booth ", "").strip()
        exhibitors.append({"name": name, "exhibitor_id": eid})

    return exhibitors


# ---------------------------------------------------------------------------
# Booth page — extract company website
# ---------------------------------------------------------------------------

def get_booth_website(page, exhibitor_id: str) -> str:
    url = EXHIBITOR_URL.format(exhibitor_id=exhibitor_id)
    try:
        page.goto(url, timeout=30000, wait_until="networkidle")
        time.sleep(2)
    except Exception as e:
        print(f"  [warn] load warning: {e} — continuing")
        time.sleep(2)

    dismiss_onetrust(page)

    hrefs = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href]'))
                   .map(a => a.href)
                   .filter(h => h.startsWith('http'))
    """)

    for href in hrefs:
        if is_company_url(href):
            domain = bare_domain(href)
            if domain:
                return "https://" + domain

    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # --- Load catalog ---
        print(f"Loading catalog ...")
        try:
            page.goto(CATALOG_URL, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] {e} — continuing")

        time.sleep(3)
        dismiss_onetrust(page)

        exhibitors = get_exhibitors(page)
        print(f"Found {len(exhibitors)} exhibitors on catalog")
        for i, ex in enumerate(exhibitors, 1):
            print(f"  {i:2d}. {ex['name']} ({ex['exhibitor_id']})")

        # --- Visit each booth page ---
        rows = []
        for i, ex in enumerate(exhibitors, 1):
            name = ex["name"]
            print(f"\n[{i}/{len(exhibitors)}] {name}")
            website = get_booth_website(page, ex["exhibitor_id"])
            print(f"  website: {website or '(none)'}")
            rows.append({"company_name": name, "website": website})

        browser.close()

    # --- Write CSV ---
    with_website = sum(1 for r in rows if r["website"])
    without_website = [r for r in rows if not r["website"]]

    print(f"\nSummary: {len(rows)} sponsors | {with_website} with website | {len(without_website)} without")
    if without_website:
        print("No website found for:")
        for r in without_website:
            print(f"  - {r['company_name']}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "website"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
