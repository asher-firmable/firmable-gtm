"""
Step 4: Create a SmartLead campaign with a 2-step email sequence and upload all leads.

The campaign template uses {{email_body_1}} and {{email_body_2}} as full-body variables,
filled per lead from the generated emails.csv.

NOTE: If create_campaign or add_email_sequence return 403, those endpoints may be
IP-restricted. In that case, create the campaign manually in SmartLead and store the
campaign_id here, then re-run with --campaign-id <id> to skip creation.

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py --dry-run
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py --campaign-id 12345
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from scripts.smartlead_client import SmartLeadClient

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.json not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_lead(row: dict) -> dict:
    return {
        "email": row.get("work_email", ""),
        "first_name": row.get("first_name", ""),
        "last_name": row.get("last_name", ""),
        "company_name": row.get("account_name", ""),
        "website": row.get("company_website", ""),
        "linkedin_url": row.get("linkedin_url", ""),
        "custom_fields": {
            "subject_1": row.get("subject_1", ""),
            "email_body_1": row.get("body_1", ""),
            "email_body_2": row.get("body_2", ""),
            "target_titles": row.get("target_titles", ""),
            "position": row.get("position", ""),
        },
    }


def run(dry_run: bool = False, existing_campaign_id: str = None):
    input_path = OUTPUT_DIR / "emails.csv"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run 3_generate_emails.py first.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(input_path)
    if df.empty:
        print("No leads to upload.")
        return

    # Drop rows missing email or both email bodies
    df = df[df["work_email"].notna() & (df["work_email"] != "")]
    print(f"Uploading {len(df)} leads...")

    config = load_config()
    delay_days = config.get("sequence", {}).get("step_2_delay_days", 3)

    if dry_run:
        print("\n[DRY RUN] Would create campaign and upload leads:")
        for _, row in df.head(3).iterrows():
            lead = build_lead(row.to_dict())
            print(f"  {lead['email']} — {lead['first_name']} {lead['last_name']} @ {lead['company_name']}")
            print(f"    Subject 1: {lead['custom_fields']['subject_1'][:60]}")
            print(f"    Subject 2: Re: {lead['custom_fields']['subject_1'][:60]}")
        print(f"\n  ... and {max(0, len(df) - 3)} more leads")
        return

    client = SmartLeadClient()
    campaign_id = existing_campaign_id

    if not campaign_id:
        campaign_name = f"Account Pipeline - {date.today().isoformat()}"
        print(f"Creating campaign: {campaign_name}")
        try:
            result = client.create_campaign(campaign_name)
            campaign_id = str(result.get("id") or result.get("campaign_id", ""))
            if not campaign_id:
                print(f"ERROR: Could not extract campaign ID from response: {result}", file=sys.stderr)
                sys.exit(1)
            print(f"  -> Campaign created: ID {campaign_id}")
        except Exception as e:
            print(f"ERROR: create_campaign failed: {e}", file=sys.stderr)
            print("If you got a 403, this endpoint may be IP-restricted.", file=sys.stderr)
            print("Create the campaign manually in SmartLead and re-run with --campaign-id <id>", file=sys.stderr)
            sys.exit(1)

        print("Adding 2-step email sequence...")
        steps = [
            {
                "subject": "{{subject_1}}",
                "email_body": "{{email_body_1}}",
                "seq_number": 1,
                "seq_delay_details": {"delay_in_days": 0},
            },
            {
                "subject": "Re: {{subject_1}}",
                "email_body": "{{email_body_2}}",
                "seq_number": 2,
                "seq_delay_details": {"delay_in_days": delay_days},
            },
        ]
        try:
            client.add_email_sequence(campaign_id, steps)
            print(f"  -> Sequence added (step 2 delay: {delay_days} days)")
        except Exception as e:
            print(f"ERROR: add_email_sequence failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Upload leads in batches of 50
    BATCH_SIZE = 50
    results = []
    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i : i + BATCH_SIZE]
        leads = [build_lead(row.to_dict()) for _, row in batch.iterrows()]
        print(f"  Uploading leads {i+1}–{min(i+BATCH_SIZE, len(df))}...", flush=True)
        try:
            resp = client.add_leads_to_campaign(campaign_id, leads)
            for lead in leads:
                results.append({"email": lead["email"], "status": "uploaded", "campaign_id": campaign_id})
        except Exception as e:
            print(f"  [ERROR] Batch {i+1}–{i+BATCH_SIZE} failed: {e}", flush=True)
            for lead in leads:
                results.append({"email": lead["email"], "status": f"error: {e}", "campaign_id": campaign_id})

    output_path = OUTPUT_DIR / "upload_results.csv"
    pd.DataFrame(results).to_csv(output_path, index=False)

    uploaded = sum(1 for r in results if r["status"] == "uploaded")
    print(f"\nDone. {uploaded}/{len(results)} leads uploaded to campaign {campaign_id}")
    print(f"  -> {output_path}")
    print(f"\nView campaign in SmartLead: https://app.smartlead.ai/app/campaigns/{campaign_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--campaign-id", help="Use existing SmartLead campaign ID (skip creation)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, existing_campaign_id=args.campaign_id)
