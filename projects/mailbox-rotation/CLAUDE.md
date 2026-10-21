# mailbox-rotation

## Purpose
Mailbox rotation health check. Reads signal data from SmartLead for every mailbox, applies rotation recommendation logic, writes state to Supabase, and prints a prioritised action report. Read-only from SmartLead — no campaign changes are made.

## What goes in
- SmartLead email accounts (via API): warmup reputation, campaign assignments, all-time stats, 14-day replies
- Supabase `mailbox_rotation` table (existing rows, for sticky-retire tracking)

## What goes out
- Upserted rows in Supabase `mailbox_rotation` table
- Terminal action report grouped by recommendation

## Scripts / tools

| File | Role |
|---|---|
| `scripts/rotation_check.py` | Main script: fetch SmartLead data, classify each mailbox, upsert Supabase, print report, send Slack notification |
| `scripts/tag_pools.py` | Rebalances Active/Standby/Retire SmartLead tags from Supabase recommendations (`--apply` to write) |
| `scripts/retire_mailboxes.py` | Permanently retires specific mailboxes: removes them from ACTIVE/PAUSED SmartLead campaigns and swaps Active tag → Retire tag (`--apply` to write, `--emails` comma-separated) |
| `supabase/001_create_mailbox_rotation.sql` | Run once in Supabase SQL editor to create the table |
| `supabase/002_add_rotation_due.sql` | (superseded by 003) originally added `rotation_due` and `days_in_pool` columns |
| `supabase/003_drop_pool_add_total_sent.sql` | Drops `pool`/`pool_since`/`rotation_due`/`days_in_pool`, adds `total_sent` |

## How to run

### First time: create Supabase table
1. Run `supabase/001_create_mailbox_rotation.sql` in the Supabase SQL editor
2. Run `supabase/002_add_rotation_due.sql` in the Supabase SQL editor
3. Run `supabase/003_drop_pool_add_total_sent.sql` in the Supabase SQL editor

### Run health check
```bash
PYTHONPATH=. python3 projects/mailbox-rotation/scripts/rotation_check.py
```

### Automated daily run (GitHub Actions)
The workflow at `.github/workflows/daily-rotation-check.yml` runs every day at 9am AEST.
Requires these secrets set in GitHub repo settings:
- `SMARTLEAD_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SLACK_MAILBOX_WEBHOOK_URL` (Slack Incoming Webhook URL — create at api.slack.com/apps, free)

## Recommendation logic

Only evaluated once a mailbox has sent more than `MIN_SENDS_FOR_CLASSIFICATION` (100) emails all-time — below that there isn't enough data for reply/bounce rates to mean anything, and it falls into `monitor` by default.

| Recommendation | Condition |
|---|---|
| `retire` | Both reply signals (AT and 14d) have data and both are below 1% |
| `move_to_warmup` | warmup reputation < 95% (and not retiring) |
| `monitor` | At least one reply signal passing, but not all 3 core signals healthy (or under 100 sends) |
| `no_action` | All signals healthy |

### Core signals
- AT reply rate ≥ 1%
- 14-day reply rate ≥ 1%
- Bounce rate < 3%

### Warmup signal (independent)
- Warmup rep ≥ 95%: fine
- Warmup rep < 95%: remove from campaigns, stay in warmup pool until it recovers

### Retire is permanent (sticky)
- Once a mailbox's `recommendation` is `retire` in Supabase, it stays `retire` on every subsequent run — the daily classifier never reclassifies it back to `monitor`/`move_to_warmup`/`no_action`, even if new signals would otherwise look better (e.g. it goes inactive and its 14-day reply rate becomes unavailable, which would normally fall through to `monitor`)
- `recommendation_reason` is preserved from the original retire decision, not overwritten
- Reactivating a retired mailbox is a manual decision (edit the Supabase row directly) — the script will not do it automatically

## Supabase table: `mailbox_rotation`

Key columns:

| Column | Description |
|---|---|
| `email` | Primary key |
| `region` | US / SEA / ANZ (from SmartLead tags) |
| `vendor` | `InboxKit` / `ScaledMail` / `sending.ac` / empty (from SmartLead tags) |
| `is_active` | True if currently assigned to ≥1 ACTIVE SmartLead campaign right now |
| `total_sent` | All-time emails sent from this mailbox (apportioned across its campaigns) |
| `warmup_rep` | SmartLead warmup reputation (0-100) |
| `at_reply_rate` | All-time reply rate (%) |
| `reply_14d_rate` | 14-day reply rate (%) |
| `bounce_rate` | All-time bounce rate (%) |
| `recommendation` | `no_action` / `monitor` / `move_to_warmup` / `retire` |
| `recommendation_reason` | Human-readable explanation with actual signal values and thresholds |
| `last_checked_at` | Last time the script ran for this mailbox |

As of `003_drop_pool_add_total_sent.sql`, `pool`/`pool_since`/`rotation_due`/`days_in_pool` no longer exist — `is_active` is a live snapshot only (no "how long" tracking), and `total_sent` is the plain send count that replaced them.

## Conventions
- The script does not execute any SmartLead changes — recommendations only. Act manually in the SmartLead UI.
- Env vars required: `SMARTLEAD_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `SLACK_MAILBOX_WEBHOOK_URL` — Slack Incoming Webhook; if not set, Slack step is silently skipped
