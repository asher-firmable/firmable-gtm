# Supabase Enrichment Skill

## Purpose

Parallel company enrichment pipeline: classify company type and target persona for a batch of companies using Firmable API descriptions, Claude Haiku, and Firecrawl as fallback. Results stored in Supabase; processing runs entirely in Trigger.dev cloud (no terminal needs to stay open).

## When to use

When you have a CSV of companies (with domains and Firmable IDs) and need to classify:
- Company type: SaaS/Software providers | MSPs | IT services firms | IT Solutions providers | Other B2B companies
- Target persona: who the company sells to (e.g. "CFOs or operations managers")

---

## Standard Process

### Step 1 — Drop CSV into input folder

Place the CSV at `projects/supabase-enrichment/input/`.

Required columns (at minimum):
- `company_domain` or `domain` — company website domain
- `firmable_id` — full Firmable URL (e.g. `https://app.firmable.com/dashboard/company/f000036715750`) or raw ID

All other company-level columns (country, industry, technographics, etc.) are also uploaded to Supabase.

### Step 2 — Preview prompts on first 10 rows

```bash
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py --limit 10
```

This reads the CSV directly, calls Firmable API for each company description, then classifies using Claude. Show the full output in chat — include description, reasoning, and both classification results so the user can judge.

### Step 3 — Iterate on prompts

If results need adjustment:
1. Edit `COMPANY_TYPE_PROMPT` or `PERSONA_PROMPT` at the top of `preview_prompts.py`
2. Re-run the same command
3. Use `--offset` to review additional batches:

```bash
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py --limit 10 --offset 10   # rows 11-20
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/preview_prompts.py --limit 20 --offset 20   # rows 21-40
```

Continue until user confirms results are satisfactory across the full CSV.

### Step 4 — Sync approved prompts to Trigger.dev tasks

Once prompts are approved, copy the final `COMPANY_TYPE_PROMPT` and `PERSONA_PROMPT` from `preview_prompts.py` into the matching `const SYSTEM_PROMPT` constants in:
- `projects/supabase-enrichment/trigger/src/tasks/classifyCompany.ts`
- `projects/supabase-enrichment/trigger/src/tasks/classifyPersona.ts`

Both files have a comment: `# Note: prompts are kept in sync with preview_prompts.py — update both together`.

### Step 5 — Upload ALL rows to Supabase

```bash
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/upload.py \
  --file "projects/supabase-enrichment/input/<filename>.csv"
```

No `--limit` flag — upload the full CSV. Uses ON CONFLICT (domain) DO UPDATE so re-running is safe.

### Step 6 — Deploy to Trigger.dev cloud

```bash
cd projects/supabase-enrichment/trigger
npx trigger.dev@latest deploy --project-ref proj_phnowgcusbqmxpphrrof
```

This compiles the TypeScript tasks and pushes to the cloud. No local dev server needed — tasks run entirely on Trigger.dev's infrastructure.

### Step 7 — Trigger enrich-batch via REST API

```python
from dotenv import load_dotenv; load_dotenv('.env')
import os, requests
r = requests.post(
    'https://api.trigger.dev/api/v1/tasks/enrich-batch/trigger',
    headers={'Authorization': f'Bearer {os.getenv("TRIGGER_SECRET_KEY")}', 'Content-Type': 'application/json'},
    json={}
)
print(r.status_code, r.text)
```

Or run from the Claude Code terminal:
```bash
cd projects/supabase-enrichment && python3 -c "
from dotenv import load_dotenv; load_dotenv('../../.env')
import os, requests
r = requests.post('https://api.trigger.dev/api/v1/tasks/enrich-batch/trigger',
    headers={'Authorization': f'Bearer {os.getenv(\"TRIGGER_SECRET_KEY\")}', 'Content-Type': 'application/json'},
    json={})
print(r.status_code, r.text)
"
```

### Step 8 — Monitor via Supabase

Poll the `companies` table. All rows should move from `pending` → `processing` → `done`. Each row takes ~10s; with concurrencyLimit: 3, a 50-row batch completes in ~3-6 minutes.

```python
# Quick status check
from supabase import create_client
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
res = sb.table('companies').select('status').execute()
counts = {}
for r in res.data:
    counts[r['status']] = counts.get(r['status'], 0) + 1
print(counts)
```

---

## Key files

| File | Role |
|---|---|
| `projects/supabase-enrichment/scripts/preview_prompts.py` | Prompt iteration tool — reads CSV directly, no Supabase needed |
| `projects/supabase-enrichment/scripts/upload.py` | Uploads all company columns to Supabase |
| `projects/supabase-enrichment/trigger/src/tasks/enrichBatch.ts` | Fan-out entry point — selects pending rows, batch-triggers classify-company |
| `projects/supabase-enrichment/trigger/src/tasks/classifyCompany.ts` | Agent 1: company type. Chains to classifyPersona when done. |
| `projects/supabase-enrichment/trigger/src/tasks/classifyPersona.ts` | Agent 2: target persona. Sets status=done. |
| `projects/supabase-enrichment/trigger/src/lib/claude.ts` | callClaude wrapper — Haiku, prompt caching, 429 retry with exponential backoff |
| `projects/supabase-enrichment/trigger/src/lib/supabase.ts` | Supabase client (direct export, WebSocket polyfilled via globalThis) |
| `projects/supabase-enrichment/trigger/src/lib/firmable.ts` | Fetches description from Firmable API by company ID |
| `projects/supabase-enrichment/trigger/src/lib/firecrawl.ts` | Scrapes website when confidence < 75% and no prior website_summary |

## Company type categories (as of June 2026)

Exact label names matter — use these verbatim:
1. `SaaS/Software providers` — sells software on subscription/license
2. `MSPs` — manages IT/cloud infrastructure for clients on ongoing contracts
3. `IT services firms` — project-based IT consulting, staffing, or implementation
4. `IT Solutions providers` — packaged hardware+software systems (AV, networking, control rooms, surveillance)
5. `Other B2B companies` — everything else, including pure IT staffing/recruiting, hardware manufacturing, robotics

Key distinctions:
- Pure IT staffing/recruiting (no consulting, no implementation) → Other B2B companies, not IT services firms
- Hardware+software deployable systems → IT Solutions providers, not SaaS or Other B2B

## Troubleshooting

- **Rows stuck in `processing`**: tasks failed mid-run with no error handler. Reset via Supabase SQL:
  ```sql
  UPDATE companies SET status='pending', error_msg=NULL, description=NULL, company_type=NULL, target_persona=NULL WHERE status='processing';
  ```
  Then re-trigger enrich-batch.

- **Rows stuck in `pending` after trigger**: check the Trigger.dev dashboard for the enrich-batch run. Common causes:
  - `payload` passed as `undefined` — fixed in current code (payload is now optional with `??` defaults)
  - Supabase client init failure — check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in Trigger.dev cloud env vars

- **429 rate limit from Anthropic**: `callClaude` already retries up to 4x with exponential backoff (2s → 4s → 8s). If still failing, reduce `concurrencyLimit` from 3 to 2 in both classify task files.

- **Tasks show `error` status**: inspect via Supabase:
  ```python
  res = sb.table('companies').select('domain, error_msg').eq('status', 'error').execute()
  for r in res.data: print(r['domain'], r['error_msg'])
  ```
  Reset and re-trigger: `UPDATE companies SET status='pending', error_msg=NULL WHERE status='error';`

- **Stale error_msg on done rows**: clear with:
  ```python
  sb.table('companies').update({'error_msg': None}).eq('status', 'done').not_.is_('error_msg', 'null').execute()
  ```

## Env vars required

In root `.env` and in Trigger.dev cloud dashboard (Production environment):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`
- `FIRMABLE_API_KEY`
- `FIRECRAWL_API_KEY`
- `TRIGGER_SECRET_KEY` — used to trigger runs via REST API from Python scripts

Trigger.dev project ref: `proj_phnowgcusbqmxpphrrof`
