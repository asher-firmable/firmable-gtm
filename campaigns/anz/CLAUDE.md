# ANZ Campaigns

## Purpose
Holds all Australia & New Zealand campaign data. Each campaign gets its own subfolder with `input/`, `data/`, and `CLAUDE.md`.

## Pipeline

`run_pipeline.py` runs the full pre-outreach pipeline for any ANZ campaign folder.

### Command
```bash
PYTHONPATH=. python3 campaigns/anz/run_pipeline.py \
    --campaign campaigns/anz/<campaign-folder>
```

Optional explicit input file (otherwise auto-detects latest CSV in `<campaign>/input/`):
```bash
PYTHONPATH=. python3 campaigns/anz/run_pipeline.py \
    --campaign campaigns/anz/<campaign-folder> \
    --input path/to/contacts.csv
```

### Steps
1. **Load input** — latest CSV from `<campaign>/input/` (or `--input`)
2. **HubSpot eligibility + Firmable enrichment** → `data/qualified/`
   - Excludes: active trials, paying customers, contacted < 30 days, active tasks/sequences
   - Adds: `au_sales_team_size`, `nz_sales_team_size`, `sea_sales_team_size`, `apac_sales_team_size`
3. **ANZ SMB size filter** → `data/validated/`
   - Keeps: `apac_sales_team_size` ≤ 4 or unknown (NaN)
   - Removes: `apac_sales_team_size` ≥ 5
4. **Normalize company names** — regex rules + domain check for messy names
5. **Persona enrichment** — ≤ 2 personas per company, `&` separator, lowercase except IT/HR/L&D/RTO etc.
6. **Save final** → `data/final/final_contacts_<timestamp>.csv`

### Input CSV requirements
Must have `email` (or `primary_work_email`) and `domain` (or `company_website`) columns.

## Campaigns
| Folder | Description |
|---|---|
| `ANZ_SMB_SaaS/Software_General_Outreach/` | ANZ SMB SaaS/Software general outreach (sales team ≤4) |
