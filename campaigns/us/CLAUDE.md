# US Campaigns

## Purpose
Outbound campaigns targeting US-based companies.

## Sub-folders

| Folder | Purpose |
|---|---|
| `creative-ideas/` | Wide outbound: Clay AI enrichment generates 2-3 personalised Firmable ideas per US SMB company |
| `msp-it-services/` | Campaigns targeting US MSPs and IT services firms |
| `zoominfo-displacement/` | Two-email sequence targeting ZoomInfo users (demo → trial) |

## Conventions
- Run scripts from repo root with `PYTHONPATH=.`
- Input CSVs go in `input/` (gitignored)
- Output CSVs go in `output/` (gitignored)
- Enrichment cache lives in `master_companies` Supabase table — always check this before running full enrichment
