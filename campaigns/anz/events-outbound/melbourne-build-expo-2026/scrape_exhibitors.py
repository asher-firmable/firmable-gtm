"""
Scrape Melbourne Build Expo 2026 exhibitor list.

The exhibitor directory at https://melbournebuildexpo.com/meet-exhibitors is
powered by ExpoFP. The full dataset (exhibitors, booths, categories) lives in
https://melbournebuild2026.expofp.com/data/data.js as `var __data = {...}`,
which is fetchable directly with requests — no browser needed.

Domain falls back to the exhibitor's contact email domain when no website is
listed (generic mail providers excluded).

Output: campaigns/anz/events-outbound/melbourne-build-expo-2026/output/exhibitors.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/events-outbound/melbourne-build-expo-2026/scrape_exhibitors.py
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_JS_URL = "https://melbournebuild2026.expofp.com/data/data.js"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "exhibitors.csv"

GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "yahoo.com.au",
    "bigpond.com", "bigpond.net.au", "live.com", "icloud.com", "qq.com",
    "163.com", "126.com", "optusnet.com.au", "me.com",
}

FIELDS = ["name", "domain", "category", "stand", "domain_source"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def email_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    domain = email.split("@", 1)[1].strip().lower()
    return "" if domain in GENERIC_EMAIL_DOMAINS else domain


def parse_data_js(body: str) -> dict:
    """Strip the JS variable wrapper and parse the JSON payload."""
    match = re.search(r"var\s+__data\s*=\s*(\{.*\})\s*;?\s*$", body, re.DOTALL)
    if not match:
        raise ValueError("Could not find __data variable in data.js")
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape() -> list:
    resp = requests.get(DATA_JS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    data = parse_data_js(resp.text)

    category_names = {c["id"]: c.get("name", "") for c in data.get("categories", [])}

    booths_by_exhibitor = defaultdict(list)
    for booth in data.get("booths", []):
        for ex_id in booth.get("exhibitors", []):
            booths_by_exhibitor[ex_id].append(booth.get("name", ""))

    results = []
    for ex in data.get("exhibitors", []):
        name = (ex.get("name") or "").strip()
        if not name:
            continue

        domain = normalize_domain(ex.get("website") or "")
        source = "website" if domain else ""
        if not domain:
            domain = email_domain(ex.get("email") or "")
            source = "email" if domain else ""

        categories = [category_names.get(c, "") for c in ex.get("categories", [])]
        results.append({
            "name": name,
            "domain": domain,
            "category": ", ".join(c for c in categories if c),
            "stand": ", ".join(sorted(booths_by_exhibitor.get(ex["id"], []))),
            "domain_source": source,
        })

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
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
    email_count = sum(1 for r in rows if r["domain_source"] == "email")
    print(f"\nSummary: {len(rows)} exhibitors | {domain_count} with domain "
          f"({email_count} from email) | {len(rows) - domain_count} missing")

    write_csv(rows)


if __name__ == "__main__":
    main()
