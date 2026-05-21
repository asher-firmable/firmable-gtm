"""
Contact Activity Check
----------------------
Read a contact list (Excel or CSV), check each email against HubSpot, and filter out
any contact that has had an email, call, or meeting activity in the past N days.

Contacts not found in HubSpot are kept (PASS — new prospects).

Usage:
  PYTHONPATH=. python campaigns/company-checks/scripts/contact_activity_check.py \\
    --input campaigns/company-checks/input/contacts.xlsx \\
    --output-dir campaigns/company-checks/output/ \\
    --days 14

If --input is omitted the script picks the most recently modified file in
campaigns/company-checks/input/.
"""

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from scripts.hubspot_client import HubSpotClient

load_dotenv()

DEFAULT_INPUT_DIR = "campaigns/company-checks/input"
DEFAULT_OUTPUT_DIR = "campaigns/company-checks/output"
DEFAULT_DAYS = 14

EMAIL_ALIASES = ["email", "Email", "email_address", "primary_work_email", "work_email", "Primary work email"]
def _parse_hs_timestamp(raw: str) -> int:
    """Parse a HubSpot timestamp to milliseconds. Handles ms-int strings and ISO-8601."""
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _resolve_email_column(df: pd.DataFrame) -> str:
    for alias in EMAIL_ALIASES:
        if alias in df.columns:
            return alias
    raise ValueError(
        f"Could not find an email column. Expected one of: {EMAIL_ALIASES}. "
        f"Found: {list(df.columns)}"
    )


def _load_file(path: str) -> pd.DataFrame:
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _find_latest_input(input_dir: str) -> str:
    candidates = [
        f for f in Path(input_dir).iterdir()
        if f.is_file() and f.suffix.lower() in (".csv", ".xlsx", ".xls")
    ]
    if not candidates:
        raise FileNotFoundError(f"No CSV or Excel files found in {input_dir}")
    return str(max(candidates, key=lambda f: f.stat().st_mtime))


def _check_contact_activity(hs: HubSpotClient, email: str, cutoff_ms: int) -> dict:
    """
    Returns dict with keys: hs_found, hs_contact_id, hs_last_contacted, activity_check, activity_reason.

    Uses hs_last_contacted — HubSpot's native stamp updated whenever any email, call, or
    meeting is logged against the contact (manually or via API).

    PASS = not in HubSpot, or no hs_last_contacted, or last activity older than cutoff.
    FAIL = hs_last_contacted within the lookback window.
    """
    result = {
        "hs_found": False,
        "hs_contact_id": "",
        "hs_last_contacted": "",
        "activity_check": "PASS",
        "activity_reason": "",
    }

    contact = hs.get_contact_by_email(email)
    if not contact:
        return result

    contact_id = contact["id"]
    props = contact.get("properties", {})
    last_contacted_raw = props.get("hs_last_contacted") or ""

    result["hs_found"] = True
    result["hs_contact_id"] = contact_id
    result["hs_last_contacted"] = last_contacted_raw

    if last_contacted_raw:
        last_ts_ms = _parse_hs_timestamp(last_contacted_raw)
        if last_ts_ms > 0 and last_ts_ms >= cutoff_ms:
            result["activity_check"] = "FAIL"
            result["activity_reason"] = "activity within lookback window"

    return result


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run(input_path: str, output_dir: str, days: int) -> None:
    hs = HubSpotClient()

    df = _load_file(input_path)
    email_col = _resolve_email_column(df)

    total_input = len(df)
    df["email_norm_key"] = df[email_col].fillna("").str.strip().str.lower()
    df_eval = df[df["email_norm_key"] != ""].copy()
    skipped = total_input - len(df_eval)

    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - days * 24 * 60 * 60 * 1000

    not_in_hs = 0
    in_hs_no_activity = 0
    failed = 0
    errors = 0

    hs_found_col = []
    hs_contact_id_col = []
    hs_last_contacted_col = []
    activity_check_col = []
    activity_reason_col = []

    for i, (_, row) in enumerate(df_eval.iterrows(), 1):
        email = row["email_norm_key"]
        check = _check_contact_activity(hs, email, cutoff_ms)

        status = check["activity_check"]
        reason = check["activity_reason"]

        if status == "ERROR":
            errors += 1
            label = f"ERROR ({reason})"
        elif status == "FAIL":
            failed += 1
            label = f"FAIL ({reason})"
        elif not check["hs_found"]:
            not_in_hs += 1
            label = "PASS (not in HubSpot)"
        else:
            in_hs_no_activity += 1
            label = "PASS"

        print(f"[{i}/{len(df_eval)}] {email} → {label}")

        hs_found_col.append(check["hs_found"])
        hs_contact_id_col.append(check["hs_contact_id"])
        hs_last_contacted_col.append(check["hs_last_contacted"])
        activity_check_col.append(status)
        activity_reason_col.append(reason)

    out_df = df_eval.drop(columns=["email_norm_key"], errors="ignore").copy()
    out_df["hs_found"] = hs_found_col
    out_df["hs_contact_id"] = hs_contact_id_col
    out_df["hs_last_contacted"] = hs_last_contacted_col
    out_df["activity_check"] = activity_check_col
    out_df["activity_reason"] = activity_reason_col

    os.makedirs(output_dir, exist_ok=True)
    ts = _timestamp()
    clean_path = f"{output_dir.rstrip('/')}/no_activity_contacts_{ts}.csv"
    full_path = f"{output_dir.rstrip('/')}/activity_check_full_{ts}.csv"

    clean_df = out_df[out_df["activity_check"] == "PASS"].drop(
        columns=["hs_found", "hs_contact_id", "activity_check", "activity_reason"],
        errors="ignore",
    )
    clean_df.to_csv(clean_path, index=False)
    out_df.to_csv(full_path, index=False)

    pass_count = not_in_hs + in_hs_no_activity
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"Contacts in file:        {total_input}")
    if skipped:
        print(f"Evaluated:               {len(df_eval)}   ({skipped} skipped — no email)")
    else:
        print(f"Evaluated:               {len(df_eval)}")
    print(f"Not in HubSpot (PASS):   {not_in_hs}")
    print(f"In HubSpot, no activity: {in_hs_no_activity}")
    print(f"Filtered out (FAIL):     {failed}")
    if errors:
        print(f"Errors:                  {errors}")
    print(sep)
    print(f"Clean list:  {clean_path}")
    print(f"Full report: {full_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Filter contacts with recent HubSpot activity (emails, calls, meetings)."
    )
    parser.add_argument("--input", help="Path to contact CSV or Excel file")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Lookback window in days (default: 14)")
    args = parser.parse_args()

    input_path = args.input or _find_latest_input(DEFAULT_INPUT_DIR)
    print(f"Input file: {input_path}")
    print(f"Lookback:   {args.days} days\n")

    run(input_path, args.output_dir, args.days)


if __name__ == "__main__":
    main()
