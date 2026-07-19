## Purpose
Scrape CEMAT 2026 exhibitor list into a CSV of company name, domain, and Firmable company ID for ANZ outbound outreach.

## What goes in
- Exhibitor list page: https://www.cemat.com.au/2026-exhibitor-list

## What goes out
- `output/exhibitors.csv` — `company_name`, `domain`, `firmable_id` columns; one row per exhibitor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright (listing page) + requests (detail pages) scraper — extracts company name, website domain, and Firmable ID |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/cemat-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Domains are blank for exhibitors without a website on their detail page
- Firmable IDs are blank if no match found for the domain
- Rows with no domain are still included — no data is silently dropped
- After scraping, feed `output/exhibitors.csv` into the event-scraper enrichment pipeline (`projects/slack-bots/event-scraper/scripts/`) or run `hubspot_check.py` for HubSpot enrichment
