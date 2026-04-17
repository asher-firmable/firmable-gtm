"""
SmartLead Pre-Campaign Check
-----------------------------
Read a company CSV, check each domain against HubSpot, and write
a clean list of eligible companies for SmartLead upload.

Filters OUT companies where:
  1. trial_status = "Active Trial" or "Paying Customer from Trial"
  2. outreach_engagement_status is set and not "Pool" or "Time Out"
  3. notes_last_contacted (company level) is within the last 30 days
  4. Any active (NOT_STARTED, no/future due date) company-level task exists

Companies NOT found in HubSpot are treated as eligible by default.

Domain matching: ccTLD suffixes are stripped before lookup (e.g. shopify.com.au → shopify.com)
so that both shopify.com and shopify.com.au stored in HubSpot are caught.

Usage:
  PYTHONPATH=. python3 scripts/smartlead_pre_campaign_check.py \\
    --output eligible_acme_campaign.csv

  # With explicit input path:
  PYTHONPATH=. python3 scripts/smartlead_pre_campaign_check.py \\
    --input campaigns/company-checks/input/companies.csv \\
    --output eligible_acme_campaign.csv
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from scripts.hubspot_client import HubSpotClient

# ── Constants ──────────────────────────────────────────────────────────────────

TRIAL_EXCLUDE      = {"Active Trial", "Paying Customer from Trial"}
ELIGIBLE_OUTREACH  = {"Pool", "Time Out"}
THIRTY_DAYS_MS     = 30 * 24 * 60 * 60 * 1000

DOMAIN_COLS        = ["domain", "website", "company_website", "company_domain"]
NAME_COLS          = ["name", "company_name", "company"]
FIRMABLE_LINK_COLS = [
    "firmable company link", "firmable_company_link",
    "firmable link",         "firmable_link",
    "firmable url",          "firmable_url",
]

# Second-level domains that appear before a 2-letter ccTLD (e.g. .com.au, .net.au, .co.nz)
COMMON_SLD = {"com", "net", "org", "co", "edu", "gov", "biz"}

DEFAULT_INPUT_DIR  = Path("campaigns/company-checks/input")
DEFAULT_OUTPUT_DIR = Path("campaigns/company-checks/output")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_col(headers: list, candidates: list) -> Optional[str]:
    """Return first matching column name (case-insensitive), or None."""
    lower = {h.lower(): h for h in headers}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def _clean_domain(raw: str) -> str:
    """Strip protocol, www, and path segments from a URL or domain string."""
    d = raw.strip().lower()
    d = d.replace("https://", "").replace("http://", "")
    d = d.replace("www.", "")
    return d.split("/")[0].strip()


def _root_domain(domain: str) -> str:
    """Strip ccTLD from second-level domains so CONTAINS search catches both variants.

    Examples:
      google.com.au  -> google.com
      shopify.com.sg -> shopify.com
      example.co.nz  -> example.co
      microsoft.com  -> microsoft.com  (unchanged)
    """
    parts = domain.split(".")
    if (
        len(parts) >= 3
        and len(parts[-1]) == 2           # 2-letter ccTLD (au, sg, nz, uk, …)
        and parts[-2] in COMMON_SLD       # preceded by com / net / org / co / …
    ):
        return ".".join(parts[:-1])
    return domain


def _extract_firmable_id(link: str) -> str:
    """Extract the ID from a Firmable company URL.

    https://app.firmable.com/companies/12345  ->  '12345'
    """
    if not link:
        return ""
    path = urlparse(link.strip()).path
    return path.rstrip("/").split("/")[-1]


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


# ── HubSpot check ──────────────────────────────────────────────────────────────

def _check_company(hs: HubSpotClient, root: str, now_ms: int, cache: dict) -> dict:
    """Look up company by root domain and run all eligibility checks.

    Returns dict: {found, eligible, fail_reasons}.
    Results are cached per root domain to avoid duplicate API calls.
    """
    if root in cache:
        return cache[root]

    not_found = {"found": False, "eligible": True, "fail_reasons": []}

    companies = hs.search_companies(root)
    if not companies:
        cache[root] = not_found
        return not_found

    company_id = companies[0]["id"]

    props = hs.get_company_properties(
        company_id,
        ["trial_status", "outreach_engagement_status", "notes_last_contacted"],
    )
    time.sleep(0.1)

    trial_status    = (props.get("trial_status") or "").strip()
    outreach_status = (props.get("outreach_engagement_status") or "").strip()
    notes_last      = (props.get("notes_last_contacted") or "").strip()

    fail_reasons = []

    # Check 1: trial / paying customer
    if trial_status in TRIAL_EXCLUDE:
        fail_reasons.append(f"trial: {trial_status}")

    # Check 2: outreach engagement status (blank = pass)
    if outreach_status and outreach_status not in ELIGIBLE_OUTREACH:
        fail_reasons.append(f"outreach status: '{outreach_status}'")

    # Check 3: recent communications (company-level)
    if notes_last:
        nlc_ms = _parse_hs_timestamp(notes_last)
        if nlc_ms > 0 and nlc_ms >= now_ms - THIRTY_DAYS_MS:
            fail_reasons.append("comms: contacted within 30 days")

    # Check 4: active company-level tasks (only run if checks 1-3 passed)
    if not fail_reasons:
        try:
            task_ids = hs.get_associated_ids("companies", company_id, "tasks")
            if task_ids:
                tasks = hs.batch_get_objects(
                    "tasks", task_ids, ["hs_task_status", "hs_timestamp"]
                )
                for task in tasks:
                    tp      = task.get("properties", {})
                    status  = tp.get("hs_task_status") or ""
                    due_raw = tp.get("hs_timestamp") or ""
                    due_ms  = _parse_hs_timestamp(due_raw)
                    if status == "NOT_STARTED" and (due_ms == 0 or due_ms > now_ms):
                        fail_reasons.append("tasks: active scheduled task on company")
                        break
            time.sleep(0.1)
        except Exception as e:
            fail_reasons.append(f"tasks: error checking ({e})")

    result = {
        "found":        True,
        "eligible":     len(fail_reasons) == 0,
        "fail_reasons": fail_reasons,
    }
    cache[root] = result
    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SmartLead pre-campaign eligibility check (company-level, read-only)."
    )
    parser.add_argument(
        "--input", required=False,
        help="Path to input CSV (default: latest CSV in campaigns/company-checks/input/)",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output filename, e.g. eligible_acme.csv — written to campaigns/company-checks/output/",
    )
    args = parser.parse_args()

    # ── Resolve input ──────────────────────────────────────────────────────────
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
    else:
        csvs = sorted(
            DEFAULT_INPUT_DIR.glob("*.csv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not csvs:
            raise FileNotFoundError(
                f"No CSV found in {DEFAULT_INPUT_DIR}. "
                "Drop a company CSV there and retry, or pass --input <path>."
            )
        input_path = csvs[0]
        print(f"Auto-detected input: {input_path.name}")

    # ── Resolve output ─────────────────────────────────────────────────────────
    output_filename = args.output
    if not output_filename.endswith(".csv"):
        output_filename += ".csv"
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DEFAULT_OUTPUT_DIR / output_filename

    # ── Load CSV ───────────────────────────────────────────────────────────────
    with open(input_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
        headers = reader.fieldnames or []

    domain_col    = _find_col(headers, DOMAIN_COLS)
    name_col      = _find_col(headers, NAME_COLS)
    firmable_col  = _find_col(headers, FIRMABLE_LINK_COLS)

    if not domain_col:
        raise ValueError(
            f"No domain column found. Expected one of: {DOMAIN_COLS}\n"
            f"Columns in file: {headers}"
        )

    total = len(rows)
    print(f"Loaded {total} companies from {input_path.name}")
    print(f"  Domain column        : {domain_col}")
    print(f"  Name column          : {name_col or '(not found — using row index)'}")
    print(f"  Firmable link column : {firmable_col or '(not found)'}")
    print()

    hs     = HubSpotClient()
    now_ms = int(time.time() * 1000)
    cache  = {}

    skipped  = []
    filtered = []   # list of {name, domain, reasons}
    eligible = []   # list of output row dicts

    filter_counts = {"trial": 0, "outreach_status": 0, "comms": 0, "tasks": 0}

    for i, row in enumerate(rows, 1):
        name          = (row.get(name_col) or f"Row {i}").strip() if name_col else f"Row {i}"
        raw_domain    = (row.get(domain_col) or "").strip()
        firmable_link = (row.get(firmable_col) or "").strip() if firmable_col else ""

        print(f"[{i}/{total}] {name} | {raw_domain or '(no domain)'}", end=" ... ", flush=True)

        if not raw_domain:
            print("SKIPPED (no domain)")
            skipped.append(name)
            continue

        domain = _clean_domain(raw_domain)
        root   = _root_domain(domain)

        result = _check_company(hs, root, now_ms, cache)
        time.sleep(0.1)

        if not result["eligible"]:
            reasons_str = " | ".join(result["fail_reasons"])
            print(f"FILTERED ({reasons_str})")
            filtered.append({"name": name, "domain": domain, "reasons": reasons_str})
            for r in result["fail_reasons"]:
                if r.startswith("trial"):
                    filter_counts["trial"] += 1
                elif r.startswith("outreach"):
                    filter_counts["outreach_status"] += 1
                elif r.startswith("comms"):
                    filter_counts["comms"] += 1
                elif r.startswith("tasks"):
                    filter_counts["tasks"] += 1
        else:
            note = " (not in HubSpot)" if not result["found"] else ""
            print(f"ELIGIBLE{note}")
            firmable_id = _extract_firmable_id(firmable_link)
            eligible.append({
                "company_name":          name,
                "domain":                domain,
                "firmable_company_link": firmable_link,
                "firmable_company_id":   firmable_id,
            })

    # ── Terminal summary ───────────────────────────────────────────────────────
    sep = "=" * 60
    print(f"\n{sep}")
    print("SUMMARY")
    print(sep)
    print(f"  Total companies:                {total}")
    print(f"  Skipped (no domain):            {len(skipped)}")
    print(f"  Filtered — trial/customer:      {filter_counts['trial']}")
    print(f"  Filtered — outreach status:     {filter_counts['outreach_status']}")
    print(f"  Filtered — comms < 30 days:     {filter_counts['comms']}")
    print(f"  Filtered — active tasks:        {filter_counts['tasks']}")
    print(f"  ELIGIBLE:                       {len(eligible)}")
    print(sep)

    if filtered:
        print(f"\nFiltered companies:")
        for c in filtered:
            print(f"  - {c['name']} | {c['domain']} | {c['reasons']}")

    # ── Write output CSV ───────────────────────────────────────────────────────
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "domain", "firmable_company_link", "firmable_company_id"],
        )
        writer.writeheader()
        writer.writerows(eligible)

    print(f"\nSaved: {output_path}  ({len(eligible)} eligible companies)")
    print()


if __name__ == "__main__":
    main()
