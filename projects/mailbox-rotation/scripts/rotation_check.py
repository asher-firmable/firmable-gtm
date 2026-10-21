"""
Mailbox rotation health check.

Reads health signals from SmartLead for every mailbox, applies rotation
recommendation logic, upserts state to Supabase, prints a prioritised
action report, and sends a Slack summary.

Does NOT write to SmartLead — read-only from SmartLead, write to Supabase only.

Recommendation rules (only evaluated once a mailbox has sent more than
MIN_SENDS_FOR_CLASSIFICATION emails all-time — below that there isn't enough
data for reply/bounce rates to mean anything):
  RETIRE         — both reply signals below 1% (AT and 14d both failing, with data)
  MOVE_TO_WARMUP — warmup reputation < 95% (and not retiring)
  MONITOR        — at least one reply signal passing but not all 3 healthy
  NO_ACTION      — all signals healthy

Run from repo root:
    PYTHONPATH=. python3 projects/mailbox-rotation/scripts/rotation_check.py
"""

import os
import sys
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from scripts.smartlead_client import SmartLeadClient
from scripts.smartlead_domain_reply_analysis import (
    build_account_domain_map,
    fetch_alltime_stats_per_account,
    fetch_active_campaigns_per_account,
    fetch_replies_per_account,
)

REGION_TAGS = {365624: "US", 354236: "SEA", 354235: "ANZ"}
LOOKBACK_DAYS = 14
SUPABASE_TABLE = "mailbox_rotation"
MIN_SENDS_FOR_CLASSIFICATION = 100


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(warmup_rep, at_reply_rate, reply_14d_rate, bounce_rate, alltime_sent):
    """
    Returns (recommendation, reason, signals_passing).

    Priority: retire > move_to_warmup > monitor > no_action

    RETIRE only when both reply signals have data and both are below 1%.
    If 14d is unavailable (inactive mailbox), fall through to monitor.
    """
    if not alltime_sent or alltime_sent < MIN_SENDS_FOR_CLASSIFICATION:
        return "monitor", f"Under {MIN_SENDS_FOR_CLASSIFICATION} emails sent — not enough data to classify", None

    at_ok = at_reply_rate is not None and at_reply_rate >= 1.0
    r14d_ok = reply_14d_rate is not None and reply_14d_rate >= 1.0
    bounce_ok = bounce_rate is not None and bounce_rate < 3.0

    either_reply_ok = at_ok or r14d_ok
    passing = sum([at_ok, r14d_ok, bounce_ok])

    if not either_reply_ok and reply_14d_rate is not None:
        failing = []
        if at_reply_rate is not None:
            failing.append(f"AT {at_reply_rate:.2f}% (needs ≥1%)")
        if reply_14d_rate is not None:
            failing.append(f"14d {reply_14d_rate:.2f}% (needs ≥1%)")
        return "retire", "; ".join(failing), passing

    if warmup_rep is not None and warmup_rep < 95:
        return "move_to_warmup", f"Warmup {warmup_rep:.0f}% (needs ≥95%)", passing

    if passing < 3:
        failing = []
        if not at_ok:
            if at_reply_rate is not None:
                failing.append(f"AT {at_reply_rate:.2f}% (needs ≥1%)")
        if not r14d_ok:
            if reply_14d_rate is not None:
                failing.append(f"14d {reply_14d_rate:.2f}% (needs ≥1%)")
            else:
                failing.append("14d — (not in active campaign)")
        if not bounce_ok and bounce_rate is not None:
            failing.append(f"Bounce {bounce_rate:.2f}% (needs <3%)")
        return "monitor", "; ".join(failing) if failing else "1 signal below threshold", passing

    return "no_action", "All signals healthy", passing


def _get_region(tag_ids: set) -> str:
    for tag_id, name in REGION_TAGS.items():
        if tag_id in tag_ids:
            return name
    return None


# ---------------------------------------------------------------------------
# Terminal output helpers
# ---------------------------------------------------------------------------

def _fmt_signal(label, value, threshold_fn, width=20):
    if value is None:
        s = f"{label}: —"
    else:
        mark = "ok" if threshold_fn(value) else "!!"
        s = f"{label}: {value:.2f}% [{mark}]"
    return s.ljust(width)


def _fmt_warmup(rep):
    if rep is None:
        return "Warmup: —".ljust(16)
    mark = "ok" if rep >= 95 else "!!"
    return f"Warmup: {rep:.0f}% [{mark}]".ljust(16)


def _signal_line(m):
    region = (m["region"] or "?").ljust(3)
    active_tag = "ACTIVE" if m["is_active"] else "      "
    at_s = _fmt_signal("AT", m["at_reply_rate"], lambda v: v >= 1.0)
    r14_s = _fmt_signal("14d", m["reply_14d_rate"], lambda v: v >= 1.0)
    b_s = _fmt_signal("Bounce", m["bounce_rate"], lambda v: v < 3.0)
    w_s = _fmt_warmup(m["warmup_rep"])
    sent_s = f"  Sent: {m.get('total_sent', 0)}"
    return f"  {m['email']:<42} {region} {active_tag}  {at_s}{r14_s}{b_s}{w_s}{sent_s}"


# ---------------------------------------------------------------------------
# Slack notification
# ---------------------------------------------------------------------------

def _build_slack_message(mailboxes: dict, prev_recs: dict, now: datetime, fetch_failures: list = None) -> str:
    retire = [m for m in mailboxes.values() if m["recommendation"] == "retire"]
    warmup = [m for m in mailboxes.values() if m["recommendation"] == "move_to_warmup"]
    monitor = [m for m in mailboxes.values() if m["recommendation"] == "monitor"]
    no_action = [m for m in mailboxes.values() if m["recommendation"] == "no_action"]

    active_count   = sum(1 for m in mailboxes.values() if m["is_active"])
    inactive_count = sum(1 for m in mailboxes.values() if not m["is_active"])

    lines = [f"📊 *Mailbox Rotation Check — {now.strftime('%Y-%m-%d')}*\n"]

    if fetch_failures:
        lines.append(
            f"⚠️ *{len(fetch_failures)} SmartLead fetch failure(s) this run* — "
            f"activity data below may be incomplete for the affected campaigns:"
        )
        for f in fetch_failures:
            lines.append(f"  • {f}")
        lines.append("")

    lines.append(f"📬 *{active_count} mailboxes active in campaigns* · *{inactive_count} inactive*\n")

    # RETIRE — individual mailboxes
    lines.append(f"⛔ *RETIRE ({len(retire)} mailboxes)* — remove from campaigns permanently")
    if retire:
        for m in sorted(retire, key=lambda x: (x["region"] or "zzz", x["email"])):
            active_note = " ✉" if m["is_active"] else ""
            lines.append(f"  • `{m['email']}` ({m['region'] or '?'}){active_note} — {m['recommendation_reason']}")
    else:
        lines.append("  _none_")

    lines.append("")

    # MOVE TO WARMUP
    lines.append(f"🔁 *MOVE TO WARMUP ({len(warmup)})* — pull from campaigns, let warmup recover")
    if warmup:
        for m in sorted(warmup, key=lambda x: (x["region"] or "zzz", x["email"])):
            lines.append(f"  • `{m['email']}` ({m['region'] or '?'}) — {m['recommendation_reason']}")
    else:
        lines.append("  _none_")

    lines.append("")
    lines.append(f"👀 *MONITOR ({len(monitor)})* — one signal below threshold, no action yet")
    lines.append(f"✅ *NO ACTION ({len(no_action)})* — all signals healthy")
    lines.append("")

    # Changes since last run
    newly_retired = [
        e for e, m in mailboxes.items()
        if m["recommendation"] == "retire" and prev_recs.get(e) != "retire"
        and prev_recs.get(e) is not None  # skip first-run (no prior state)
    ]
    newly_resolved = [
        e for e, m in mailboxes.items()
        if m["recommendation"] == "no_action"
        and prev_recs.get(e) in ("retire", "monitor", "move_to_warmup")
    ]

    lines.append("🆕 *Changes since last run*")
    lines.append(f"  • {len(newly_retired)} newly flagged for retirement")
    lines.append(f"  • {len(newly_resolved)} resolved (back to healthy)")

    return "\n".join(lines)


def _send_slack(message: str):
    webhook_url = os.getenv("SLACK_MAILBOX_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        resp.raise_for_status()
        print("  Slack notification sent.")
    except Exception as e:
        print(f"  WARNING: Slack notification failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    api_key = os.getenv("SMARTLEAD_API_KEY")
    if not api_key:
        print("ERROR: SMARTLEAD_API_KEY not set in .env")
        sys.exit(1)

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

    sl = SmartLeadClient()
    sb = create_client(sb_url, sb_key)

    now = datetime.now(timezone.utc)
    print(f"\n=== MAILBOX ROTATION CHECK — {now.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    # 1. Fetch SmartLead data
    print("Fetching account data...")
    id_to_domain, id_to_email, id_to_vendor, _, id_to_tag_ids, id_to_warmup_rep, id_to_from_name = (
        build_account_domain_map(sl)
    )
    print(f"  {len(id_to_email)} mailboxes found")

    print("Fetching campaigns...")
    campaigns = sl.list_campaigns()
    print(f"  {len(campaigns)} campaigns")

    print("Fetching all-time stats per mailbox...")
    alltime_sent, alltime_replies, alltime_bounces, alltime_failures = fetch_alltime_stats_per_account(sl, campaigns)

    print("Fetching active campaign assignments...")
    active_count, active_sent, active_campaigns, n_active, active_failures = fetch_active_campaigns_per_account(sl, campaigns)

    fetch_failures = alltime_failures + active_failures
    if fetch_failures:
        print(f"\n  {len(fetch_failures)} SmartLead fetch failure(s) this run — activity data may be incomplete for affected campaigns:")
        for f in fetch_failures:
            print(f"    - {f}")

    print(f"Fetching {LOOKBACK_DAYS}-day replies...")
    start_iso = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end_iso = now.strftime("%Y-%m-%d")
    replies_14d = fetch_replies_per_account(sl, start_iso, end_iso)

    # 2. Read existing Supabase state
    print("Reading existing Supabase state...")
    existing = {}
    try:
        resp = sb.table(SUPABASE_TABLE).select(
            "email,recommendation,recommendation_reason"
        ).execute()
        for row in (resp.data or []):
            existing[row["email"]] = row
        print(f"  {len(existing)} existing rows")
    except Exception as e:
        print(f"  WARNING: Could not read existing state ({e})")

    prev_recs = {e: r.get("recommendation") for e, r in existing.items()}

    # 3. Classify each mailbox
    now_iso = now.isoformat()
    mailboxes = {}

    for acc_id in id_to_email:
        email = id_to_email[acc_id]
        if not email or email.startswith("unknown-"):
            continue

        a_sent = alltime_sent.get(acc_id, 0)
        a_replies = alltime_replies.get(acc_id, 0)
        a_bounces = alltime_bounces.get(acc_id, 0)
        ac_sent = active_sent.get(acc_id, 0)
        r14d = replies_14d.get(acc_id, 0)
        warmup = id_to_warmup_rep.get(acc_id)
        is_active = active_count.get(acc_id, 0) > 0

        at_rate = (a_replies / a_sent * 100) if a_sent > 0 else None
        r14d_rate = (r14d / ac_sent * 100) if ac_sent > 0 else None
        bounce_rate = (a_bounces / a_sent * 100) if a_sent > 0 else None

        rec, reason, signals_passing = classify(warmup, at_rate, r14d_rate, bounce_rate, a_sent)

        old = existing.get(email, {})
        if old.get("recommendation") == "retire":
            # Retire is permanent — once flagged, a mailbox stays retired even if its
            # signals look better later (e.g. it goes inactive and 14d data disappears).
            # Reactivating a retired mailbox is a manual decision, not something the
            # daily classifier should undo on its own.
            rec = "retire"
            reason = old.get("recommendation_reason") or reason

        mailboxes[email] = {
            "email": email,
            "from_name": id_to_from_name.get(acc_id),
            "region": _get_region(id_to_tag_ids.get(acc_id, set())),
            "vendor": id_to_vendor.get(acc_id, "") or "",
            "is_active": is_active,
            "total_sent": int(round(a_sent)),
            "warmup_rep": warmup,
            "at_reply_rate": round(at_rate, 4) if at_rate is not None else None,
            "reply_14d_rate": round(r14d_rate, 4) if r14d_rate is not None else None,
            "bounce_rate": round(bounce_rate, 4) if bounce_rate is not None else None,
            "signals_passing": signals_passing,
            "recommendation": rec,
            "recommendation_reason": reason,
            "last_checked_at": now_iso,
        }

    # 4. Upsert to Supabase
    print(f"\nWriting {len(mailboxes)} rows to Supabase ({SUPABASE_TABLE})...")
    rows = list(mailboxes.values())
    batch_size = 200
    written = 0
    for i in range(0, len(rows), batch_size):
        sb.table(SUPABASE_TABLE).upsert(
            rows[i:i + batch_size],
            on_conflict="email",
        ).execute()
        written += len(rows[i:i + batch_size])
    print(f"  {written} rows upserted")

    # 5. Print terminal report
    buckets = {"retire": [], "move_to_warmup": [], "monitor": [], "no_action": []}
    for m in mailboxes.values():
        buckets[m["recommendation"]].append(m)

    for k in buckets:
        buckets[k].sort(key=lambda m: (not m["is_active"], m["region"] or "zzz", m["email"]))

    active_count = sum(1 for m in mailboxes.values() if m["is_active"])
    inactive_count = sum(1 for m in mailboxes.values() if not m["is_active"])

    divider = "=" * 110
    print(f"\n{divider}")
    print("ROTATION RECOMMENDATIONS")
    print(divider)
    print(f"\n  {active_count} mailboxes active in campaigns · {inactive_count} inactive\n")

    if buckets["retire"]:
        print(f"\n  RETIRE ({len(buckets['retire'])})")
        print("  Remove from campaigns permanently. Do not re-enter rotation.")
        for m in buckets["retire"]:
            print(f"    {_signal_line(m)}")
            print(f"      Reason: {m['recommendation_reason']}")

    if buckets["move_to_warmup"]:
        print(f"\n  MOVE TO WARMUP ({len(buckets['move_to_warmup'])})")
        print("  Remove from campaigns. Keep SmartLead warmup running until reputation reaches 95%.")
        for m in buckets["move_to_warmup"]:
            print(f"    {_signal_line(m)}")
            print(f"      Reason: {m['recommendation_reason']}")

    if buckets["monitor"]:
        print(f"\n  MONITOR ({len(buckets['monitor'])})")
        print("  One signal below threshold. No action yet — review next check.")
        for m in buckets["monitor"]:
            print(f"    {_signal_line(m)}")
            print(f"      Reason: {m['recommendation_reason']}")

    print(f"\n  NO ACTION ({len(buckets['no_action'])}) — all signals healthy")

    print(f"\n{divider}")
    print(f"Supabase updated: {written} rows in '{SUPABASE_TABLE}'.\n")

    # 6. Send Slack notification
    print("Sending Slack notification...")
    slack_msg = _build_slack_message(mailboxes, prev_recs, now, fetch_failures)
    _send_slack(slack_msg)
    if not os.getenv("SLACK_MAILBOX_WEBHOOK_URL"):
        print("  (SLACK_MAILBOX_WEBHOOK_URL not set — skipped)")


if __name__ == "__main__":
    main()
