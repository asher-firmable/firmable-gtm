"""
Scrape Tech Week Singapore 2026 exhibitor/sponsor list.

Listing pages are server-rendered (ASP.events "SHOWOFF" platform), 50 items per
page across 16 pages. Each exhibitor card links to a detail page with a labeled
"Website" link used to resolve the company domain.

Output: campaigns/sea-conferences/tech-week-singapore-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/tech-week-singapore-2026/scrape_exhibitors.py
"""

import csv
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL    = "https://www.singaporetechnologyweek.com"
LISTING_URL = f"{BASE_URL}/exhibitor-list-2026"
TOTAL_PAGES = 17

LISTING_PARAMS = {
    "filters.events": (
        "Big Data & AI World Asia,Cloud & AI Infrastructure,"
        "Cyber Security World Asia,Data Centre World Asia,Devops Live"
    ),
    "sortby": "title asc ,title asc",
    "azLetterField": "trading-name",
}

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

PAGE_DELAY    = 0.3
PROFILE_DELAY = 0.3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIER_LABELS = [
    "Diamond Sponsor", "Platinum Sponsor", "VIP Lounge Sponsor",
    "Theatre Sponsor", "Mainstage Sponsor", "Knowledge Partner",
    "Gold Sponsor", "Delegate Sponsor", "Executive Lunch Sponsor",
    "Lunch Host", "Coffee Point Sponsor", "Exhibitor",
]

EXCLUDED_DOMAINS = (
    "linkedin.com", "twitter.com", "x.com", "instagram.com",
    "facebook.com", "youtube.com", "asp.events",
    "singaporetechnologyweek.com", "closerstillmedia.com",
    "hsforms.com", "wa.me",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def is_excluded(url: str) -> bool:
    return any(d in url.lower() for d in EXCLUDED_DOMAINS)


def get_soup(url: str, params: Optional[dict] = None):
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[warn] Failed to fetch {url}: {e}")
        return None


def detect_tier(status_span_text: str) -> str:
    text = status_span_text.strip()
    for label in TIER_LABELS:
        if label.lower() in text.lower():
            return label
    return text or "Exhibitor"


# ---------------------------------------------------------------------------
# Step 1: Collect exhibitor cards from all listing pages
# ---------------------------------------------------------------------------

def detect_total_pages(soup) -> int:
    """Read the pagination widget to find the last page number (list grows over time)."""
    page_numbers = [
        int(a.get_text(strip=True))
        for a in soup.select(".pagination__list__item__link")
        if a.get_text(strip=True).isdigit()
    ]
    return max(page_numbers) if page_numbers else TOTAL_PAGES


def collect_all_exhibitors() -> Dict[str, dict]:
    exhibitors: Dict[str, dict] = {}

    first_soup = get_soup(LISTING_URL, params={"page": 1, **LISTING_PARAMS})
    if not first_soup:
        raise RuntimeError("Could not fetch main listing page")
    total_pages = detect_total_pages(first_soup)
    print(f"Detected {total_pages} listing pages")

    for page in range(1, total_pages + 1):
        if page == 1:
            soup = first_soup
        else:
            params = {"page": page, **LISTING_PARAMS}
            soup = get_soup(LISTING_URL, params=params)
        if not soup:
            continue

        cards = soup.select("li.m-exhibitors-list__items__item")
        new_count = 0
        for card in cards:
            slug = (card.get("data-href") or "").strip()
            if not slug:
                continue

            title_el = card.select_one(".m-exhibitors-list__items__item__header__title")
            name = title_el.get_text(strip=True) if title_el else ""
            if not name:
                img = card.select_one("img")
                name = img.get("alt", "").strip() if img else ""
            if not name:
                continue

            status_el = card.select_one(".m-exhibitors-list__items__item__header__status__item")
            tier = detect_tier(status_el.get_text(strip=True)) if status_el else "Exhibitor"

            stand_el = card.select_one(".m-exhibitors-list__items__item__header__meta__stand")
            stand = stand_el.get_text(strip=True).replace("Stand:", "").strip() if stand_el else ""

            if slug not in exhibitors:
                exhibitors[slug] = {"name": name, "tier": tier, "stand": stand}
                new_count += 1

        print(f"[page {page}/{total_pages}] {len(cards)} cards, +{new_count} new (total {len(exhibitors)})")
        time.sleep(PAGE_DELAY)

    return exhibitors


# ---------------------------------------------------------------------------
# Step 2: Visit each detail page → resolve website domain
# ---------------------------------------------------------------------------

def extract_domain(slug: str) -> str:
    url = f"{BASE_URL}/{slug}"
    soup = get_soup(url)
    if not soup:
        return ""

    website_div = soup.select_one(".m-exhibitor-entry__item__body__contacts__additional__website")
    if website_div:
        a = website_div.find("a", href=True)
        if a:
            href = a["href"].strip()
            if href.startswith("http") and not is_excluded(href):
                return normalize_domain(href)

    # Fallback: first external non-excluded link on the page
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("http") and not is_excluded(href):
            return normalize_domain(href)

    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape() -> List[dict]:
    print("Collecting exhibitor cards...")
    exhibitors = collect_all_exhibitors()
    total = len(exhibitors)
    print(f"\nTotal unique exhibitors/sponsors: {total}")
    print("Fetching detail pages for domains...\n")

    rows = []
    for i, (slug, info) in enumerate(exhibitors.items(), 1):
        domain = extract_domain(slug)
        print(f"[{i}/{total}] {info['name']} ({info['tier']}) ... {domain or 'NO DOMAIN FOUND'}")
        rows.append({
            "name": info["name"],
            "domain": domain,
            "tier": info["tier"],
            "stand": info["stand"],
        })
        time.sleep(PROFILE_DELAY)

    return rows


def write_csv(rows: List[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "tier", "stand"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows -> {OUTPUT_FILE}")


def main():
    rows = scrape()
    with_domain = sum(1 for r in rows if r["domain"])
    print(f"\nSummary: {len(rows)} total | {with_domain} with domain | {len(rows) - with_domain} missing")
    write_csv(rows)


if __name__ == "__main__":
    main()
