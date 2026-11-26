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
├── cemat-2026/
│   ├── scrape_exhibitors.py
│   └── output/
│       └── exhibitors.csv
└── melbourne-build-expo-2026/
    ├── scrape_exhibitors.py     ← ExpoFP data.js, same platform as Sydney Build
    └── output/
        └── exhibitors.csv
```

## Scripts / tools
- `scrape_exhibitors.py` — per-event scraper; extracts name + website from the exhibitor list page
- `hubspot_check.py` — **shared** HubSpot + Firmable enrichment script; single pass, computes `status`/`reason`; run after scraping for any ANZ event
- `build_workbook.py` — **shared** — builds the combined Excel workbook (all exhibitors, colour-coded by status, hyperlinked) from `hubspot_check.csv`
- Downstream enrichment/scoring/upload uses `projects/slack-bots/event-scraper/scripts/` pipeline

## HubSpot check — shared script

Run after scraping to enrich the exhibitor list with HubSpot data:

```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/anz/events-outbound/<event>/output/exhibitors.csv \
  --output campaigns/anz/events-outbound/<event>/output/hubspot_check.csv
```

**Input**: any CSV with at minimum a `website` or `domain` column (auto-detected). `name`, `tier`, and `stand`/`booth` columns are also auto-detected and passed through if present.

This is a **single-pass** script — every field below is fetched or computed in one run, including `status`/`reason`. There is no separate follow-up enrichment step; if a new field is needed, extend this script rather than bolting on a per-event patch.

**Output columns** (`hubspot_check.csv`):
| Column | Source |
|---|---|
| exists_in_hubspot | YES / NO |
| found_in_firmable | YES / NO |
| firmable_id | Firmable company ID (blank if not found) — build a link with `https://app.firmable.com/dashboard/company/{id}` |
| company_name | HubSpot `name` (falls back to input CSV) |
| company_website | HubSpot `domain` (falls back to input URL) |
| tier | Passed through from the input CSV's `tier`/`category` column, if present |
| stand | Passed through from the input CSV's `stand`/`booth`/`booth_number` column, if present |
| status | Computed: `Eligible` or `Ineligible` — see priority order below |
| reason | Computed: which rule the row failed (blank if Eligible) |
| company_hubspot_url | Direct link to HubSpot record |
| company_owner | Resolved from `hubspot_owner_id` |
| company_owner_anz | Resolved from `company_owner_nz` |
| company_owner_sea | Resolved from `company_owner_sea` |
| sdr_au | `sdr__new_` |
| sdr_nz | `sdr_nz` |
| sdr_sea | `sdr_sea` |
| outreach_engagement_status | `outreach_engagement_status` |
| outreach_engagement_status_sea | `outreach_engagement_statussea` |
| customer_status | `customer_status` |
| icp_match_anz | `icp_match_anz` (ICP Match (ANZ)), mapped to label: SMB / Mid-market / Enterprise / Partner |
| icp_match_sea | `icp_match_sea` (ICP Match (SEA)), mapped to label: SMB / Medium / High / Very High / Partner |
| open_deal | YES / NO — any deal on the company not in a closed stage |
| deal_owner | Owner(s) of any open deal, comma-joined if more than one (blank if no open deal) |
| sales_team_au / sales_team_nz / sales_team_sea / sales_team_us | Real-time from Firmable's `get_sales_team_size` (one call returns all four) |
| sales_team_anz | Computed: `sales_team_au + sales_team_nz` (blank only if both are blank) |
| hq_country | Firmable `hq_country`, from the same `lookup_company` response used for `firmable_id` — no extra API call |
| last_contacted | `notes_last_contacted` (DD Mon YYYY) |

**Status/Reason priority order** (first match wins, else `Eligible`):
1. Already customer or trialing (`customer_status` is `Paying Customer` or `Trialing Customer`)
2. Open deal
3. Next step scheduled — only checked when an SDR (AU/NZ/SEA) is assigned and the row is otherwise clear of 1–2 (an open/`NOT_STARTED` task on the company record)
4. No Firmable match

**Contacted in the last 30 days is NOT an exclusion** (changed 2026-11-12). A company that passes 1–4 but was contacted in the last 30 days is `Eligible`, and `reason` carries the note `Contacted in last 30 days (last contact DD Mon YYYY)`. This applies to the event exhibitor check only; the SmartLead pre-campaign gate (`scripts/hubspot_eligibility.py`, `/smartlead-pre-campaign-check`) still treats recent contact as ineligible.

**Domain matching logic**:
1. Strip protocol + path + `www.` → bare domain (e.g. `security.gallagher.com`)
2. `domain EQ bare_domain` — exact match preferred
3. If no match → `domain CONTAINS_TOKEN <SLD>` — first result wins

## Conventions
- One scraper script per event, named `scrape_exhibitors.py`
- Output always goes to `output/` inside the event folder (gitignored)
- Run from repo root: `PYTHONPATH=. python3 campaigns/anz/events-outbound/{event-folder}/scrape_exhibitors.py`
