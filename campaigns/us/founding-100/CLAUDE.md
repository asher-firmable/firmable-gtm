# US Founding 100

## Purpose
Enrichment and classification project for ~8,000 US companies. Segments by company type — each subfolder is a vertical (MSP/IT services, SaaS, Other B2B, etc.). Uses `master_companies` as a shared cache across all segments.

## Subfolders

| Folder | Segment | Supabase table |
|---|---|---|
| `msp-it-services/` | MSPs and IT services firms | `us_founding_100` |
| `saas/` | SaaS companies | — |

## How the pipeline works

1. Drop CSV into the segment's `input/` folder
2. Run `scripts/upload.py` — checks `master_companies` cache, pre-fills known domains, queues unknowns
3. Trigger `enrich-batch` in Trigger.dev — enriches unknown domains in `master_companies`
4. Run `scripts/sync.py` — copies enrichment back from `master_companies` to the segment table

Each segment has its own Supabase table and its own `input/` + `scripts/`. The Trigger.dev tasks are shared.
