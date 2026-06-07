# US Founding 100 — MSP/IT Services

## Purpose
Classify ~8,000 US MSP and IT services companies into company type + target persona. Uses `master_companies` as a cache: domains already enriched are pre-filled instantly; new domains go through Trigger.dev cloud enrichment.

## What goes in
- CSV with `domain` (or `company_domain`) + optional Firmable columns
- Drop in `input/` before running

## What goes out
- `us_founding_100` Supabase table: all input columns + `company_type`, `target_persona`, `status`
- Export via SQL: `SELECT * FROM us_founding_100 WHERE status = 'done'`

## How to run

### 1. Preview prompts (optional — prompts are already tuned)
```bash
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py --limit 10
```

### 2. Upload CSV + cache check
```bash
PYTHONPATH=. python3 campaigns/us/msp-it-services/founding-100/scripts/upload.py \
  --file campaigns/us/msp-it-services/founding-100/input/<file>.csv
```
Prints how many rows were pre-filled from cache vs pending enrichment.

### 3. Trigger Trigger.dev enrichment (only if there are pending rows)
```bash
PYTHONPATH=. python3 -c "
from dotenv import load_dotenv; load_dotenv('.env')
import os, requests
r = requests.post('https://api.trigger.dev/api/v1/tasks/enrich-batch/trigger',
    headers={'Authorization': f'Bearer {os.getenv(\"TRIGGER_SECRET_KEY\")}', 'Content-Type': 'application/json'},
    json={})
print(r.status_code, r.text)
"
```
Monitor in Trigger.dev dashboard. For ~8,000 new domains: ~7–8 hours at concurrencyLimit 3.

### 4. Sync results back
```bash
PYTHONPATH=. python3 campaigns/us/msp-it-services/founding-100/scripts/sync.py
```
Re-run periodically until "Pending remaining: 0".

## Scripts

| Script | Role |
|---|---|
| `scripts/upload.py` | Load CSV, check master_companies cache, upsert to us_founding_100 |
| `scripts/sync.py` | Copy enrichment from master_companies → us_founding_100 after Trigger.dev completes |

## Supabase table
`us_founding_100` — created via `projects/supabase-enrichment/supabase/migrations/002_create_us_founding_100.sql`

Run in Supabase SQL editor to create:
```sql
-- Run the contents of migrations/002_create_us_founding_100.sql
```

## Timing (8,000 new domains)
- ~7–8 hours at concurrencyLimit 3 (safe overnight run)
- Trigger.dev paid plan required (~160,000 task-seconds; free tier is 100k/month)
- To speed up: raise concurrencyLimit in classifyCompany.ts + classifyPersona.ts (requires higher Anthropic API tier)
