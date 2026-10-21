"""
Permanently retire specific mailboxes: remove them from any ACTIVE/PAUSED
SmartLead campaign, and swap their status tag to Retire.

Scope: only ACTIVE and PAUSED campaign memberships are removed. ARCHIVED/COMPLETED
campaigns can never send again, so removing membership there has no functional
effect and is skipped.

Tag handling: only the Active/Retire status tags are ever added or removed.
Every other tag on the account (region tags, vendor tags, etc.) is left untouched.
If a mailbox already has the Retire tag and no Active tag, no tag change is made.

Does not touch Supabase — mailbox_rotation.recommendation is already 'retire'
from the daily rotation_check.py run; is_active self-corrects to false the
next time that script runs once campaign membership is gone.

Usage:
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/retire_mailboxes.py --emails "a@x.com,b@x.com"          # dry run
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/retire_mailboxes.py --emails "a@x.com,b@x.com" --apply  # write to SmartLead
"""

import sys
import time
import argparse
from collections import defaultdict

REMOVE_FROM_STATUSES = {"ACTIVE", "PAUSED"}
STATUS_TAG_NAMES = {"Active", "Standby", "Retire"}
RETIRE_TAG_NAME = "Retire"
ACTIVE_TAG_NAME = "Active"

BATCH_SIZE = 25
RATE_LIMIT_DELAY = 0.2


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


def _batches(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emails", required=True, help="Comma-separated list of mailbox emails to retire")
    parser.add_argument("--apply", action="store_true", help="Apply changes to SmartLead (default: dry run)")
    args = parser.parse_args()

    targets = [e.strip().lower() for e in args.emails.split(",") if e.strip()]
    if not targets:
        print("ERROR: --emails produced no valid addresses.")
        sys.exit(1)

    from scripts.smartlead_client import SmartLeadClient
    sl = SmartLeadClient()

    mode = "APPLY" if args.apply else "DRY RUN"
    divider = "=" * 80
    print(f"\n{divider}")
    print(f"RETIRE MAILBOXES — {mode} — {len(targets)} target(s)")
    print(divider)

    print("\nFetching SmartLead email accounts...")
    accounts = _fetch_all_sl_accounts(sl)
    print(f"  Fetched {len(accounts)} accounts.")

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

    missing = [e for e in targets if e not in sl_map]
    if missing:
        print(f"\nWARNING: {len(missing)} target email(s) not found in SmartLead — skipped:")
        for e in missing:
            print(f"  {e}")
    found = [e for e in targets if e in sl_map]
    if not found:
        print("\nERROR: none of the target emails were found in SmartLead.")
        sys.exit(1)

    target_account_ids = {sl_map[e]["account_id"] for e in found}

    print(f"\nResolving Active/Retire tag ids...")
    existing_tags = sl.list_email_account_tags()
    tag_id_map = {}
    for t in existing_tags:
        name = t.get("tag_name") or t.get("name") or ""
        tid = t.get("tag_id") or t.get("id")
        if name in {ACTIVE_TAG_NAME, RETIRE_TAG_NAME}:
            tag_id_map[name] = tid
    for name in (ACTIVE_TAG_NAME, RETIRE_TAG_NAME):
        if name not in tag_id_map:
            print(f"  ERROR: '{name}' tag not found in SmartLead. Run tag_pools.py first to create status tags.")
            sys.exit(1)
    print(f"  Active tag id={tag_id_map[ACTIVE_TAG_NAME]}, Retire tag id={tag_id_map[RETIRE_TAG_NAME]}")

    print(f"\nScanning campaigns for membership (status in {sorted(REMOVE_FROM_STATUSES)})...")
    campaigns = sl.list_campaigns()
    relevant_campaigns = [c for c in campaigns if c.get("status") in REMOVE_FROM_STATUSES]
    print(f"  {len(relevant_campaigns)} of {len(campaigns)} campaigns are ACTIVE/PAUSED.")

    membership = defaultdict(list)  # account_id -> [(campaign_id, name, status, current_count)]
    for camp in relevant_campaigns:
        camp_id = camp["id"]
        try:
            camp_accounts = sl.get_campaign_email_accounts(camp_id)
        except Exception as e:
            print(f"  ERROR fetching accounts for campaign {camp_id}: {e}")
            continue
        if not camp_accounts:
            continue
        acc_ids_in_camp = {a.get("id") for a in camp_accounts}
        overlap = target_account_ids & acc_ids_in_camp
        for acc_id in overlap:
            membership[acc_id].append((camp_id, camp.get("name", str(camp_id)), camp.get("status"), len(camp_accounts)))

    # Build per-mailbox change plan
    plan = []
    for email in found:
        acc = sl_map[email]
        acc_id = acc["account_id"]
        current_status_tags = {tid: name for tid, name in acc["tag_ids"].items() if name in STATUS_TAG_NAMES}
        has_active = tag_id_map[ACTIVE_TAG_NAME] in current_status_tags
        has_retire = tag_id_map[RETIRE_TAG_NAME] in current_status_tags
        plan.append({
            "email": email,
            "account_id": acc_id,
            "campaigns": membership.get(acc_id, []),
            "remove_active_tag": has_active,
            "add_retire_tag": not has_retire,
        })

    print(f"\nCHANGES PREVIEW")
    for p in plan:
        if p["campaigns"]:
            camp_str = ", ".join(f"{name} ({status}, {count} accts)" for _, name, status, count in p["campaigns"])
        else:
            camp_str = "no ACTIVE/PAUSED memberships"
        tag_parts = []
        if p["remove_active_tag"]:
            tag_parts.append("remove Active")
        if p["add_retire_tag"]:
            tag_parts.append("add Retire")
        tag_str = ", ".join(tag_parts) if tag_parts else "tags already correct"
        print(f"  {p['email']}")
        print(f"    campaigns to remove: {camp_str}")
        print(f"    tag change: {tag_str}")

    if not args.apply:
        print(f"\nRun with --apply to execute these changes in SmartLead.")
        print()
        return

    errors = 0

    print(f"\nRemoving campaign memberships...")
    for p in plan:
        for camp_id, name, status, count in p["campaigns"]:
            try:
                sl.remove_email_accounts_from_campaign(camp_id, [p["account_id"]])
                time.sleep(RATE_LIMIT_DELAY)
                print(f"  Removed {p['email']} from campaign {camp_id} ({name})")
            except Exception as e:
                print(f"  ERROR removing {p['email']} from campaign {camp_id} ({name}): {e}")
                errors += 1

    removals_by_tag = defaultdict(list)
    additions_by_tag = defaultdict(list)
    for p in plan:
        if p["remove_active_tag"]:
            removals_by_tag[tag_id_map[ACTIVE_TAG_NAME]].append(p["account_id"])
        if p["add_retire_tag"]:
            additions_by_tag[tag_id_map[RETIRE_TAG_NAME]].append(p["account_id"])

    if removals_by_tag:
        print(f"\nRemoving Active tag...")
        for tid, account_ids in removals_by_tag.items():
            for batch in _batches(account_ids, BATCH_SIZE):
                try:
                    sl.remove_tags_from_email_accounts(batch, [tid])
                    time.sleep(RATE_LIMIT_DELAY)
                except Exception as e:
                    print(f"  ERROR removing tag {tid} from {len(batch)} accounts: {e}")
                    errors += 1
            print(f"  Removed Active tag from {len(account_ids)} account(s).")

    if additions_by_tag:
        print(f"\nApplying Retire tag...")
        for tid, account_ids in additions_by_tag.items():
            for batch in _batches(account_ids, BATCH_SIZE):
                try:
                    sl.assign_tags_to_email_accounts(batch, [tid])
                    time.sleep(RATE_LIMIT_DELAY)
                except Exception as e:
                    print(f"  ERROR assigning Retire tag to {len(batch)} accounts: {e}")
                    errors += 1
            print(f"  Tagged {len(account_ids)} account(s) as Retire.")

    print(f"\n{divider}")
    print(f"  Done. {len(plan)} mailbox(es) processed, {errors} errors.")
    print()


if __name__ == "__main__":
    main()
