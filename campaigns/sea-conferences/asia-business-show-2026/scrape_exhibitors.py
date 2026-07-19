"""
Scrape Asia Business Show exhibitor list.

Fetches the main listing page (static HTML, no JS rendering needed), collects
all exhibitor profile slugs, then concurrently visits each profile to extract
company website and LinkedIn URL via JSON-LD structured data.

Output: campaigns/sea-conferences/asia-business-show-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/asia-business-show-2026/scrape_exhibitors.py
"""

import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL    = "https://www.asiabusinessshow.com"
LISTING_URL = "https://www.asiabusinessshow.com/our-exhibitors"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

MAX_WORKERS    = 5
REQUEST_DELAY  = 0.3   # seconds between listing/profile requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_soup(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [warn] Failed to fetch {url}: {e}")
        return None


def parse_json_ld(soup) -> dict:
    """Return the first Organization JSON-LD block found on the page, or {}."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Organization":
                        return item
            elif data.get("@type") == "Organization":
                return data
        except (json.JSONDecodeError, AttributeError):
            continue
    return {}


# ---------------------------------------------------------------------------
# Step 1: Parse listing page → list of {name, profile_url}
# ---------------------------------------------------------------------------

def collect_exhibitors() -> list[dict]:
    print(f"Fetching listing page: {LISTING_URL}")
    soup = get_soup(LISTING_URL)
    if not soup:
        raise RuntimeError("Could not fetch main listing page")

    exhibitors = []
    seen_slugs = set()

    for article in soup.find_all("article", class_=lambda c: c and "m-exhibitors-list__list__items__item" in c):
        link = article.find("a", class_=lambda c: c and "m-exhibitors-list__list__items__item__header__title__link" in c)
        if not link:
            continue

        name = link.get_text(strip=True)
        href = link.get("href", "")
        if not href or not name:
            continue

        slug = href.rstrip("/").split("/")[-1]
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        profile_url = urljoin(BASE_URL, href)
        exhibitors.append({"name": name, "profile_url": profile_url})

    print(f"  Found {len(exhibitors)} exhibitors")
    return exhibitors


# ---------------------------------------------------------------------------
# Step 2: Fetch each profile → extract website + LinkedIn
# ---------------------------------------------------------------------------

def fetch_profile(exhibitor: dict) -> dict:
    name = exhibitor["name"]
    url  = exhibitor["profile_url"]

    soup = get_soup(url)
    if not soup:
        return {"company_name": name, "website": "", "linkedin_url": ""}

    # Website: JSON-LD primary, DOM fallback
    ld = parse_json_ld(soup)
    website = ld.get("url", "")
    if not website:
        btn = soup.find("a", attrs={"aria-label": "Visit website"})
        if btn:
            website = btn.get("href", "")

    # LinkedIn: find the exhibitor-specific link — skip the organizer's tbsasia page
    # which appears in both the header nav and footer on every profile page
    linkedin_url = ""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com" in href and "tbsasia" not in href:
            linkedin_url = href
            break

    return {"company_name": name, "website": website, "linkedin_url": linkedin_url}


def fetch_all_profiles(exhibitors: list[dict]) -> list[dict]:
    total = len(exhibitors)
    print(f"\nFetching {total} profile pages ({MAX_WORKERS} workers)...\n")

    results = [None] * total
    futures = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for i, ex in enumerate(exhibitors):
            time.sleep(REQUEST_DELAY / MAX_WORKERS)
            future = executor.submit(fetch_profile, ex)
            futures[future] = i

        for future in as_completed(futures):
            i = futures[future]
            ex = exhibitors[i]
            try:
                row = future.result()
            except Exception as e:
                print(f"  [error] {ex['name']}: {e}")
                row = {"company_name": ex["name"], "website": "", "linkedin_url": ""}

            results[i] = row
            print(f"  [{i + 1}/{total}] {row['company_name']} | {row['website'] or '—'} | {row['linkedin_url'] or '—'}")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    exhibitors = collect_exhibitors()
    rows = fetch_all_profiles(exhibitors)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "website", "linkedin_url"])
        writer.writeheader()
        writer.writerows(rows)

    with_website  = sum(1 for r in rows if r["website"])
    with_linkedin = sum(1 for r in rows if r["linkedin_url"])
    print(f"\nSummary: {len(rows)} total | {with_website} with website | {with_linkedin} with LinkedIn")
    print(f"Saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
