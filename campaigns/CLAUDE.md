# Campaigns — Data Store

Campaign data organised by region. This folder contains data only — all scripts live in `projects/`.

## Regions

| Folder | Market |
|---|---|
| `anz/` | Australia & New Zealand |
| `us/` | United States |
| `sea/` | South-East Asia |

## Campaign Folder Convention

Each campaign gets its own subfolder inside the relevant region:

```
campaigns/
└── anz/
    └── 2026-q2-fintech-sydney/
        ├── brief.md              ← Campaign goal, ICP, target accounts, sender details
        └── data/
            ├── raw/              ← Original input files from Clay or manual upload
            ├── qualified/        ← After ICP scoring (icp_score, tier added)
            ├── validated/        ← After contact validation (DNC applied)
            └── final/            ← Ready for SmartLead upload
```

## Rules

- **Data only** — no scripts live here; run scripts from `projects/outbound/` or `projects/event-scraper/`
- **brief.md required** — every campaign folder must have a brief describing the goal, ICP, and sender
- **gitignore** — all `data/` subfolders are gitignored; only `brief.md` and `.gitkeep` files are committed
- **Naming** — use `YYYY-[q or month]-[descriptor]-[region]` format (e.g. `2026-q2-fintech-sydney`)

## Creating a New Campaign

Run `/new-campaign` and follow the wizard. It will create the folder structure and populate `brief.md`.

---

## Pre-Campaign Pipeline (all regions)

Before any contact list is uploaded to SmartLead, run it through `scripts/hubspot_eligibility.py`. This is mandatory for every campaign regardless of region or signal type.

```bash
PYTHONPATH=. python3 scripts/hubspot_eligibility.py \
  --input campaigns/<region>/<campaign>/data/raw/contacts.csv \
  --output-dir campaigns/<region>/<campaign>/data/eligible/
```

Input CSV must have `email` and `domain` columns.

### Stage 1 — Company-level HubSpot check (domain)
- Looks up each unique domain in HubSpot
- **Excludes** contacts at companies with `trial_status` = `Active Trial` or `Paying Customer from Trial`

### Stage 2 — Contact-level HubSpot check (email)
- Contact **not in HubSpot** → PASS (new prospect, carry on)
- Contact **in HubSpot**:
  - `hs_last_contacted` within last 30 days → FAIL
  - Active scheduled tasks (`NOT_STARTED`) on contact or company → FAIL
  - Otherwise → PASS

### Stage 3 — Firmable sales team enrichment (eligible contacts only)
- Looks up each eligible contact's company in Firmable by domain
- Fetches regional sales headcount: AU, NZ, SEA
- Adds `au_sales_team_size`, `nz_sales_team_size`, `sea_sales_team_size`, `apac_sales_team_size`
- **APAC = AU + NZ + SEA**

### Outputs
Two files written to `--output-dir`:
- `eligible_contacts_<timestamp>.csv` — passing contacts only
- `eligible_contacts_with_reasons_<timestamp>.csv` — all contacts with pass/fail reasons

### ANZ campaigns — extra filter (apply manually after pipeline)
After running the pipeline, filter out contacts where `apac_sales_team_size >= 5`.
This is not applied automatically — review the eligible CSV and apply before uploading to SmartLead.

### data/raw/ source
Input CSVs come from **Firmable exports** or manual uploads. Not from Clay directly.
