"""
Pre-Campaign Pipeline
---------------------
Read-only eligibility check + Firmable enrichment. Run this on every contact list
before uploading to SmartLead, regardless of region or campaign type.

Input CSV must have 'email' and 'domain' columns.

Stage 1 — Company-level HubSpot check (per unique domain):
  • Exclude if trial_status = Active Trial or Paying Customer from Trial
  • Exclude if notes_last_contacted (company-level) is within the last 30 days
  • Exclude if outreach_engagement_status is set and not "Pool" or "Time Out"

Stage 2 — Contact-level HubSpot check:
  • Contact NOT in HubSpot → PASS (new prospect)
  • Contact in HubSpot:
      - hs_last_contacted within last 30 days → FAIL
      - Active scheduled tasks (NOT_STARTED, future/open due date) on contact or company → FAIL

Stage 3 — Firmable sales team enrichment (eligible contacts only):
  • Looks up company by domain, fetches AU / NZ / SEA sales headcount
  • Adds apac_sales_team_size = au + nz + sea
  • Note: for ANZ campaigns, apply a manual post-pipeline filter: apac_sales_team_size >= 5 → exclude

Usage:
  PYTHONPATH=. python3 scripts/hubspot_eligibility.py \\
    --input campaigns/sea/my-campaign/data/raw/contacts.csv \\
    --output-dir campaigns/sea/my-campaign/data/eligible/
"""

import time
import argparse
import pandas as pd
from datetime import datetime, timezone

from scripts.hubspot_client import HubSpotClient
from scripts.firmable_api import FirmableClient
from scripts.utils import load_csv, save_csv, timestamp

TRIAL_EXCLUDE = {"Active Trial", "Paying Customer from Trial"}
ELIGIBLE_OUTREACH_STATUSES = {"Pool", "Time Out"}
THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000

# HubSpot internal property name for Outreach Engagement Status.
# Verify in HubSpot → Settings → Properties → Company if checks aren't matching.
OUTREACH_STATUS_PROP = "outreach_engagement_status"


# ── Stage 1: Company-level HubSpot check ──────────────────────────────────────

def _check_company(hs: HubSpotClient, domain: str, now_ms: int, cache: dict) -> dict:
    """Returns a dict with eligibility result and company fields. Caches per domain."""
    if domain in cache:
        return cache[domain]

    empty = {
        "found": False, "eligible": True, "fail_reasons": [],
        "trial_status": "", "notes_last_contacted": "", "outreach_status": "",
    }

    companies = hs.search_companies(domain)
    if not companies:
        cache[domain] = empty
        return empty

    company_id = companies[0]["id"]
    props = hs.get_company_properties(
        company_id, ["trial_status", "notes_last_contacted", OUTREACH_STATUS_PROP]
    )

    trial_status = props.get("trial_status") or ""
    notes_last_contacted = props.get("notes_last_contacted") or ""
    outreach_status = props.get(OUTREACH_STATUS_PROP) or ""

    fail_reasons = []

    # Check 1: trial/customer status
    if trial_status in TRIAL_EXCLUDE:
        fail_reasons.append(f"company: {trial_status}")

    # Check 2: company-level last contacted (catches comms on any contact at the account)
    if notes_last_contacted:
        nlc_ms = _parse_hs_timestamp(notes_last_contacted)
        if nlc_ms > 0 and nlc_ms >= now_ms - THIRTY_DAYS_MS:
            fail_reasons.append("company: last contacted < 30 days")

    # Check 3: outreach engagement status must be Pool or Time Out (if set)
    if outreach_status and outreach_status not in ELIGIBLE_OUTREACH_STATUSES:
        fail_reasons.append(f"company: outreach status '{outreach_status}'")

    result = {
        "found": True,
        "eligible": len(fail_reasons) == 0,
        "fail_reasons": fail_reasons,
        "trial_status": trial_status,
        "notes_last_contacted": notes_last_contacted,
        "outreach_status": outreach_status,
    }
    cache[domain] = result
    return result


def _parse_hs_timestamp(raw: str) -> int:
    """Parse a HubSpot timestamp to milliseconds. Handles both ms-int strings and ISO-8601."""
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


# ── Stage 2: Contact-level HubSpot check ──────────────────────────────────────

def _check_contact(hs: HubSpotClient, email: str, company_task_cache: dict, now_ms: int) -> dict:
    result = {
        "hs_contact_found": False,
        "hs_last_contacted": "",
        "hs_active_tasks": 0,
        "contact_eligible": True,
        "contact_fail_reasons": [],
    }

    contact = hs.get_contact_by_email(email)
    if not contact:
        # Not in HubSpot → new prospect, PASS
        return result

    result["hs_contact_found"] = True
    props = contact.get("properties", {})
    contact_id = contact["id"]
    company_id = props.get("associatedcompanyid") or ""

    # Check hs_last_contacted
    last_contacted_raw = props.get("hs_last_contacted") or ""
    result["hs_last_contacted"] = last_contacted_raw
    if last_contacted_raw:
        last_ts_ms = _parse_hs_timestamp(last_contacted_raw)
        if last_ts_ms > 0 and last_ts_ms >= now_ms - THIRTY_DAYS_MS:
            result["contact_fail_reasons"].append("comms: last contacted < 30 days")

    # Check active scheduled tasks (contact + company)
    try:
        contact_task_ids = hs.get_associated_ids("contacts", contact_id, "tasks")

        company_task_ids = []
        if company_id:
            if company_id not in company_task_cache:
                company_task_cache[company_id] = hs.get_associated_ids("companies", company_id, "tasks")
            company_task_ids = company_task_cache[company_id]

        all_task_ids = list(set(contact_task_ids + company_task_ids))
        active_count = 0

        if all_task_ids:
            tasks = hs.batch_get_objects("tasks", all_task_ids, ["hs_task_status", "hs_timestamp"])
            for task in tasks:
                tprops = task.get("properties", {})
                status = tprops.get("hs_task_status") or ""
                raw_ts = tprops.get("hs_timestamp") or ""
                due_ts_ms = _parse_hs_timestamp(raw_ts)
                if status == "NOT_STARTED" and (due_ts_ms == 0 or due_ts_ms > now_ms):
                    active_count += 1

        result["hs_active_tasks"] = active_count
        if active_count > 0:
            result["contact_fail_reasons"].append(f"tasks: {active_count} active scheduled task(s)")
    except Exception as e:
        result["contact_fail_reasons"].append(f"tasks: error ({e})")

    if result["contact_fail_reasons"]:
        result["contact_eligible"] = False

    return result


# ── Stage 3: Firmable enrichment ───────────────────────────────────────────────

def _enrich_firmable(fc: FirmableClient, domain: str, cache: dict) -> dict:
    """Returns firmable headcount dict. Caches per domain."""
    if domain in cache:
        return cache[domain]

    empty = {"firmable_id": "", "au_sales_team_size": None, "nz_sales_team_size": None,
             "sea_sales_team_size": None, "apac_sales_team_size": None}

    try:
        company = fc.lookup_company(domain)
        firmable_id = company.get("id") or company.get("companyId") or ""
        if not firmable_id:
            cache[domain] = empty
            return empty

        sizes = fc.get_sales_team_size(str(firmable_id))
        au = sizes.get("au_sales_team_size") or 0
        nz = sizes.get("nz_sales_team_size") or 0
        sea = sizes.get("sea_sales_team_size") or 0
        result = {
            "firmable_id": str(firmable_id),
            "au_sales_team_size": sizes.get("au_sales_team_size"),
            "nz_sales_team_size": sizes.get("nz_sales_team_size"),
            "sea_sales_team_size": sizes.get("sea_sales_team_size"),
            "apac_sales_team_size": au + nz + sea,
        }
    except Exception:
        result = empty

    cache[domain] = result
    return result


# ── Main pipeline ──────────────────────────────────────────────────────────────

EMAIL_ALIASES = ["email", "primary_work_email", "work_email"]
DOMAIN_ALIASES = ["domain", "company_website", "website"]


def _resolve_column(df, aliases: list, label: str) -> str:
    """Return the first matching column name from aliases, or raise."""
    for alias in aliases:
        if alias in df.columns:
            return alias
    raise ValueError(
        f"Could not find a '{label}' column. Expected one of: {aliases}. "
        f"Found: {list(df.columns)}"
    )


def run(input_path: str, output_dir: str) -> None:
    hs = HubSpotClient()
    fc = FirmableClient()
    df = load_csv(input_path)

    email_col = _resolve_column(df, EMAIL_ALIASES, "email")
    domain_col = _resolve_column(df, DOMAIN_ALIASES, "domain")

    # Normalise to 'email' and 'domain' for the rest of the pipeline
    if email_col != "email":
        df = df.rename(columns={email_col: "email"})
    if domain_col != "domain":
        df = df.rename(columns={domain_col: "domain"})

    # Strip protocol/path from domain values
    df["domain"] = (
        df["domain"].fillna("").str.strip()
        .str.replace(r"^https?://", "", regex=True)
        .str.replace(r"^www\.", "", regex=True)
        .str.split("/").str[0]
    )

    total_input = len(df)
    df["email"] = df["email"].fillna("").str.strip()
    df_eval = df[(df["email"] != "") & (df["domain"] != "")].copy()
    skipped = total_input - len(df_eval)

    now_ms = int(time.time() * 1000)
    company_hs_cache: dict = {}
    company_task_cache: dict = {}
    firmable_cache: dict = {}

    rows = []
    for i, row in enumerate(df_eval.itertuples(index=False), 1):
        email = row.email
        domain = row.domain

        # Stage 1: company HubSpot check
        co = _check_company(hs, domain, now_ms, company_hs_cache)
        fail_reasons = list(co["fail_reasons"])

        # Stage 2: contact HubSpot check (only if company passed)
        contact_result = {"hs_contact_found": False, "hs_last_contacted": "", "hs_active_tasks": 0}
        if co["eligible"]:
            contact_result = _check_contact(hs, email, company_task_cache, now_ms)
            fail_reasons.extend(contact_result.get("contact_fail_reasons", []))

        eligible = len(fail_reasons) == 0

        # Stage 3: Firmable enrichment (eligible contacts only)
        enrichment = {"firmable_id": "", "au_sales_team_size": None, "nz_sales_team_size": None,
                      "sea_sales_team_size": None, "apac_sales_team_size": None}
        if eligible:
            enrichment = _enrich_firmable(fc, domain, firmable_cache)

        status_label = "PASS" if eligible else "FAIL"
        print(f"[{i}/{len(df_eval)}] {email} → {status_label}" +
              (f" ({' | '.join(fail_reasons)})" if fail_reasons else ""))

        row_dict = row._asdict()
        row_dict.update({
            "eligible": eligible,
            "fail_reason": " | ".join(fail_reasons),
            "hs_company_found": co["found"],
            "hs_trial_status": co["trial_status"],
            "hs_notes_last_contacted": co["notes_last_contacted"],
            "hs_outreach_status": co["outreach_status"],
            "hs_contact_found": contact_result["hs_contact_found"],
            "hs_last_contacted": contact_result["hs_last_contacted"],
            "hs_active_tasks": contact_result["hs_active_tasks"],
            **enrichment,
        })
        rows.append(row_dict)

    out_df = pd.DataFrame(rows)

    ts = timestamp()
    eligible_path = f"{output_dir.rstrip('/')}/eligible_contacts_{ts}.csv"
    full_path = f"{output_dir.rstrip('/')}/eligible_contacts_with_reasons_{ts}.csv"

    save_csv(out_df[out_df["eligible"] == True], eligible_path)
    save_csv(out_df, full_path)

    pass_count = int(out_df["eligible"].sum())
    fail_count = len(out_df) - pass_count

    print(f"\n{'─' * 52}")
    print(f"Contacts in input CSV:   {total_input}")
    print(f"Contacts evaluated:      {len(df_eval)}" +
          (f"   ({skipped} skipped — missing email or domain)" if skipped else ""))
    print(f"Passed (eligible):       {pass_count}")
    print(f"Failed:                  {fail_count}")
    print(f"{'─' * 52}")
    print(f"Eligible CSV:            {eligible_path}")
    print(f"Full report CSV:         {full_path}")


def main():
    parser = argparse.ArgumentParser(description="Pre-campaign eligibility check + Firmable enrichment (read-only).")
    parser.add_argument("--input", required=True, help="CSV with 'email' and 'domain' columns")
    parser.add_argument("--output-dir", default="output", help="Directory to write output CSVs (default: output/)")
    args = parser.parse_args()
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
