"""
Step 2: Score leads against ICP criteria.

Reads enriched.csv and config.json, applies ICP filters (headcount, industry, country),
outputs scored.csv with icp_score and qualified columns.

Usage:
    python workflows/event_outbound/2_score.py --project projects/event_outbound/gitex_asia_2026
"""

import argparse
import csv
import json
from pathlib import Path


def score_lead(sponsor: dict, icp: dict) -> tuple[int, bool]:
    score = 0

    headcount = sponsor.get("headcount", "")
    try:
        hc = int(headcount)
        min_hc = icp.get("min_headcount", 0)
        max_hc = icp.get("max_headcount", 99999)
        if min_hc <= hc <= max_hc:
            score += 40
    except (ValueError, TypeError):
        pass

    target_industries = [i.lower() for i in icp.get("target_industries", [])]
    industry = (sponsor.get("industry") or "").lower()
    if not target_industries or any(t in industry for t in target_industries):
        score += 30

    target_countries = [c.lower() for c in icp.get("target_countries", [])]
    country = (sponsor.get("country") or "").lower()
    if not target_countries or any(t in country for t in target_countries):
        score += 30

    qualified = score >= 60
    return score, qualified


def score(project_path: Path):
    input_path = project_path / "data" / "output" / "enriched.csv"
    output_path = project_path / "data" / "output" / "scored.csv"

    with open(project_path / "config.json") as f:
        config = json.load(f)

    icp = config.get("icp", {})

    with open(input_path, newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    scored = []
    for lead in leads:
        s, q = score_lead(lead, icp)
        lead["icp_score"] = s
        lead["qualified"] = q
        scored.append(lead)

    qualified_count = sum(1 for l in scored if l["qualified"])
    print(f"{len(scored)} leads scored. {qualified_count} qualified.")

    fieldnames = list(scored[0].keys()) if scored else []
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored)

    print(f"Saved to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    score(Path(args.project))


if __name__ == "__main__":
    main()
