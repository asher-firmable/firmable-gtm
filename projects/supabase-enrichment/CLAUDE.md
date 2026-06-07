# supabase-enrichment

## Purpose
Parallel company enrichment pipeline. Upload a CSV of companies (domain + description) into Supabase, then fan out two AI classification checks across all rows simultaneously using Trigger.dev — no row-by-row waiting.

## What goes in
- CSV with at minimum: `domain` or `company_domain` (Firmable exports) + optional `description` column
- Drop in `input/` and pass the path to `upload.py`
- The upload script automatically treats `company_domain` as an alias for `domain` — no manual renaming needed

## What goes out
- Results stored in Supabase `companies` master table
- Columns written: `company_type`, `company_type_reasoning`, `target_persona`, `persona_reasoning`, `firecrawl_used`, `status`
- Query directly in Supabase, or run `export.py` (future) for a CSV dump

## Scripts / tools

| File | Role |
|---|---|
| `scripts/upload.py` | CSV -> Supabase upsert. ON CONFLICT (domain) DO UPDATE so re-runs are safe. |
| `trigger/src/tasks/enrichBatch.ts` | Entry point. Selects all `status='pending'` rows, fans out via `batchTrigger`. |
| `trigger/src/tasks/classifyCompany.ts` | Agent 1. Classifies company type: SaaS/Software, MSP, IT Services, Other B2B. |
| `trigger/src/tasks/classifyPersona.ts` | Agent 2. Classifies target persona (who the company sells to). Chains from Agent 1. |

## How to run

### 1. Upload companies
```bash
PYTHONPATH=. python3 projects/supabase-enrichment/scripts/upload.py --file path/to/companies.csv
```

### 2. Trigger enrichment batch
In Trigger.dev dashboard: run the `enrich-batch` task manually.
Or via CLI: `npx trigger.dev@latest run enrich-batch`

### 3. Monitor
Check Trigger.dev dashboard for run status, retries, and errors.

## Conventions
- Supabase credentials: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`
- Anthropic: `ANTHROPIC_API_KEY` in `.env` (Haiku model, prompt caching enabled)
- Firecrawl: `FIRECRAWL_API_KEY` in `.env` — only triggered when description is thin or classification is low-confidence
- Classification prompts live in `knowledge/company-type-classification.md` and `knowledge/target-persona-classification.md` — edit there, not in TypeScript
- Master table cache: each agent checks if its output column is already filled before calling Claude — skip if so
- Never re-enrich a company that already has results; set `status='pending'` manually in Supabase to force a re-run
