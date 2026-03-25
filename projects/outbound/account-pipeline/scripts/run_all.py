"""
Orchestrator: runs the full account-based outbound pipeline end-to-end.

Steps:
  0. Filter junk accounts (lead-gen companies, suspect names)
  1. Find decision-maker contacts via Firmable
  2. Research each company's target market
  3. Generate personalised 2-email PQS sequences
  4. Create SmartLead campaign and upload leads

Usage:
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx --countries AU,NZ
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx --dry-run
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx --skip-upload
  PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx --campaign-id 12345
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def banner(step: int, title: str):
    print(f"\n{'='*60}")
    print(f"  STEP {step}: {title}")
    print(f"{'='*60}\n")


def run_step(script: str, extra_args: list[str] = None):
    cmd = [sys.executable, str(SCRIPTS_DIR / script)] + (extra_args or [])
    result = subprocess.run(cmd, env={**__import__("os").environ, "PYTHONPATH": "."})
    if result.returncode != 0:
        print(f"\nERROR: {script} exited with code {result.returncode}. Aborting pipeline.", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Account-based outbound pipeline")
    parser.add_argument(
        "--input", required=True,
        help="Path to input Excel or CSV (columns: account_name, firmable_company_id)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview SmartLead upload without actually uploading"
    )
    parser.add_argument(
        "--skip-upload", action="store_true",
        help="Stop after generating emails (don't upload to SmartLead)"
    )
    parser.add_argument(
        "--campaign-id",
        help="Use existing SmartLead campaign ID (skip campaign creation)"
    )
    parser.add_argument(
        "--countries",
        help="Comma-separated country codes for contact search, e.g. AU,NZ (if omitted, you will be prompted)"
    )
    args = parser.parse_args()

    banner(0, "Filter Accounts")
    run_step("0_filter.py", ["--input", args.input])

    banner(1, "Find Contacts")
    contacts_args = []
    if args.countries:
        contacts_args += ["--countries", args.countries]
    run_step("1_find_contacts.py", contacts_args)

    banner(2, "Research Companies")
    run_step("2_research.py")

    banner(3, "Generate Emails")
    run_step("3_generate_emails.py")

    if args.skip_upload:
        print("\n[--skip-upload] Stopping before SmartLead upload.")
        print("Review outbound/account-pipeline/output/emails.csv before uploading.")
        return

    banner(4, "Upload to SmartLead")
    upload_args = []
    if args.dry_run:
        upload_args.append("--dry-run")
    if args.campaign_id:
        upload_args += ["--campaign-id", args.campaign_id]
    run_step("4_upload.py", upload_args)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
