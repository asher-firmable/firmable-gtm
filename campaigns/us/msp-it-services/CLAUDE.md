# US MSP & IT Services Campaigns

## Purpose
Campaigns targeting US-based MSPs (managed service providers) and IT services firms.

## Target company types
- `MSPs` — manages IT/cloud infrastructure for clients on ongoing contracts
- `IT services firms` — project-based IT consulting, implementation, or staffing

## Sub-folders

| Folder | Purpose |
|---|---|
| `founding-100/` | US Founding 100 — ~8,000 company enrichment and classification run |

## Conventions
- All enrichment uses the `master_companies` Supabase table as a cache
- Campaign-specific results go into a separate campaign table (e.g. `us_founding_100`)
- Enrichment pipeline: upload.py (cache check) → Trigger.dev enrich-batch → sync.py
