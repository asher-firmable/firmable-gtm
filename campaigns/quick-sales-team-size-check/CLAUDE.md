# Quick Sales Team Size Check

## Purpose
Enrich a company list with regional sales team sizes (ANZ, SEA, US) using the Firmable OS Search API.

## What goes in
Drop a CSV or Excel (`.xlsx`) file into `input/`. The file must have at least one of:
- `firmable_id` / `id` — Firmable company ID (highest priority)
- `firmable_website` / `firmable_company_url` — Firmable app URL (ID extracted from path)
- `domain` / `website` / `fqdn` — company domain (e.g. `firmable.com`)
- `company_name` / `name` — company name (cannot be resolved without domain/ID)

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
- `scripts/enrich_sales_team_size.py` — enriches with ANZ, SEA, US, APAC (combined ANZ view)
- `scripts/enrich_us_au_nz_sales.py` — enriches with US, AU, NZ as separate columns
  - Accepts: `firmable_id`, `firmable_website`, `domain`, `company_name` (uses best available per row)
  - Parallel execution (5 workers); prints resolved/unresolved summary

Both scripts use `FirmableClient.get_sales_team_size()` against the OS Search API.

## How to run

### ANZ/SEA/US combined view
```bash
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_sales_team_size.py --input path/to/companies.csv
```

### US / AU / NZ split (separate columns)
```bash
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_us_au_nz_sales.py
PYTHONPATH=. python campaigns/quick-sales-team-size-check/scripts/enrich_us_au_nz_sales.py --input path/to/companies.csv
```

## Conventions
- Requires `FIRMABLE_API_KEY` and `FIRMABLE_OS_API_KEY` in `.env`
- `output/` is gitignored — never commit enriched files
- If re-running on an already-enriched file, existing `firmable_id` / size columns are overwritten
