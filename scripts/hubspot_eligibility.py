"""
HubSpot Contact Eligibility Check
-----------------------------------
Read-only script. Given a CSV of email addresses, checks each contact against two gates
before adding them to a cold outbound campaign.

Gate 1 — Lifecycle:
  • Contact lifecyclestage must not be "customer"
  • Company trial_status must not be "Active Trial" or "Paying Customer from Trial"

Gate 2 — Engagement (last 30 days):
  • Contact or associated company must have at least one scheduled task (NOT_STARTED, future due date)
  • No logged calls, emails, or meetings in the last 30 days

Usage:
  PYTHONPATH=. python3 scripts/hubspot_eligibility.py \\
    --input data/input/contacts.csv \\
    --output campaigns/anz/my-campaign/data/final/eligible.csv
"""

import time
import argparse
import pandas as pd

from scripts.hubspot_client import HubSpotClient
from scripts.utils import load_csv, save_csv, timestamp

TRIAL_EXCLUDE = {"Active Trial", "Paying Customer from Trial"}
THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000
COMM_TYPES = ("calls", "emails", "meetings")


def _check_contact(hs: HubSpotClient, email: str, company_cache: dict, company_task_cache: dict, now_ms: int) -> dict:
    result = {
        "email": email,
        "status": "PASS",
        "eligible": True,
        "fail_reasons": "",
        "contact_id": "",
        "company_id": "",
        "lifecyclestage": "",
        "trial_status": "",
        "scheduled_tasks": 0,
        "recent_comms": 0,
    }
    fail_reasons = []

    # ── Step 1: Contact lookup ─────────────────────────────────────────────
    try:
        contact = hs.get_contact_by_email(email)
    except Exception as e:
        result.update({"status": "ERROR", "eligible": False, "fail_reasons": f"lookup error: {e}"})
        return result

    if not contact:
        result.update({"status": "NOT_FOUND", "eligible": False, "fail_reasons": "not found in HubSpot"})
        return result

    contact_id = contact["id"]
    props = contact.get("properties", {})
    lifecyclestage = props.get("lifecyclestage") or ""
    company_id = props.get("associatedcompanyid") or ""

    result["contact_id"] = contact_id
    result["company_id"] = company_id
    result["lifecyclestage"] = lifecyclestage

    # ── Gate 1a: Lifecycle ─────────────────────────────────────────────────
    if lifecyclestage == "customer":
        fail_reasons.append("lifecycle: is a customer")

    # ── Gate 1b: Trial status (company level) ──────────────────────────────
    if company_id:
        if company_id not in company_cache:
            try:
                cprops = hs.get_company_properties(company_id, ["trial_status"])
                company_cache[company_id] = cprops.get("trial_status") or ""
            except Exception:
                company_cache[company_id] = ""
        trial_status = company_cache[company_id]
        result["trial_status"] = trial_status
        if trial_status in TRIAL_EXCLUDE:
            fail_reasons.append(f"trial: {trial_status}")

    # ── Gate 2a: Scheduled tasks ───────────────────────────────────────────
    try:
        contact_task_ids = hs.get_associated_ids("contacts", contact_id, "tasks")

        company_task_ids = []
        if company_id:
            if company_id not in company_task_cache:
                company_task_cache[company_id] = hs.get_associated_ids("companies", company_id, "tasks")
            company_task_ids = company_task_cache[company_id]

        all_task_ids = list(set(contact_task_ids + company_task_ids))
        scheduled_count = 0

        if all_task_ids:
            tasks = hs.batch_get_objects("tasks", all_task_ids, ["hs_task_status", "hs_timestamp"])
            for task in tasks:
                tprops = task.get("properties", {})
                status = tprops.get("hs_task_status") or ""
                due_ts = int(tprops.get("hs_timestamp") or 0)
                # Scheduled = NOT_STARTED with no due date (open) or a future due date
                if status == "NOT_STARTED" and (due_ts == 0 or due_ts > now_ms):
                    scheduled_count += 1

        result["scheduled_tasks"] = scheduled_count
        if scheduled_count == 0:
            fail_reasons.append("tasks: no scheduled tasks on contact or company")
    except Exception as e:
        fail_reasons.append(f"tasks: error ({e})")

    # ── Gate 2b: Recent communications ────────────────────────────────────
    try:
        cutoff_ms = now_ms - THIRTY_DAYS_MS
        recent_count = 0

        for obj_type in COMM_TYPES:
            ids = hs.get_associated_ids("contacts", contact_id, obj_type)
            if ids:
                objects = hs.batch_get_objects(obj_type, ids, ["hs_timestamp"])
                for obj in objects:
                    ts = int(obj.get("properties", {}).get("hs_timestamp") or 0)
                    if ts >= cutoff_ms:
                        recent_count += 1

        result["recent_comms"] = recent_count
        if recent_count > 0:
            fail_reasons.append(f"comms: {recent_count} activity(s) in last 30 days")
    except Exception as e:
        fail_reasons.append(f"comms: error ({e})")

    if fail_reasons:
        result.update({
            "status": "FAIL",
            "eligible": False,
            "fail_reasons": " | ".join(fail_reasons),
        })

    return result


def run(input_path: str, output_path: str) -> None:
    hs = HubSpotClient()
    df = load_csv(input_path)

    if "email" not in df.columns:
        raise ValueError("Input CSV must have an 'email' column")

    emails = df["email"].dropna().str.strip().tolist()
    emails = [e for e in emails if e]
    total = len(emails)
    now_ms = int(time.time() * 1000)
    company_cache: dict = {}
    company_task_cache: dict = {}
    rows = []

    for i, email in enumerate(emails, 1):
        result = _check_contact(hs, email, company_cache, company_task_cache, now_ms)
        rows.append(result)

        status = result["status"]
        if status == "PASS":
            print(f"[{i}/{total}] {email} → PASS")
        elif status == "NOT_FOUND":
            print(f"[{i}/{total}] {email} → NOT FOUND")
        elif status == "ERROR":
            print(f"[{i}/{total}] {email} → ERROR ({result['fail_reasons']})")
        else:
            print(f"[{i}/{total}] {email} → FAIL ({result['fail_reasons']})")

    out_df = pd.DataFrame(rows, columns=[
        "email", "status", "eligible", "fail_reasons",
        "contact_id", "company_id", "lifecyclestage", "trial_status",
        "scheduled_tasks", "recent_comms",
    ])
    save_csv(out_df, output_path)

    pass_count = sum(1 for r in rows if r["status"] == "PASS")
    fail_count = sum(1 for r in rows if r["status"] == "FAIL")
    not_found = sum(1 for r in rows if r["status"] == "NOT_FOUND")
    errors = sum(1 for r in rows if r["status"] == "ERROR")

    print(f"\n{'─' * 60}")
    print(f"Total: {total} | Pass: {pass_count} | Fail: {fail_count} | Not found: {not_found} | Errors: {errors}")
    print(f"Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Check HubSpot contact eligibility before outreach (read-only).")
    parser.add_argument("--input", required=True, help="CSV with 'email' column")
    parser.add_argument("--output", default=None, help="Output CSV path (default: output/eligible_<timestamp>.csv)")
    args = parser.parse_args()

    output_path = args.output or f"output/eligible_{timestamp()}.csv"
    run(args.input, output_path)


if __name__ == "__main__":
    main()
