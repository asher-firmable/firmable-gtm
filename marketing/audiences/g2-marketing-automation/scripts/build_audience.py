"""Build a marketing audience CSV from a G2 category scrape (Apify via Deepline).

The scrape is run with the omkar-cloud/g2-product-scraper actor (expandListings +
scrapeProductDetails), which writes two row types to one dataset:
  - category_product: G2 rank, rating, review count, top pro/con
  - product:          full profile incl. company_website, LinkedIn, HQ, pricing

This script pages through the dataset, merges both row types on product slug and
writes one row per product.

Usage (from repo root):
    PYTHONPATH=. python3 marketing/audiences/g2-marketing-automation/scripts/build_audience.py \
        --dataset-id HwkjFjQPZxbp6ybyZ
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from urllib.parse import urlparse

DEEPLINE = ".deepline/runtime/node_modules/.bin/deepline"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
PAGE_SIZE = 500

COLUMNS = [
    "g2_rank", "product_name", "vendor_name", "domain", "company_website",
    "company_linkedin", "hq_location", "founded_year", "rating", "reviews_count",
    "starting_price", "has_free_trial", "solution_type", "top_pro", "top_con",
    "description", "g2_link",
]


def fetch_items(dataset_id):
    """Page through the Apify dataset via the Deepline CLI."""
    items, offset = [], 0
    while True:
        payload = json.dumps({"datasetId": dataset_id, "offset": offset, "limit": PAGE_SIZE})
        result = subprocess.run(
            [DEEPLINE, "tools", "execute", "apify_get_dataset_items", "--input", payload, "--json"],
            capture_output=True, text=True,
        )
        # The CLI prints a deprecation banner before the JSON body
        body = result.stdout[result.stdout.find("{"):]
        try:
            page = json.loads(body)["toolResponse"]["raw"]
        except (json.JSONDecodeError, KeyError) as e:
            sys.exit(f"Failed to read dataset page at offset {offset}: {e}\n{result.stdout[:500]}{result.stderr[:500]}")
        items.extend(page)
        print(f"  fetched {len(items)} rows")
        if len(page) < PAGE_SIZE:
            return items
        offset += PAGE_SIZE


def to_domain(url):
    if not url:
        return ""
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    return host.removeprefix("www.")


def build_rows(items):
    listings = {r["slug"]: r for r in items if r.get("type") == "category_product"}
    profiles = {r["slug"]: r for r in items if r.get("type") == "product"}

    rows = []
    for slug, listing in listings.items():
        profile = profiles.get(slug, {})
        website = profile.get("company_website") or profile.get("likely_product_website") or ""
        rows.append({
            "g2_rank": listing.get("position"),
            # Listing names are truncated ("...") so prefer the profile name
            "product_name": profile.get("name") or listing.get("name"),
            "vendor_name": profile.get("seller_name") or listing.get("seller_name"),
            "domain": to_domain(website),
            "company_website": website,
            "company_linkedin": profile.get("company_linkedin") or "",
            "hq_location": profile.get("company_location") or "",
            "founded_year": profile.get("company_founded_year") or "",
            "rating": listing.get("rating"),
            "reviews_count": listing.get("reviews_count"),
            "starting_price": profile.get("starting_price") or "",
            "has_free_trial": profile.get("has_free_trial", ""),
            "solution_type": profile.get("solution_type") or "",
            "top_pro": listing.get("top_pro") or "",
            "top_con": listing.get("top_con") or "",
            "description": profile.get("what_is") or profile.get("description") or "",
            "g2_link": listing.get("link"),
        })

    missing = [s for s in listings if s not in profiles]
    if missing:
        print(f"  {len(missing)} products have no profile row (domain may be blank): {missing[:10]}")
    return sorted(rows, key=lambda r: r["g2_rank"] or 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output", default=os.path.join(OUTPUT_DIR, "g2_marketing_automation.csv"))
    args = parser.parse_args()

    items = fetch_items(args.dataset_id)
    rows = build_rows(items)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with_domain = sum(1 for r in rows if r["domain"])
    vendors = len({r["domain"] for r in rows if r["domain"]})
    print(f"Wrote {len(rows)} products ({with_domain} with domain, {vendors} unique vendor domains) -> {args.output}")


if __name__ == "__main__":
    main()
