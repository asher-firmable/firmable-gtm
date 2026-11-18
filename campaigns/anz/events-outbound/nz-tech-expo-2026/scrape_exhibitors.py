"""
Scrape NZ Tech Expo 2026 companies page.

The page is a client-rendered React SPA (https://nztechexpo.co.nz/companies) —
a plain requests fetch returns an empty shell, so Playwright is used to render
it. Each exhibitor is a logo wrapped in <a href="..."><img alt="Company Name">,
grouped under section headings (PARTNERS / SPONSORS / Companies you will meet /
Supporters). Several logos (mostly Partners) are re-shown a second time inside
the main Companies grid as featured highlights — deduped here by (name, href).

Output: campaigns/anz/events-outbound/nz-tech-expo-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/nz-tech-expo-2026/scrape_exhibitors.py
"""

import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PARENT_URL = "https://nztechexpo.co.nz/companies"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

PAGE_LOAD_WAIT_MS = 3000

SITE_LOGO_ALT = "NZ Tech Expo"
CATEGORY_HEADINGS = {
    "PARTNERS": "Partner",
    "SPONSORS": "Sponsor",
    "Companies you will meet": "Company",
    "Supporters": "Supporter",
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


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape() -> list:
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

        print(f"Loading {PARENT_URL} ...")
        try:
            page.goto(PARENT_URL, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] networkidle timed out: {e} — continuing")

        page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

        # Walk the DOM in order, tagging each exhibitor logo with the nearest
        # preceding section heading.
        sequence = page.evaluate(
            """
            () => {
                const out = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let node;
                while (node = walker.nextNode()) {
                    if (/^H[1-4]$/.test(node.tagName)) {
                        out.push({type: 'heading', text: node.innerText.trim()});
                    } else if (node.tagName === 'A' && node.querySelector('img')) {
                        const alt = node.querySelector('img').alt;
                        if (alt) {
                            out.push({type: 'logo', name: alt, href: node.href});
                        }
                    }
                }
                return out;
            }
            """
        )
        browser.close()

    if not sequence:
        print("ERROR: no headings/logos captured. The page may have changed.")
        return []

    results = []
    seen = set()
    category = ""
    for item in sequence:
        if item["type"] == "heading":
            if item["text"] in CATEGORY_HEADINGS:
                category = CATEGORY_HEADINGS[item["text"]]
            continue

        name = item["name"].strip()
        href = item["href"]
        if not name or name == SITE_LOGO_ALT:
            continue

        key = (name, href)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "name": name,
            "domain": normalize_domain(href),
            "category": category,
        })

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "category"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows -> {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = scrape()

    if not rows:
        print("No data scraped.")
        return

    domain_count = sum(1 for r in rows if r["domain"])
    print(f"\nSummary: {len(rows)} exhibitors | {domain_count} with domain | {len(rows) - domain_count} missing")

    write_csv(rows)


if __name__ == "__main__":
    main()
