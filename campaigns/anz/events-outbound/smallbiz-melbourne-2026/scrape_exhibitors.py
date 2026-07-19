"""
Scrape Small Biz Melbourne 2026 exhibitor list.

Page structure (confirmed via DOM inspection):
  Listing page: https://www.smallbizmelbourne.com.au/exhibit
    - Each exhibitor card contains:
        <h4>Company Name</h4>
        <span>2026</span>  ← year badge; filter to 2026-only
        <nav aria-label="Company social profiles"> ← social links
        <a href="/exhibit/{slug}" aria-label="View Company exhibitor profile">
    - Cards without a "View profile" link only have social links
  Detail page: https://www.smallbizmelbourne.com.au/exhibit/{slug}
    - Contains social links (title="LinkedIn" etc.) + one plain external <a> for website

Steps:
  1. Load listing page with Playwright (JS-rendered)
  2. Parse exhibitor cards: extract name, year badge, and profile slug
  3. Filter to 2026 exhibitors only
  4. Fetch each detail page with requests (concurrent) to extract website URL
  5. Normalize to bare domain
  6. Look up Firmable ID via FirmableClient.lookup_company(domain)
  7. Write output/exhibitors.csv

Output: campaigns/anz/events-outbound/smallbiz-melbourne-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/smallbiz-melbourne-2026/scrape_exhibitors.py
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

LISTING_URL = "https://www.smallbizmelbourne.com.au/exhibit"
PROFILE_BASE = "https://www.smallbizmelbourne.com.au/exhibit"

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

SOCIAL_DOMAINS = {
    "linkedin.com", "instagram.com", "facebook.com",
    "tiktok.com", "twitter.com", "x.com", "youtube.com",
    "smallbizmelbourne.com.au",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def is_social(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)
    except Exception:
        return False


def is_linkedin_company(href: str) -> bool:
    return bool(re.search(r"linkedin\.com/company/|linkedin\.com/showcase/", href, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Step 1: load listing page
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
        # Scroll to trigger any lazy-loaded content
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        html = page.content()
        browser.close()
        print(f"Listing loaded — {len(html):,} bytes")
        return html


# ---------------------------------------------------------------------------
# Step 2: parse exhibitor cards (2026 only)
# ---------------------------------------------------------------------------

def parse_exhibitors(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    exhibitors = []
    seen = set()

    # Each card has an <h4> for the company name and a <span> for the year badge.
    # Walk up from h4 to find the card container, then check year + extract slug.
    for h4 in soup.find_all("h4"):
        name = h4.get_text(strip=True)
        if not name:
            continue

        # Walk up to find the enclosing card div (contains both the badge and profile link)
        card = h4
        for _ in range(6):
            card = card.parent
            if card is None:
                break
            # A card container will have at least the year span inside it
            if card.find("span") and card.find("a"):
                break

        if card is None:
            continue

        # Extract year badge — only keep 2026 exhibitors
        year_span = card.find("span")
        year = year_span.get_text(strip=True) if year_span else ""
        if year != "2026":
            continue

        # Extract slug from "View profile" link
        slug = ""
        for a in card.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/exhibit/") and "View" in (a.get("aria-label") or ""):
                slug = href.split("/exhibit/")[-1].rstrip("/")
                break

        # Deduplicate by name
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        exhibitors.append({"company_name": name, "slug": slug})

    print(f"Found {len(exhibitors)} 2026 exhibitors on listing page")
    return exhibitors


# ---------------------------------------------------------------------------
# Step 3: fetch detail page + extract website + LinkedIn
# ---------------------------------------------------------------------------

def fetch_profile(slug: str, company_name: str) -> dict:
    if not slug:
        return {"website": "", "linkedin_url": ""}

    url = f"{PROFILE_BASE}/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        website = ""
        linkedin_url = ""

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or not href.startswith("http"):
                continue
            if is_linkedin_company(href) and not linkedin_url:
                linkedin_url = href
            elif not is_social(href) and not website:
                website = href

    except Exception as e:
        print(f"[warn] {company_name} ({slug}): {e}")
        return {"website": "", "linkedin_url": ""}

    return {"website": website, "linkedin_url": linkedin_url}


def fetch_all_profiles(exhibitors: list) -> list:
    total = len(exhibitors)
    results = [None] * total

    def fetch_one(idx, ex):
        profile = fetch_profile(ex["slug"], ex["company_name"])
        return idx, {**ex, **profile}

    print(f"Fetching profile pages for {total} exhibitors ...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, i, ex): i for i, ex in enumerate(exhibitors)}
        for done, future in enumerate(as_completed(futures), 1):
            i, result = future.result()
            results[i] = result
            if done % 10 == 0:
                print(f"  {done}/{total} profile pages fetched")

    print("All profile pages fetched")
    return results


# ---------------------------------------------------------------------------
# Step 4: Firmable domain lookup
# ---------------------------------------------------------------------------

def enrich_firmable(exhibitors: list) -> list:
    client = FirmableClient()
    domain_cache = {}

    def enrich_one(ex):
        domain = normalize_domain(ex.get("website", ""))
        ex["domain"] = domain
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
            if done % 10 == 0:
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
            fieldnames=["company_name", "website", "domain", "linkedin_url", "firmable_id"],
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

    exhibitors = parse_exhibitors(html)
    if not exhibitors:
        print("No exhibitors found — check page structure.")
        return

    with_profiles = fetch_all_profiles(exhibitors)
    final = enrich_firmable(with_profiles)

    with_website  = sum(1 for r in final if r.get("website"))
    with_linkedin = sum(1 for r in final if r.get("linkedin_url"))
    with_firmable = sum(1 for r in final if r.get("firmable_id"))
    print(
        f"\nSummary: {len(final)} exhibitors | "
        f"{with_website} with website | "
        f"{with_linkedin} with LinkedIn | "
        f"{with_firmable} with Firmable ID"
    )

    write_csv(final)


if __name__ == "__main__":
    main()
