"""
Step 0: Scrape event exhibitors list.

Phase 1: Uses the exhibitors platform POST API to paginate through all exhibitors
         and collect company name + profile URL. Fast, no browser needed.

Phase 2: Uses Playwright to visit each exhibitor profile page (JS-rendered)
         and extract website + LinkedIn URL.

Writes results to data/input/sponsors_raw.csv in the project folder.

Usage:
    python3 workflows/event_outbound/0_scrape_sponsors.py --project projects/event_outbound/_template
    python3 workflows/event_outbound/0_scrape_sponsors.py --project projects/event_outbound/_template --list-only
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


LINKEDIN_RE = re.compile(r"https?://(www\.)?linkedin\.com/company/[^\"'\s/>]+", re.IGNORECASE)
PAGE_SIZE = 100
PROFILE_TIMEOUT = 15000  # ms


# ---------------------------------------------------------------------------
# Phase 1: Paginate exhibitors list via POST API
# ---------------------------------------------------------------------------

def build_api_url(exhibitors_url):
    """Turn the exhibitors listing URL into the fetchExhibitors API endpoint."""
    base = exhibitors_url.rstrip("/")
    return base + "/fetchExhibitors"


def fetch_exhibitor_page(api_url, start, limit=PAGE_SIZE):
    data = {
        "limit": limit,
        "start": start,
        "keyword_search": "",
        "product_search": "",
        "cuntryId": "",
        "event_prod_cat_id": "",
        "exb_listed_as": "",
        "InitialKey": "",
        "selected_event_id": "",
        "start_up_exhibitors": "",
        "pav_country_id": "",
        "type": "",
        "vacancies": "",
        "new_category": "",
        "new_sub_category": "",
        "new_sub_sub_category": "",
        "event_sector_value": "",
    }
    resp = requests.post(api_url, data=data, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_exhibitor_cards(html, base_url):
    """Extract (company_name, profile_url) from API response HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.list-group-item")
    results = []
    for card in cards:
        name_tag = card.select_one("h4.heading")
        name = name_tag.get_text(strip=True) if name_tag else ""

        link_tag = card.select_one("a.btn")
        href = link_tag["href"] if link_tag and link_tag.get("href") else ""
        if href and not href.startswith("http"):
            href = urljoin(base_url, href)

        if name and href:
            results.append({"company_name": name, "profile_url": href})

    return results


def get_all_exhibitors(exhibitors_url):
    api_url = build_api_url(exhibitors_url)
    base_url = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(exhibitors_url))
    all_exhibitors = []
    start = 0

    print("Fetching exhibitor list from API...")
    while True:
        print(f"  Fetching records {start}–{start + PAGE_SIZE - 1} ...", end=" ", flush=True)
        html = fetch_exhibitor_page(api_url, start)
        batch = parse_exhibitor_cards(html, base_url)
        if not batch:
            print("done (no more results)")
            break
        all_exhibitors.extend(batch)
        print(f"{len(batch)} found (total: {len(all_exhibitors)})")
        start += PAGE_SIZE
        time.sleep(0.3)

    return all_exhibitors


# ---------------------------------------------------------------------------
# Phase 2: Visit each profile page with Playwright to get website + LinkedIn
# ---------------------------------------------------------------------------

def scrape_profile(page, profile_url):
    """Visit a profile page and extract website + LinkedIn URL."""
    website = ""
    linkedin = ""
    try:
        page.goto(profile_url, timeout=PROFILE_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)  # let JS render
        content = page.content()

        # LinkedIn: look for linkedin.com/company link
        match = LINKEDIN_RE.search(content)
        if match:
            linkedin = match.group(0).rstrip("/")

        # Website: find "VISIT WEBSITE" link
        soup = BeautifulSoup(content, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).upper()
            href = a["href"]
            if "VISIT WEBSITE" in text and href.startswith("http") and "linkedin.com" not in href:
                website = href
                break

    except Exception as e:
        print(f"[warn] {profile_url}: {e}")

    return website, linkedin


def enrich_with_profiles(exhibitors, list_only=False):
    if list_only:
        for ex in exhibitors:
            ex["website"] = ""
            ex["linkedin_url"] = ""
        return exhibitors

    print(f"\nVisiting {len(exhibitors)} profile pages for website + LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        profile_page = context.new_page()

        for i, ex in enumerate(exhibitors):
            print(f"  [{i+1}/{len(exhibitors)}] {ex['company_name']} ...", end=" ", flush=True)
            website, linkedin = scrape_profile(profile_page, ex["profile_url"])
            ex["website"] = website
            ex["linkedin_url"] = linkedin
            found = []
            if website:
                found.append("website")
            if linkedin:
                found.append("linkedin")
            print(", ".join(found) if found else "nothing found")
            time.sleep(0.3)

        browser.close()

    return exhibitors


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(exhibitors, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["company_name", "website", "linkedin_url", "profile_url"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(exhibitors)
    print(f"\nSaved {len(exhibitors)} rows to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape event exhibitors")
    parser.add_argument("--project", required=True, help="Path to project folder")
    parser.add_argument("--list-only", action="store_true",
                        help="Only fetch the exhibitor list, skip profile page visits")
    args = parser.parse_args()

    project_path = Path(args.project)
    config_path = project_path / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    exhibitors_url = config.get("exhibitors_url")
    if not exhibitors_url:
        raise ValueError("exhibitors_url is not set in config.json")

    # Phase 1: get full list
    exhibitors = get_all_exhibitors(exhibitors_url)
    print(f"\nTotal exhibitors found: {len(exhibitors)}")

    # Phase 2: enrich with website + LinkedIn from profile pages
    exhibitors = enrich_with_profiles(exhibitors, list_only=args.list_only)

    # Stats
    website_count = sum(1 for e in exhibitors if e["website"])
    linkedin_count = sum(1 for e in exhibitors if e["linkedin_url"])
    print(f"Summary: {len(exhibitors)} exhibitors | {website_count} websites | {linkedin_count} LinkedIn URLs")

    output_path = project_path / "data" / "input" / "sponsors_raw.csv"
    write_csv(exhibitors, output_path)


if __name__ == "__main__":
    main()
