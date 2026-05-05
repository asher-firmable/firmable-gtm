"""
Scrape HR Tech Festival Asia 2026 sponsor/exhibitor list.

Fetches the main listing page and iterates A-Z pagination to collect all
exhibitor slugs, then visits each profile page to extract the company website
domain from the Contact section.

Output: campaigns/sea-conferences/hr-tech-festival-asia-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/hr-tech-festival-asia-2026/scrape_exhibitors.py
"""

import csv
import string
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import re

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL         = "https://www.hrtechfestivalasia.com"
LISTING_URL      = "https://www.hrtechfestivalasia.com/sponsors-partners"
PROFILE_URL_BASE = "https://www.hrtechfestivalasia.com/exhibitors/"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

REQUEST_DELAY  = 0.5   # seconds between profile page requests
AZ_PAGE_DELAY  = 0.3   # seconds between A-Z listing pages

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Ordered so more specific matches (e.g. "gold") come before generic ones
TIER_KEYWORDS = [
    ("gold",        "Gold Sponsor"),
    ("silver",      "Silver Sponsor"),
    ("bronze",      "Bronze Sponsor"),
    ("startup",     "Startup"),
    ("tabletop",    "Tabletop Showcase"),
    ("supporting",  "Supporting Partner"),
    ("exhibitor",   "Exhibitor"),
]

# Links to exclude: social media + event organizer/platform domains present on every page
EXCLUDED_DOMAINS = (
    "linkedin.com", "twitter.com", "x.com",
    "instagram.com", "facebook.com", "youtube.com",
    "hrmasia.com", "hrtechfestivalasia.com",
    "hrtechnologyconference.com", "hrtechnologyeurope.com",
    "asp.events", "hsforms.com", "wa.me",
)

URL_SHORTENERS = ("bit.ly", "tinyurl.com", "ow.ly", "t.co")


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


def resolve_shortener(url: str) -> str:
    """Follow redirect for known URL shorteners; return final URL (or original on failure)."""
    if not any(s in url.lower() for s in URL_SHORTENERS):
        return url
    try:
        resp = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        return resp.url
    except Exception:
        return url


def get_soup(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[warn] Failed to fetch {url}: {e}")
        return None


def detect_tier(heading_text: str) -> Optional[str]:
    text = heading_text.lower()
    for keyword, tier_name in TIER_KEYWORDS:
        if keyword in text:
            return tier_name
    return None


# ---------------------------------------------------------------------------
# Step 1: Parse listing pages → {slug: {name, tier}}
# ---------------------------------------------------------------------------

def parse_exhibitors_from_soup(soup, default_tier: str = "Exhibitor") -> dict[str, dict]:
    """Walk DOM top-to-bottom; track current tier from headings; collect exhibitor links."""
    exhibitors = {}
    current_tier = default_tier

    for element in soup.find_all(True):
        tag = element.name

        if tag in ("h1", "h2", "h3", "h4"):
            tier = detect_tier(element.get_text(strip=True))
            if tier:
                current_tier = tier

        elif tag == "a":
            href = element.get("href", "")
            if not href or "exhibitors/" not in href:
                continue

            slug = href.rstrip("/").split("/")[-1]
            if not slug or slug in exhibitors:
                continue

            # Prefer <h3> inside the link, then logo alt text, then link text
            name = ""
            h3 = element.find("h3")
            if h3:
                name = h3.get_text(strip=True)
            if not name:
                img = element.find("img")
                if img:
                    name = img.get("alt", "").strip()
            if not name:
                name = element.get_text(strip=True)

            if name:
                exhibitors[slug] = {"name": name, "tier": current_tier, "href": href}

    return exhibitors


def collect_all_slugs() -> dict[str, dict]:
    """Fetch main page + every A-Z letter page; return deduplicated exhibitors keyed by slug."""
    print(f"Fetching main page: {LISTING_URL}")
    soup = get_soup(LISTING_URL)
    if not soup:
        raise RuntimeError("Could not fetch main listing page")

    all_exhibitors = parse_exhibitors_from_soup(soup)
    print(f"  Main page: {len(all_exhibitors)} exhibitors found")

    # A-Z pages catch Supporting Partners that may not appear on the unfiltered page
    for letter in list(string.digits + string.ascii_uppercase):
        time.sleep(AZ_PAGE_DELAY)
        url = f"{LISTING_URL}?azletter={letter}"
        soup = get_soup(url)
        if not soup:
            continue

        page_exhibitors = parse_exhibitors_from_soup(soup, default_tier="Supporting Partner")
        new_count = sum(1 for s in page_exhibitors if s not in all_exhibitors)
        for slug, info in page_exhibitors.items():
            if slug not in all_exhibitors:
                all_exhibitors[slug] = info

        if new_count:
            print(f"  [{letter}]: +{new_count} new (total {len(all_exhibitors)})")

    return all_exhibitors


# ---------------------------------------------------------------------------
# Step 2: Fetch each profile page → extract domain
# ---------------------------------------------------------------------------

def extract_domain_from_profile(slug: str, fallback_name: str) -> tuple:
    """Return (name, domain). Uses the listing-page name to avoid profile page noise."""
    url = f"{PROFILE_URL_BASE}{slug}"
    soup = get_soup(url)
    if not soup:
        return fallback_name, ""

    # Strategy 1: find the Contact section heading, then first external non-social link
    contact_heading = None
    for tag_name in ("h2", "h3", "h4"):
        for heading in soup.find_all(tag_name):
            if "contact" in heading.get_text(strip=True).lower():
                contact_heading = heading
                break
        if contact_heading:
            break

    if contact_heading:
        for sibling in contact_heading.find_next_siblings():
            links = sibling.find_all("a", href=True) if sibling.name != "a" else [sibling]
            for a in links:
                href = resolve_shortener(a.get("href", ""))
                if href.startswith("http") and not is_excluded(href):
                    return fallback_name, normalize_domain(href)

    # Strategy 2: any external non-excluded link on the page
    for a in soup.find_all("a", href=True):
        href = resolve_shortener(a.get("href", ""))
        if href.startswith("http") and not is_excluded(href):
            return fallback_name, normalize_domain(href)

    return fallback_name, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape() -> list[dict]:
    all_exhibitors = collect_all_slugs()
    total = len(all_exhibitors)
    print(f"\nTotal unique exhibitors/sponsors: {total}")
    print("Fetching profile pages for domains...\n")

    rows = []
    for i, (slug, info) in enumerate(all_exhibitors.items(), 1):
        print(f"[{i}/{total}] {info['name']} ({info['tier']})")
        name, domain = extract_domain_from_profile(slug, info["name"])
        rows.append({"name": name, "domain": domain, "tier": info["tier"]})
        time.sleep(REQUEST_DELAY)

    return rows


def write_csv(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "tier"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows → {OUTPUT_FILE}")


def main():
    rows = scrape()
    with_domain = sum(1 for r in rows if r["domain"])
    print(f"\nSummary: {len(rows)} total | {with_domain} with domain | {len(rows) - with_domain} missing")
    write_csv(rows)


if __name__ == "__main__":
    main()
