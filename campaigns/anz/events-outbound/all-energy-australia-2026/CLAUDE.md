## Purpose
Scrape and process the full exhibitor list from All-Energy Australia 2026 (RX, 28-29 Oct 2026, MCEC Melbourne) for outbound outreach.

## What goes in
- Exhibitor directory: https://www.all-energy.com.au/en-gb/exhibitor-directory.html#/ (RX single-page app backed by a public Algolia index)

## What goes out
- `output/exhibitors.csv`: `name`, `domain`, `stand`, `categories`, `country`, `is_new`; one row per exhibitor (453 as of Oct 2026)
- `output/hubspot_check.csv`: shared HubSpot + Firmable check output
- `output/All-Energy exhibitor list.xlsx`: colour-coded workbook from `build_workbook.py`

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests scraper. Queries the directory's Algolia index directly (app ID, public search key, index and event edition ID are in the script) in one call with `hitsPerPage=1000` |

## Run commands
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/all-energy-australia-2026/scrape_exhibitors.py

PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/anz/events-outbound/all-energy-australia-2026/output/exhibitors.csv \
  --output campaigns/anz/events-outbound/all-energy-australia-2026/output/hubspot_check.csv

PYTHONPATH=. python3 campaigns/anz/events-outbound/build_workbook.py \
  --input  campaigns/anz/events-outbound/all-energy-australia-2026/output/hubspot_check.csv \
  --output "campaigns/anz/events-outbound/all-energy-australia-2026/output/All-Energy exhibitor list.xlsx"
```

## Conventions
- Output writes to `output/` (gitignored)
- Product categories column is named `categories`, not `category`, because `hubspot_check.py` treats `category` as the tier column
- No sponsor tiers on this directory, so the workbook's Tier column is blank
- 10 exhibitors have no website in the directory. LONGi (`longi.com`) and REC Traders (`rectraders.com.au`) are filled via `DOMAIN_OVERRIDES`. The other 8 (Shaanxi pavilion and two other China-based manufacturers) had no verifiable site and are left blank
- If the scraper raises a pagination error, the event has grown past 1000 exhibitors; loop over `page`
