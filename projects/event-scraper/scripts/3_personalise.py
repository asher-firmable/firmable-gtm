"""
Step 3: Generate personalised email openers using Claude.

Reads scored.csv (qualified leads only), calls Claude to write a custom
email opening line per company, outputs personalised.csv.

Usage:
    python workflows/event_outbound/3_personalise.py --project projects/event_outbound/gitex_asia_2026
"""

import argparse
import csv
import json
from pathlib import Path

from scripts.ai import ask_claude


PROMPT_TEMPLATE = """Write a single personalised opening line for a cold email from {sender_name} to a decision-maker at {company_name}.

Company context:
- Industry: {industry}
- Headcount: {headcount}
- Description: {description}
- Value prop we're offering: {value_prop}

Rules:
- One sentence only, under 20 words
- Do not start with "I" or "We"
- Sound natural and specific, not generic
- Reference something real about the company if possible

Return only the opening line, no extra text."""


def personalise(project_path: Path):
    input_path = project_path / "data" / "output" / "scored.csv"
    output_path = project_path / "data" / "output" / "personalised.csv"

    with open(project_path / "config.json") as f:
        config = json.load(f)

    outreach = config.get("outreach", {})
    sender_name = outreach.get("sender_name", "")
    value_prop = outreach.get("value_prop", "")

    with open(input_path, newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    qualified = [l for l in leads if str(l.get("qualified", "")).lower() == "true"]
    print(f"{len(qualified)} qualified leads to personalise...")

    for i, lead in enumerate(qualified):
        print(f"[{i+1}/{len(qualified)}] {lead['company_name']} ...", end=" ", flush=True)
        prompt = PROMPT_TEMPLATE.format(
            sender_name=sender_name,
            company_name=lead.get("company_name", ""),
            industry=lead.get("industry", ""),
            headcount=lead.get("headcount", ""),
            description=lead.get("description", ""),
            value_prop=value_prop,
        )
        try:
            lead["email_opener"] = ask_claude(prompt)
            print("✓")
        except Exception as e:
            lead["email_opener"] = ""
            print(f"error: {e}")

    fieldnames = list(qualified[0].keys()) if qualified else []
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(qualified)

    print(f"\nSaved {len(qualified)} personalised leads to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    personalise(Path(args.project))


if __name__ == "__main__":
    main()
