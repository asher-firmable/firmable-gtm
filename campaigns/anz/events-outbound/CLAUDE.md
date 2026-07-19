## Purpose
Outbound campaigns targeting exhibitors and attendees at ANZ trade events and expos.

## What goes in
- Event exhibitor/attendee lists (scraped or manually obtained)
- Event metadata (name, date, URL)

## What goes out
- `output/exhibitors.csv` — name + domain per event
- Downstream: feeds into enrichment → scoring → SmartLead upload via the main event-scraper pipeline

## Folder structure
Each event gets its own sub-folder named `{event-name}-{year}/`:
```
events-outbound/
├── sydney-build-expo-2026/
│   ├── scrape_exhibitors.py
│   └── output/
│       └── exhibitors.csv
├── fhweek-2026/
│   ├── scrape_exhibitors.py
│   └── output/
│       └── exhibitors.csv
└── cemat-2026/
    ├── scrape_exhibitors.py
    └── output/
        └── exhibitors.csv
```

## Scripts / tools
- `scrape_exhibitors.py` — per-event scraper; extracts name + website from the exhibitor list page
- `hubspot_check.py` — **shared** HubSpot enrichment script; run after scraping for any ANZ event
- Downstream enrichment/scoring/upload uses `projects/slack-bots/event-scraper/scripts/` pipeline

## HubSpot check — shared script

Run after scraping to enrich the exhibitor list with HubSpot data:

```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/anz/events-outbound/<event>/output/exhibitors.csv \
  --output campaigns/anz/events-outbound/<event>/output/hubspot_check.csv
```

**Input**: any CSV with at minimum a `website` or `domain` column (auto-detected).

**Output columns** (`hubspot_check.csv`):
| Column | Source |
|---|---|
| exists_in_hubspot | YES / NO |
| company_name | HubSpot `name` (falls back to input CSV) |
| company_website | HubSpot `domain` (falls back to input URL) |
| company_hubspot_url | Direct link to HubSpot record |
| company_owner | Resolved from `hubspot_owner_id` |
| sdr_au | `sdr__new_` |
| sdr_nz | `sdr_nz` |
| sdr_sea | `sdr_sea` |
| outreach_engagement_status | `outreach_engagement_status` |
| outreach_engagement_status_sea | `outreach_engagement_statussea` |
| sales_team_size_au | `au_sales_team_size` |
| sales_team_size_nz | `nz_sales_team_size` |
| sales_team_size_sea | `sea_sales_team_size` |
| last_contacted | `notes_last_contacted` (DD-MM-YYYY) |

**Domain matching logic**:
1. Strip protocol + path + `www.` → bare domain (e.g. `security.gallagher.com`)
2. `domain EQ bare_domain` — exact match preferred
3. If no match → `domain CONTAINS_TOKEN <SLD>` — first result wins

## Conventions
- One scraper script per event, named `scrape_exhibitors.py`
- Output always goes to `output/` inside the event folder (gitignored)
- Run from repo root: `PYTHONPATH=. python3 campaigns/anz/events-outbound/{event-folder}/scrape_exhibitors.py`
