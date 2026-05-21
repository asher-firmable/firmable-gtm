"""
Scrape FH Week 2026 exhibitor list.

Page structure (confirmed via DOM inspection):
  .exhibitor-card          — one per exhibitor (1,900 on the page)
    .exhibitor-name        — company name text
    .exhibitor-links       — contains website + social links as <a href>

Loads with Playwright (handles any lazy-loading), then parses with BeautifulSoup.

Output: campaigns/anz/events-outbound/fhweek-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/fhweek-2026/scrape_exhibitors.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_URL = "https://fhweek.com.au/exhibiting-brands/"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

SOCIAL_DOMAINS = {
    "linkedin.com", "instagram.com", "facebook.com",
    "tiktok.com", "twitter.com", "x.com", "youtube.com",
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


def is_social(href: str) -> bool:
    try:
        host = urlparse(href).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)
    except Exception:
        return False


def is_linkedin_company(href: str) -> bool:
    return bool(re.search(r"linkedin\.com/company/", href, re.IGNORECASE))


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------------------
# Page load + scroll
# ---------------------------------------------------------------------------

def load_page(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"Loading {url} ...")
        try:
            # networkidle ensures the JS filter has run before we snapshot the DOM
            page.goto(url, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] Page load warning: {e} — continuing")

        # Extra buffer for the filter JS to finish applying .filtered classes
        time.sleep(5)

        html = page.content()
        browser.close()
        print(f"Page loaded — {len(html):,} bytes of HTML")
        return html


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    # Only select cards with the .filtered class — JS adds this to visible cards
    # and removes it from hidden ones after applying the default event filter
    cards = soup.select(".exhibitor-card.filtered")
    print(f"Found {len(cards)} visible exhibitor cards")

    rows = []
    seen = set()

    for card in cards:
        # Company name
        name_el = card.select_one(".exhibitor-name")
        name = clean_text(name_el.get_text()) if name_el else ""

        # Links — prefer .exhibitor-links section; fall back to all links in card
        links_section = card.select_one(".exhibitor-links")
        link_els = (links_section or card).find_all("a", href=True)

        website = ""
        linkedin_url = ""

        for a in link_els:
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            if is_linkedin_company(href) and not linkedin_url:
                linkedin_url = href
            elif not is_social(href) and not website:
                website = href

        if not name:
            continue

        # Deduplicate by domain AND name — skip if either was seen before
        domain_key = bare_domain(website)
        name_key = name.lower()
        if (domain_key and domain_key in seen) or name_key in seen:
            continue
        if domain_key:
            seen.add(domain_key)
        seen.add(name_key)

        rows.append({"company_name": name, "website": website, "linkedin_url": linkedin_url})

    return rows


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "website", "linkedin_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows → {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    html = load_page(TARGET_URL)
    rows = parse_html(html)

    if not rows:
        print("No data extracted. Check the page structure.")
        return

    with_website  = sum(1 for r in rows if r["website"])
    with_linkedin = sum(1 for r in rows if r["linkedin_url"])
    print(f"\nSummary: {len(rows)} exhibitors | {with_website} with website | {with_linkedin} with LinkedIn")

    write_csv(rows)


if __name__ == "__main__":
    main()
