# Account Level Enrichment — Sub-Agent

## Purpose
Enrich a Firmable-exported accounts CSV with regional sales headcount and an AI-generated company summary note, then sync the enriched data to HubSpot.

## What goes in
- A CSV from Firmable (or `data/input/`) that includes a **Firmable ID** column.
- The CSV can contain any other columns — they are all preserved in output.

## What goes out
- An enriched CSV written to `output/enriched_<timestamp>.csv` with one new column added:

| Column | Description |
|--------|-------------|
| `enrichment_note` | Multi-line note with extraction date, regional headcount, target persona, problem, and solution |

Individual country-level columns (`AU Sales`, `NZ Emp`, `SG Sales`, `MY Sales`, `ID Sales`, `PH Sales`, `HK Sales`, `JP Sales`) are stripped from the output — only the APAC and regional totals are kept.

### Enrichment note format
```
Data extracted: 25 March 2026

APAC Sales Team Size: 71
ANZ Sales Team Size: 51
SEA Sales Team Size: 20

Target persona: VP of Engineering, Head of Operations, Chief Digital Officer

Problem they solve: [1–2 sentences]

How they solve it: [1–2 sentences]
```

## Scripts
- `scripts/enrich_accounts.py` — pulls Firmable headcount + AI note per account; writes enriched CSV
- `scripts/hubspot_check.py` — read-only check: which companies exist in HubSpot, their lifecycle stage and trial status
- `scripts/hubspot_sync.py` — pushes ICP Match (SEA) and Company owner (SEA) to HubSpot per the sync rules below

## Usage
```bash
# Step 1 — enrich
PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/enrich_accounts.py \
  --input "data/input/Darcy Accounts.csv"

# Step 2 — check (read-only)
PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/hubspot_check.py \
  --input "projects/account-level-enrichment-sea/output/enriched_<timestamp>.csv"

# Step 3 — sync (writes to HubSpot — confirm before running)
PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/hubspot_sync.py \
  --input "projects/account-level-enrichment-sea/output/enriched_<timestamp>.csv"
```

## HubSpot sync rules
- **Customers** (`lifecyclestage = customer`) → skip entirely, no changes
- **Active Trial accounts** → update `icp_match_sea` always; set `company_owner_sea` only if currently empty
- **All other accounts** → update `icp_match_sea` + set `company_owner_sea`
- **Never** touch `hubspot_owner_id` (AE/company owner field)

ICP Match (SEA) tiers based on SEA Sales Team Size in the enrichment note:
| SEA team size | ICP Match (SEA) |
|---|---|
| 0–4 | SMB |
| 5–9 | Medium |
| 10–24 | High |
| 25+ | Very High |

## Conventions
- Import API clients from `scripts/` only — never duplicate API logic here.
- Output files are gitignored; never commit enriched CSVs.
- Requires `FIRMABLE_API_KEY` and `FIRMABLE_OS_API_KEY` in `.env` (headcount uses the OS Search API).
- Requires `ANTHROPIC_API_KEY` in `.env` for enrichment note generation.
- Requires `HUBSPOT_ACCESS_TOKEN` in `.env` for HubSpot check and sync.
- Rows with no Firmable ID are preserved in output with a blank enrichment note.
- Always run `hubspot_check.py` before `hubspot_sync.py` to review what will be affected.
