"""
Step 1: Enrich sponsors with Firmable.

Reads sponsors_raw.csv, calls Firmable API using LinkedIn URL to get Firmable company ID
and enrichment data (industry, headcount, location, etc.).

Usage:
    python projects/slack-bots/event-scraper/scripts/1_enrich.py --project projects/slack-bots/event-scraper/output/gitex_asia_2026
"""

import argparse
import csv
import json
from pathlib import Path

from scripts.firmable_api import FirmableClient


def enrich(project_path: Path):
    input_path = project_path / "data" / "input" / "sponsors_raw.csv"
    output_path = project_path / "data" / "output" / "enriched.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = FirmableClient()

    with open(input_path, newline="", encoding="utf-8") as f:
        sponsors = list(csv.DictReader(f))

    enriched = []
    for i, sponsor in enumerate(sponsors):
        print(f"[{i+1}/{len(sponsors)}] Enriching {sponsor['company_name']} ...", end=" ", flush=True)
        try:
            result = client.lookup_company(domain=sponsor["website"].replace("https://", "").replace("http://", "").split("/")[0])
            sponsor.update({
                "firmable_id": result.get("id", ""),
                "industry": result.get("industry", ""),
                "headcount": result.get("employee_count", ""),
                "country": result.get("country", ""),
                "description": result.get("description", ""),
            })
            print("✓")
        except Exception as e:
            print(f"error: {e}")
            sponsor.update({"firmable_id": "", "industry": "", "headcount": "", "country": "", "description": ""})

        enriched.append(sponsor)

    fieldnames = list(enriched[0].keys()) if enriched else []
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)

    print(f"\nSaved {len(enriched)} rows to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    enrich(Path(args.project))


if __name__ == "__main__":
    main()
