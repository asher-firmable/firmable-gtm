# US Founding 100 — MSP/IT Services Segment

## Purpose
Classify ~8,000 US MSP and IT services companies. Uses `master_companies` as a cache.

## What goes in
CSV with `domain` (or `company_domain`) + optional Firmable columns. Drop in `input/`.

## What goes out
`us_founding_100` Supabase table with `company_type`, `target_persona`, `status` populated.

## How to run

### 1. Upload + cache check
```bash
PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/upload.py \
  --file "campaigns/us/founding-100/msp-it-services/input/<file>.csv"
```

### 2. Trigger enrichment (only if pending rows exist)
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

### 3. Sync results back
```bash
PYTHONPATH=. python3 campaigns/us/founding-100/msp-it-services/scripts/sync.py
```
Re-run until "Pending remaining: 0".

## Supabase table
`us_founding_100` — run `projects/supabase-enrichment/supabase/migrations/002_create_us_founding_100.sql` in Supabase SQL editor to create.
