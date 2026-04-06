"""
Scrape Sydney Build Expo 2026 exhibitor list.

The exhibitor directory is powered by ExpoFP. When the parent page loads,
the browser fetches https://sydneybuild2026.expofp.com/data/data.js — a
single JS file containing the full exhibitor dataset as a JSON object
(var __data = {...}).

This scraper intercepts that response, parses the JSON, and writes
name + domain to a CSV. No per-card clicking required.

Output: campaigns/anz/events-outbound/sydney-build-expo-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/sydney-build-expo-2026/scrape_exhibitors.py
"""

import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PARENT_URL  = "https://www.sydneybuildexpo.com/exhibitor-list"
DATA_JS_URL = "sydneybuild2026.expofp.com/data/data.js"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

PAGE_LOAD_WAIT_MS = 6000


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


def parse_data_js(body: str) -> list:
    """Strip the JS variable wrapper and parse the JSON payload."""
    # Strip: var __data = { ... };
    match = re.search(r"var\s+__data\s*=\s*(\{.*\})\s*;?\s*$", body, re.DOTALL)
    if not match:
        raise ValueError("Could not find __data variable in data.js")
    return json.loads(match.group(1)).get("exhibitors", [])


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape() -> list:
    results = []

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

        data_js_captured = []

        def on_response(response):
            if DATA_JS_URL in response.url:
                try:
                    body = response.text()
                    print(f"Captured data.js ({len(body):,} bytes) from {response.url}")
                    exhibitors = parse_data_js(body)
                    print(f"Parsed {len(exhibitors)} exhibitors from data.js")
                    data_js_captured.extend(exhibitors)
                except Exception as e:
                    print(f"[error] Could not parse data.js: {e}")

        page.on("response", on_response)

        print(f"Loading {PARENT_URL} ...")
        try:
            page.goto(PARENT_URL, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print(f"[warn] networkidle timed out: {e} — continuing")

        page.wait_for_timeout(PAGE_LOAD_WAIT_MS)
        browser.close()

    if not data_js_captured:
        print("ERROR: data.js was not captured. The page may have changed.")
        return []

    for ex in data_js_captured:
        name = (ex.get("name") or "").strip()
        website = ex.get("website") or ""
        if name:
            results.append({"name": name, "domain": normalize_domain(website)})

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows → {OUTPUT_FILE}")


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
