"""
Standby pool check.

Reads the mailbox_rotation Supabase table (populated by rotation_check.py)
and reports which mailboxes are available to swap IN per region:
  - Currently inactive (pool = not_sending)
  - Tagged US / SEA / ANZ
  - Warmup reputation >= 95%
  - Not already flagged retire or move_to_warmup

Also shows how many retirements are pending per region so you can see
immediately whether you have enough standby coverage.

Run from repo root:
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/standby_check.py
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

REGIONS = ["US", "SEA", "ANZ"]
SUPABASE_TABLE = "mailbox_rotation"
WARMUP_THRESHOLD = 95


def main():
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed. Run: pip3 install supabase")
        sys.exit(1)

    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not sb_url or not sb_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    sb = create_client(sb_url, sb_key)

    # Standby candidates
    standby_resp = (
        sb.table(SUPABASE_TABLE)
        .select(
            "email, region, vendor, warmup_rep, recommendation, recommendation_reason, "
            "at_reply_rate, reply_14d_rate, bounce_rate, days_in_pool, last_checked_at"
        )
        .in_("region", REGIONS)
        .eq("pool", "not_sending")
        .gte("warmup_rep", WARMUP_THRESHOLD)
        .not_.in_("recommendation", ["retire", "move_to_warmup"])
        .execute()
    )

    # Retire-pending per region (for coverage gap calculation)
    retire_resp = (
        sb.table(SUPABASE_TABLE)
        .select("email, region")
        .in_("region", REGIONS)
        .eq("recommendation", "retire")
        .execute()
    )

    standby_rows = standby_resp.data or []
    retire_rows  = retire_resp.data or []

    # Group
    standby_by_region = defaultdict(list)
    for row in standby_rows:
        standby_by_region[row["region"]].append(row)

    retire_count_by_region = defaultdict(int)
    for row in retire_rows:
        retire_count_by_region[row["region"]] += 1

    # Data freshness
    timestamps = [r["last_checked_at"] for r in standby_rows if r.get("last_checked_at")]
    if not timestamps:
        # fall back to retire rows to show something
        timestamps = [r.get("last_checked_at") for r in retire_rows if r.get("last_checked_at")]
    freshness = max(timestamps) if timestamps else "unknown"
    if isinstance(freshness, str) and freshness != "unknown":
        try:
            dt = datetime.fromisoformat(freshness.replace("Z", "+00:00"))
            freshness = dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            pass

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    divider = "=" * 90

    print(f"\n{divider}")
    print(f"STANDBY POOL CHECK — {now_str}")
    print(f"Data as of: {freshness}")
    print(divider)

    total_standby = 0
    total_retire  = 0

    for region in REGIONS:
        candidates = sorted(standby_by_region[region], key=lambda r: r["email"])
        retire_n   = retire_count_by_region[region]
        standby_n  = len(candidates)
        gap        = retire_n - standby_n

        total_standby += standby_n
        total_retire  += retire_n

        if gap > 0:
            coverage = f"GAP — need {gap} more"
        else:
            coverage = "OK"

        print(f"\n  {region:<4}  {standby_n} standby available  |  retire pending: {retire_n}  |  {coverage}")

        if candidates:
            for row in candidates:
                email   = row["email"]
                vendor  = (row.get("vendor") or "—").ljust(12)
                warmup  = f"Warmup: {row['warmup_rep']:.0f}%" if row.get("warmup_rep") is not None else "Warmup: —"
                at      = f"AT: {row['at_reply_rate']:.2f}%"  if row.get("at_reply_rate")  is not None else "AT: —"
                r14     = f"14d: {row['reply_14d_rate']:.2f}%" if row.get("reply_14d_rate") is not None else "14d: —"
                days    = f"{row['days_in_pool']}d in pool" if row.get("days_in_pool") is not None else ""
                print(f"    {email:<44}  {vendor}  {warmup:<14}  {at:<12}  {r14:<14}  {days}")
        else:
            print(f"    (none available)")

    print(f"\n{divider}")
    print(f"  Total standby: {total_standby}  |  Total retire pending: {total_retire}")
    if total_retire > total_standby:
        print(f"  WARNING: {total_retire - total_standby} more retirements than standby mailboxes available.")
    else:
        print(f"  Standby coverage looks sufficient.")
    print()


if __name__ == "__main__":
    main()
