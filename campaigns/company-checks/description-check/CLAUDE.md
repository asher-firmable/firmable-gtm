# Description Check — Sub-Agent

## Purpose
Given a company list with descriptions, evaluate each description against a user-provided yes/no question using Claude Code's in-context reasoning. No external API calls — Claude Code itself does the analysis.

Useful for filtering lists by company type, industry, or any binary characteristic that can be inferred from a description (e.g. "Is this a recruitment agency?", "Does this company sell to enterprise?").

## What goes in
- Drop a CSV or Excel file into `input/` before running `/description-check`
- Required: at least one description column — accepts `description`, `company_description`, `about`, `overview`, `summary` (case-insensitive)
- Optional but helpful: company name (`company_name`, `name`, `company`) and domain (`website`, `domain`, `company_website`, `company_domain`, `url`)
- Rows with no description are included in output with blank result and reason fields

## What goes out
- `output/<your-filename>.csv` — all processed rows with columns: `row_num`, `company_name`, `domain`, `description`, `result`, `reason`
- Results are written per batch; subsequent batches append to the same file
- `output/` is gitignored — never commit result files

## Scripts
| Script | Purpose |
|---|---|
| `scripts/description_check.py` | Extract mode: reads input file, prints JSON batch. Write mode: appends results to output CSV. |

## How to run
Use the `/description-check` slash command for the full interactive workflow (recommended).

Or run the script directly:
```bash
# Extract a batch for manual evaluation
PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py \
  --start 0 --count 10

# Write results (first batch)
PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py \
  --mode write \
  --output staffing_check.csv \
  --results-json '[{"row_num":1,"company_name":"Acme","domain":"acme.com","description":"...","result":"Yes","reason":"..."}]'

# Append subsequent batches
PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py \
  --mode write --append \
  --output staffing_check.csv \
  --results-json '[...]'
```

## Conventions
- Run from repo root with `PYTHONPATH=.`
- Column detection is case-insensitive — no renaming needed before running
- `--count 9999` processes all remaining rows from `--start` onwards (pandas truncates safely)
- `input/*.csv` is gitignored; `input/*.xlsx` is not covered by gitignore — do not commit Excel files manually
- `output/` is gitignored — never commit result files
- No API keys required — no external AI calls
