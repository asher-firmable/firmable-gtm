# Quick Sales Team Size Check

## Purpose
Enrich a company list with regional sales team sizes (ANZ, SEA, US) using the Firmable OS Search API.

## What goes in
Drop a CSV or Excel (`.xlsx`) file into `input/`. The file must have at least one of:
- `domain` / `website` / `fqdn` — company domain (e.g. `firmable.com`)
- `firmable_id` / `id` — Firmable company ID (e.g. `f000000117274`)

## What goes out
A CSV written to `output/<original_filename>_enriched.csv` with four new columns appended:

| Column | Type | Description |
|---|---|---|
| `firmable_id` | string | Firmable company ID (resolved from domain if needed) |
| `anz_sales_team_size` | int | AU + NZ sales headcount |
| `sea_sales_team_size` | int | SEA sales headcount (PH, MY, SG, ID, HK, JP) |
| `apac_sales_team_size` | int | ANZ + SEA combined |
| `us_sales_team_size` | int | US sales headcount |

Values are `0` when a company is found but has no sales people in that region. Values are blank (`None`) only when the company lookup fails entirely.

## Scripts / tools
- `scripts/enrich_sales_team_size.py` — main enrichment script
  - Uses `FirmableClient.lookup_company()` to resolve domains → Firmable IDs
  - Uses `FirmableClient.get_sales_team_size()` for regional headcount
  - Parallel execution (5 workers)

## How to run
```bash
# Auto-picks the latest file in input/
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py

# Or specify a file explicitly
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py --input path/to/companies.csv
```

## Conventions
- Requires `FIRMABLE_API_KEY` and `FIRMABLE_OS_API_KEY` in `.env`
- `output/` is gitignored — never commit enriched files
- If re-running on an already-enriched file, existing `firmable_id` / size columns are overwritten
