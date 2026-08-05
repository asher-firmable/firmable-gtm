"""
Tag mailboxes in SmartLead with pool status: Active, Standby, or Retire.

Data source: Supabase mailbox_rotation table (populated by rotation_check.py).
SmartLead is used to fetch account IDs, apply bulk tag assignments and removals.

Tags applied:
  Active  — currently in campaigns (green)
  Standby — backup pool, not in campaigns (amber)
  Retire  — both reply signals failing, should be removed (red)

Existing tags (US Campaigns, SEA Campaigns, ANZ Campaigns, InboxKit, ScaledMail, etc.)
are never touched. Only the three status tags above are managed by this script.

US split: all US mailboxes are currently in active campaigns, so non-retiring US
mailboxes are split 50/50 alphabetically — first half Active, second half Standby.

SEA/ANZ split: based on actual pool status from Supabase
(pool=sending → Active, pool=not_sending → Standby).

Usage:
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/tag_pools.py          # dry run
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/tag_pools.py --apply  # write to SmartLead
"""

import os
import sys
import time
import argparse
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

REGIONS = ["US", "SEA", "ANZ"]
SUPABASE_TABLE = "mailbox_rotation"

STATUS_TAG_NAMES = {"Active", "Standby", "Retire"}
TAG_COLORS = {
    "Active":  "#22c55e",
    "Standby": "#f59e0b",
    "Retire":  "#ef4444",
}

BATCH_SIZE = 25     # SmartLead tag-mapping allows up to 25 accounts per call
RATE_LIMIT_DELAY = 0.2


def _fetch_supabase_data(sb):
    resp = (
        sb.table(SUPABASE_TABLE)
        .select("email, region, pool, recommendation, last_checked_at")
        .in_("region", REGIONS)
        .execute()
    )
    return resp.data or []


def _compute_desired_tags(rows):
    by_region = defaultdict(list)
    for row in rows:
        by_region[row["region"]].append(row)

    desired = {}
    for region, region_rows in by_region.items():
        retiring     = [r for r in region_rows if r["recommendation"] == "retire"]
        non_retiring = [r for r in region_rows if r["recommendation"] != "retire"]

        for row in retiring:
            desired[row["email"]] = "Retire"

        if region == "US":
            sorted_rows = sorted(non_retiring, key=lambda r: r["email"].lower())
            half = len(sorted_rows) // 2
            for i, row in enumerate(sorted_rows):
                desired[row["email"]] = "Active" if i < half else "Standby"
        else:
            for row in non_retiring:
                desired[row["email"]] = "Active" if row["pool"] == "sending" else "Standby"

    return desired


def _fetch_all_sl_accounts(sl):
    accounts = []
    offset = 0
    limit = 100
    while True:
        batch = sl.get_email_accounts(limit=limit, offset=offset)
        if not batch:
            break
        accounts.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return accounts


def _ensure_status_tags(sl, apply: bool):
    existing = sl.list_email_account_tags()
    tag_map = {}
    for t in existing:
        name = t.get("tag_name") or t.get("name") or ""
        tid  = t.get("tag_id") or t.get("id")
        if name in STATUS_TAG_NAMES:
            tag_map[name] = tid

    for name in STATUS_TAG_NAMES:
        if name not in tag_map:
            if apply:
                result = sl.create_email_account_tag(name, TAG_COLORS[name])
                data = result.get("data") or result
                new_id = data.get("tag_id") or data.get("id")
                if not new_id:
                    print(f"  ERROR: Failed to create tag '{name}': {result}")
                    sys.exit(1)
                tag_map[name] = new_id
                print(f"  Created tag '{name}' (id={new_id})")
                time.sleep(RATE_LIMIT_DELAY)
            else:
                tag_map[name] = f"<new:{name}>"

    return tag_map


def _batches(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes to SmartLead (default: dry run)")
    args = parser.parse_args()

    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed. Run: pip3 install supabase")
        sys.exit(1)

    from scripts.smartlead_client import SmartLeadClient

    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not sb_url or not sb_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    sb = create_client(sb_url, sb_key)
    sl = SmartLeadClient()

    mode = "APPLY" if args.apply else "DRY RUN"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    divider = "=" * 80
    print(f"\n{divider}")
    print(f"TAG POOL STATUS — {mode} — {now_str}")
    print(divider)

    print("\nFetching Supabase data...")
    rows = _fetch_supabase_data(sb)
    if not rows:
        print("ERROR: No rows returned from Supabase. Run rotation_check.py first.")
        sys.exit(1)

    timestamps = [r["last_checked_at"] for r in rows if r.get("last_checked_at")]
    freshness = max(timestamps) if timestamps else "unknown"
    if isinstance(freshness, str) and freshness != "unknown":
        try:
            dt = datetime.fromisoformat(freshness.replace("Z", "+00:00"))
            freshness = dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            pass
    print(f"Supabase data as of: {freshness}")

    desired = _compute_desired_tags(rows)

    print()
    for region in REGIONS:
        region_rows = [r for r in rows if r["region"] == region]
        counts = defaultdict(int)
        for row in region_rows:
            counts[desired.get(row["email"], "—")] += 1
        parts = [f"{counts[t]} {t}" for t in ["Active", "Standby", "Retire"] if counts[t]]
        print(f"  {region:<4}  {' | '.join(parts)}")

    print(f"\nFetching SmartLead email accounts...")
    accounts = _fetch_all_sl_accounts(sl)
    print(f"  Fetched {len(accounts)} accounts.")

    # Build email -> account map
    sl_map = {}
    for acc in accounts:
        email = (
            acc.get("from_email") or acc.get("username") or
            acc.get("email") or acc.get("smtp_username") or ""
        ).lower().strip()
        if email:
            tags = acc.get("tags") or []
            sl_map[email] = {
                "account_id": acc["id"],
                "tag_ids": {(t.get("tag_id") or t.get("id")): (t.get("tag_name") or t.get("name") or "") for t in tags},
            }

    tag_id_map = _ensure_status_tags(sl, args.apply)

    # Per-mailbox change plan
    changes = []
    skipped = []
    for row in sorted(rows, key=lambda r: (r["region"], r["email"].lower())):
        email = row["email"].lower().strip()
        desired_tag = desired.get(row["email"])
        if not desired_tag:
            continue
        if email not in sl_map:
            skipped.append(row["email"])
            continue

        acc = sl_map[email]
        current_status = {tid: name for tid, name in acc["tag_ids"].items() if name in STATUS_TAG_NAMES}
        to_remove = {tid: name for tid, name in current_status.items() if name != desired_tag}
        already_correct = desired_tag in current_status.values()

        changes.append({
            "email":           row["email"],
            "region":          row["region"],
            "account_id":      acc["account_id"],
            "desired_tag":     desired_tag,
            "to_remove_ids":   list(to_remove.keys()),
            "to_remove_names": list(to_remove.values()),
            "already_correct": already_correct,
        })

    needs_change = [c for c in changes if not c["already_correct"] or c["to_remove_ids"]]
    already_ok   = [c for c in changes if c["already_correct"] and not c["to_remove_ids"]]

    print(f"\nCHANGES PREVIEW — {len(needs_change)} mailboxes to update, {len(already_ok)} already correct")
    if skipped:
        print(f"  WARNING: {len(skipped)} mailboxes in Supabase not found in SmartLead — skipped")

    if needs_change:
        print()
        for c in needs_change:
            remove_str = ", ".join(c["to_remove_names"]) if c["to_remove_names"] else "—"
            print(f"  {c['email']:<46}  {c['region']:<4}  remove: {remove_str:<12}  add: {c['desired_tag']}")

    if not args.apply:
        print(f"\nRun with --apply to execute these changes in SmartLead.")
        print()
        return

    # Group by operation for bulk calls
    # Removals: group by tag_id being removed -> list of account_ids
    removals_by_tag = defaultdict(list)
    for c in needs_change:
        for tid in c["to_remove_ids"]:
            removals_by_tag[tid].append(c["account_id"])

    # Additions: group by desired_tag -> list of account_ids (only those not already correct)
    additions_by_tag = defaultdict(list)
    for c in needs_change:
        if not c["already_correct"]:
            additions_by_tag[c["desired_tag"]].append(c["account_id"])

    errors = 0

    if removals_by_tag:
        print(f"\nRemoving old status tags...")
        for tid, account_ids in removals_by_tag.items():
            for batch in _batches(account_ids, BATCH_SIZE):
                try:
                    sl.remove_tags_from_email_accounts(batch, [tid])
                    time.sleep(RATE_LIMIT_DELAY)
                except Exception as e:
                    print(f"  ERROR removing tag {tid} from {len(batch)} accounts: {e}")
                    errors += 1
            print(f"  Removed tag id={tid} from {len(account_ids)} accounts.")

    if additions_by_tag:
        print(f"\nApplying new status tags...")
        for tag_name, account_ids in additions_by_tag.items():
            tag_id = tag_id_map[tag_name]
            for batch in _batches(account_ids, BATCH_SIZE):
                try:
                    sl.assign_tags_to_email_accounts(batch, [tag_id])
                    time.sleep(RATE_LIMIT_DELAY)
                except Exception as e:
                    print(f"  ERROR assigning '{tag_name}' to {len(batch)} accounts: {e}")
                    errors += 1
            print(f"  Tagged {len(account_ids)} accounts as '{tag_name}'.")

    print(f"\n{divider}")
    print(f"  Done. {len(needs_change)} updated, {errors} errors, {len(already_ok)} already correct.")
    print()


if __name__ == "__main__":
    main()
