## Purpose
Scrape Salesforce World Tour Melbourne 2026 sponsor list into a CSV for ANZ outbound outreach.

## What goes in
- Sponsor catalog page: https://reg.salesforce.com/flow/plus/wtmelbourne26/sponsors/page/sponsorcatalog (~18 sponsors)

## What goes out
- `output/exhibitors.csv` — `company_name`, `website` columns; one row per sponsor
- `output/hubspot_check.csv` — enriched with HubSpot + Firmable data

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright scraper — loads SPA, navigates each "View Booth" page, extracts company name + website |

## Run commands
```bash
# Step 1: scrape
PYTHONPATH=. python3 campaigns/anz/events-outbound/salesforce-world-tour-melbourne-2026/scrape_exhibitors.py

# Step 2: HubSpot + Firmable check
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/anz/events-outbound/salesforce-world-tour-melbourne-2026/output/exhibitors.csv \
  --output campaigns/anz/events-outbound/salesforce-world-tour-melbourne-2026/output/hubspot_check.csv
```

## Conventions
- Output writes to `output/` (gitignored)
- Each booth page is visited individually to extract the domain (domain not visible on catalog page)
- Rows with no website are still included — no data is silently dropped
