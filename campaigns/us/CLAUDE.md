# US Campaigns

## Purpose
Outbound campaigns targeting US-based companies.

## Sub-folders

| Folder | Purpose |
|---|---|
| `msp-it-services/` | Campaigns targeting US MSPs and IT services firms |

## Conventions
- Run scripts from repo root with `PYTHONPATH=.`
- Input CSVs go in `input/` (gitignored)
- Output CSVs go in `output/` (gitignored)
- Enrichment cache lives in `master_companies` Supabase table — always check this before running full enrichment
