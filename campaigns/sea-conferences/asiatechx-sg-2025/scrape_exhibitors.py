"""
Scrape AsiaTechX Singapore 2025 exhibitor/sponsor list.

Fetches the main listing page (plain HTML), walks through headings to identify
which sub-event each company belongs to, then visits each company's profile
page to extract their website domain from the Contact section.

Output: campaigns/sea-conferences/asiatechx-sg-2025/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/asiatechx-sg-2025/scrape_exhibitors.py
"""

import csv
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
import re

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL     = "https://asiatechxsg.com"
LISTING_URL  = "https://asiatechxsg.com/sponsors/sponsor-exhibitor-list/"
PROFILE_BASE = "/sponsors/sponsors/"

OUTPUT_DIR   = Path(__file__).parent / "output"
OUTPUT_FILE  = OUTPUT_DIR / "exhibitors.csv"

REQUEST_DELAY = 0.5  # seconds between profile page requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Map heading keywords → canonical event name
EVENT_KEYWORDS = [
    ("BroadcastAsia",         "BroadcastAsia"),
    ("CommunicAsia",          "CommunicAsia"),
    ("SatelliteAsia",         "SatelliteAsia"),
    ("TechXLR8Asia",          "TechXLR8Asia"),
    ("AI Summit Singapore",   "The AI Summit Singapore"),
    ("ATxSG",                 "ATxSG"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_event(heading_text: str) -> Optional[str]:
    """Return canonical event name if heading text contains a known keyword."""
    for keyword, event_name in EVENT_KEYWORDS:
        if keyword.lower() in heading_text.lower():
            return event_name
    return None


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def is_linkedin(url: str) -> bool:
    return "linkedin.com" in url.lower()


def get_soup(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[warn] Failed to fetch {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 1: Parse listing page → {slug: {name, event}}
# ---------------------------------------------------------------------------

def parse_listing() -> dict[str, dict]:
    """
    Walk the listing page top-to-bottom. Track current_event from headings;
    collect exhibitor links. Returns dict keyed by slug (deduplicates companies
    that appear under multiple sponsor tiers — first occurrence wins).
    """
    soup = get_soup(LISTING_URL)
    if not soup:
        raise RuntimeError("Could not fetch listing page")

    exhibitors = {}
    current_event = "ATxSG"  # default for any links before a recognised heading

    heading_tags = {"h1", "h2", "h3", "h4"}

    for element in soup.find_all(True):
        tag = element.name

        if tag in heading_tags:
            text = element.get_text(strip=True)
            event = detect_event(text)
            if event:
                current_event = event

        elif tag == "a":
            href = element.get("href", "")
            if href.startswith(PROFILE_BASE):
                slug = href.strip("/").split("/")[-1]
                if slug and slug not in exhibitors:
                    name = element.get_text(strip=True)
                    exhibitors[slug] = {
                        "name": name,
                        "event": current_event,
                        "href": href,
                    }

    return exhibitors


# ---------------------------------------------------------------------------
# Step 2: Fetch each profile page → extract domain
# ---------------------------------------------------------------------------

SOCIAL_DOMAINS = ("linkedin.com", "twitter.com", "x.com", "instagram.com", "facebook.com", "youtube.com")

def is_social(url: str) -> bool:
    return any(d in url.lower() for d in SOCIAL_DOMAINS)


def extract_domain_from_profile(profile_url: str, fallback_name: str):
    """
    Returns (company_name, domain). company_name comes from the first profile <h2>
    that is NOT 'Profile' or 'Contact'; domain comes from the 'Find Out More' link
    in the Contact section (the first non-social link after the Contact <h2>).
    """
    soup = get_soup(profile_url)
    if not soup:
        return fallback_name, ""

    # Use the listing page name — it's the official directory name and avoids
    # profile page noise like "Meet Comtech" or "Find us at the event".
    name = fallback_name

    # Find Contact section: <h2> containing "Contact"
    contact_h2 = None
    for h2 in soup.find_all("h2"):
        if "contact" in h2.get_text(strip=True).lower():
            contact_h2 = h2
            break

    if not contact_h2:
        return name, ""

    # Walk siblings after the Contact h2; find first non-social <a>
    domain = ""
    for sibling in contact_h2.find_next_siblings():
        links = sibling.find_all("a", href=True) if sibling.name != "a" else [sibling]
        for a in links:
            href = a.get("href", "")
            if href and not is_social(href):
                domain = normalize_domain(href)
                break
        if domain:
            break

    return name, domain


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Fetching listing page: {LISTING_URL}")
    exhibitors = parse_listing()
    print(f"Found {len(exhibitors)} unique exhibitors/sponsors on listing page")

    rows = []
    total = len(exhibitors)

    for i, (slug, info) in enumerate(exhibitors.items(), 1):
        profile_url = urljoin(BASE_URL, info["href"])
        print(f"[{i}/{total}] {info['name']} ({info['event']}) → {profile_url}")

        name, domain = extract_domain_from_profile(profile_url, info["name"])
        rows.append({
            "name":   name,
            "domain": domain,
            "event":  info["event"],
        })

        time.sleep(REQUEST_DELAY)

    # Summary
    with_domain = sum(1 for r in rows if r["domain"])
    print(f"\nSummary: {len(rows)} exhibitors | {with_domain} with domain | {len(rows) - with_domain} missing")

    # Write CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "event"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
