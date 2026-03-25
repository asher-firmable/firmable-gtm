"""
Step 4: Upload personalised leads to SmartLead campaign.

Reads personalised.csv and config.json, uploads each lead to the configured
SmartLead campaign.

Usage:
    python projects/slack-bots/event-scraper/scripts/4_upload_to_smartlead.py --project projects/slack-bots/event-scraper/output/gitex_asia_2026
    python projects/slack-bots/event-scraper/scripts/4_upload_to_smartlead.py --project projects/slack-bots/event-scraper/output/gitex_asia_2026 --dry-run
"""

import argparse
import csv
import json
from pathlib import Path

from scripts.smartlead_client import SmartLeadClient


def upload(project_path: Path, dry_run: bool = False):
    input_path = project_path / "data" / "output" / "personalised.csv"

    with open(project_path / "config.json") as f:
        config = json.load(f)

    campaign_id = config.get("smartlead_campaign_id", "")
    if not campaign_id:
        raise ValueError("smartlead_campaign_id is not set in config.json")

    with open(input_path, newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    smartlead_leads = []
    for lead in leads:
        smartlead_leads.append({
            "email": lead.get("email", ""),
            "first_name": lead.get("first_name", ""),
            "last_name": lead.get("last_name", ""),
            "company_name": lead.get("company_name", ""),
            "website": lead.get("website", ""),
            "linkedin_url": lead.get("linkedin_url", ""),
            "custom_fields": {
                "email_opener": lead.get("email_opener", ""),
                "industry": lead.get("industry", ""),
            },
        })

    if dry_run:
        print(f"[DRY RUN] Would upload {len(smartlead_leads)} leads to campaign {campaign_id}")
        for l in smartlead_leads[:3]:
            print(f"  - {l['company_name']}: {l['custom_fields']['email_opener'][:80]}...")
        return

    client = SmartLeadClient()
    result = client.add_leads_to_campaign(campaign_id, smartlead_leads)
    print(f"Uploaded {len(smartlead_leads)} leads to campaign {campaign_id}")
    print(f"Response: {result}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    args = parser.parse_args()
    upload(Path(args.project), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
