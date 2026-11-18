"""
Scrape CyberCon Melbourne 2026 sponsors page.

The page (https://melbourne2026.cyberconference.com.au/sponsors) is a
server-rendered Webflow site, so a plain requests fetch returns full HTML.
Sponsors are grouped under tier headings (Ruby / Diamond / Platinum / Gold /
Silver / Bronze Exhibitors, Startup, and a final "Sponsors" section for
special-category sponsors e.g. Welcome Reception, Lanyards). Each sponsor is
a logo link to /sponsors/<slug> — company names come from the logo's alt
text, tiers from the nearest preceding <h2>.

The listing page has no external website links, so each unique sponsor's
detail page (/sponsors/<slug>) is fetched separately to pull the "Visit
<Company>" button href.

A few companies appear in both a paid tier and the special-category
"Sponsors" section (e.g. Cloudflare, Darktrace) — deduped by slug, keeping
the first (highest) tier encountered in document order.

Output: campaigns/anz/events-outbound/cybercon-melbourne-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/cybercon-melbourne-2026/scrape_exhibitors.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://melbourne2026.cyberconference.com.au"
SPONSORS_URL = f"{BASE_URL}/sponsors"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 0.4

TIER_HEADINGS = {
    "Ruby Exhibitors": "Ruby",
    "Diamond Exhibitors": "Diamond",
    "Platinum Exhibitors": "Platinum",
    "Gold Exhibitors": "Gold",
    "Silver Exhibitors": "Silver",
    "Bronze Exhibitors": "Bronze",
    "Startup": "Startup",
    "Sponsors": "Special Category",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape_listing() -> list:
    """Walk the sponsors page in document order, tagging each sponsor with
    its nearest preceding tier heading. Dedupe by slug, first occurrence wins."""
    soup = get_soup(SPONSORS_URL)
    body = soup.body

    tier = ""
    seen_slugs = set()
    results = []

    for el in body.find_all(["h2", "a"]):
        if el.name == "h2":
            heading = el.get_text(strip=True)
            if heading in TIER_HEADINGS:
                tier = TIER_HEADINGS[heading]
            continue

        href = el.get("href", "")
        if not href.startswith("/sponsors/"):
            continue

        slug = href.split("/sponsors/")[-1].strip("/")
        if not slug or slug in seen_slugs:
            continue

        img = el.find("img")
        name = img.get("alt", "").strip() if img else ""
        if not name:
            continue

        seen_slugs.add(slug)
        results.append({"name": name, "slug": slug, "tier": tier})

    return results


def get_sponsor_website(slug: str) -> str:
    """Fetch a sponsor's detail page and return their external website URL,
    taken from the 'Visit <Company>' button link."""
    try:
        soup = get_soup(f"{BASE_URL}/sponsors/{slug}")
    except requests.RequestException as e:
        print(f"  [warn] failed to load detail page for {slug}: {e}")
        return ""

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not href.startswith("http"):
            continue
        if text.lower().startswith("visit"):
            return href

    return ""


def scrape() -> list:
    print(f"Loading {SPONSORS_URL} ...")
    sponsors = scrape_listing()
    print(f"Found {len(sponsors)} unique sponsors across all tiers.\n")

    results = []
    for i, s in enumerate(sponsors, 1):
        print(f"[{i}/{len(sponsors)}] {s['name']} ({s['tier']}) ...", end=" ", flush=True)
        website = get_sponsor_website(s["slug"])
        domain = normalize_domain(website)
        print(domain or "NO DOMAIN FOUND")

        results.append({
            "name": s["name"],
            "domain": domain,
            "tier": s["tier"],
        })
        time.sleep(REQUEST_DELAY)

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "tier"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows -> {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = scrape()

    if not rows:
        print("No data scraped.")
        return

    domain_count = sum(1 for r in rows if r["domain"])
    print(f"\nSummary: {len(rows)} sponsors | {domain_count} with domain | {len(rows) - domain_count} missing")

    write_csv(rows)


if __name__ == "__main__":
    main()
