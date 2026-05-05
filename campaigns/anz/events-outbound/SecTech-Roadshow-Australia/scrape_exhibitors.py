"""
Scrape exhibitors from SecTech Roadshow Australia.
Source: https://sectechroadshow.com.au/exhibitors-sectech/
Output: output/exhibitors.csv — name, website columns
"""

import csv
import os

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://sectechroadshow.com.au/exhibitors-sectech/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "exhibitors.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_exhibitors():
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    seen = set()

    for col in soup.find_all("div", class_="elementor-inner-column"):
        link = next(
            (a for a in col.find_all("a") if a.get_text(strip=True) == "Learn more"),
            None,
        )
        if not link:
            continue

        website = link.get("href", "").strip()
        texts = [
            t.strip()
            for t in col.stripped_strings
            if t.strip() and t.strip() != "Learn more"
        ]
        name = texts[0] if texts else ""

        if not name:
            continue

        key = (name.lower(), website.lower())
        if key in seen:
            continue
        seen.add(key)

        results.append({"name": name, "website": website})

    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    exhibitors = scrape_exhibitors()

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "website"])
        writer.writeheader()
        writer.writerows(exhibitors)

    no_website = sum(1 for e in exhibitors if not e["website"])
    print(f"Scraped {len(exhibitors)} exhibitors -> {OUTPUT_FILE}")
    print(f"  With website:    {len(exhibitors) - no_website}")
    print(f"  Without website: {no_website}")


if __name__ == "__main__":
    main()
