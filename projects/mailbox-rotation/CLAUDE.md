# mailbox-rotation

## Purpose
Mailbox rotation health check. Reads signal data from SmartLead for every mailbox, applies rotation recommendation logic, writes state to Supabase, and prints a prioritised action report. Read-only from SmartLead — no campaign changes are made.

## What goes in
- SmartLead email accounts (via API): warmup reputation, campaign assignments, all-time stats, 14-day replies
- Supabase `mailbox_rotation` table (existing rows, for pool transition tracking)

## What goes out
- Upserted rows in Supabase `mailbox_rotation` table
- Terminal action report grouped by recommendation

## Scripts / tools

| File | Role |
|---|---|
| `scripts/rotation_check.py` | Main script: fetch SmartLead data, classify each mailbox, upsert Supabase, print report, send Slack notification |
| `supabase/001_create_mailbox_rotation.sql` | Run once in Supabase SQL editor to create the table |
| `supabase/002_add_rotation_due.sql` | Run once to add `rotation_due` and `days_in_pool` columns |

## How to run

### First time: create Supabase table
1. Run `supabase/001_create_mailbox_rotation.sql` in the Supabase SQL editor
2. Run `supabase/002_add_rotation_due.sql` in the Supabase SQL editor

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

| Recommendation | Condition |
|---|---|
| `retire` | Both reply signals (AT and 14d) have data and both are below 1% |
| `move_to_warmup` | warmup reputation < 95% (and not retiring) |
| `monitor` | At least one reply signal passing, but not all 3 core signals healthy |
| `no_action` | All signals healthy |

### Core signals
- AT reply rate ≥ 1%
- 14-day reply rate ≥ 1%
- Bounce rate < 3%

### Warmup signal (independent)
- Warmup rep ≥ 95%: fine
- Warmup rep < 95%: remove from campaigns, stay in warmup pool until it recovers

### Rotation due (independent of health)
- `rotation_due = true` when `pool = 'sending'` and `days_in_pool >= 30`
- Shown as a separate section — healthy mailboxes can still be rotation-due

## Supabase table: `mailbox_rotation`

Key columns:

| Column | Description |
|---|---|
| `email` | Primary key |
| `region` | US / SEA / ANZ (from SmartLead tags) |
| `pool` | `sending` (in ≥1 campaign) or `not_sending` |
| `pool_since` | When the mailbox entered the current pool |
| `days_in_pool` | Days in the current pool (computed each run) |
| `rotation_due` | True when sending pool and active 30+ days |
| `recommendation` | `no_action` / `monitor` / `move_to_warmup` / `retire` |
| `recommendation_reason` | Human-readable explanation with actual signal values and thresholds |
| `last_checked_at` | Last time the script ran for this mailbox |

## Conventions
- `pool_since` is preserved across runs unless the pool changes — source of truth for "how long in this state"
- The script does not execute any SmartLead changes — recommendations only. Act manually in the SmartLead UI.
- Env vars required: `SMARTLEAD_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `SLACK_MAILBOX_WEBHOOK_URL` — Slack Incoming Webhook; if not set, Slack step is silently skipped
