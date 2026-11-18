## Purpose
Scrape and process exhibitors from Melbourne Build Expo 2026 for outbound outreach.

## What goes in
- Exhibitor page: https://melbournebuildexpo.com/meet-exhibitors (ExpoFP embed)
- Data source: https://melbournebuild2026.expofp.com/data/data.js (`var __data = {...}` with exhibitors, booths, categories)

## What goes out
- `output/exhibitors.csv`: `name`, `domain`, `category`, `stand`, `domain_source` (website / email / manual)
- `output/hubspot_check.csv`: shared HubSpot + Firmable check output
- `output/eligible_companies.csv`: eligible rows only
- `output/melbourne_build_expo_2026_exhibitors.xlsx`: combined workbook (same columns as CyberCon Melbourne 2026)

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests scraper over ExpoFP `data.js`; maps booth numbers to `stand`, category names to `category`; falls back to contact email domain when no website is listed |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/melbourne-build-expo-2026/scrape_exhibitors.py
```
Then run `campaigns/anz/events-outbound/hubspot_check.py` and `build_workbook.py` per `/event-exhibitor-check`.

## Conventions
- Output writes to `output/` (gitignored)
- ExpoFP categories for this event are only "Melbourne Build" / "Featured Exhibitors"; they land in the workbook's Tier column
- ~58 exhibitors (Nov 2026 scrape) list no website or usable email. Their domains were researched manually and filled into `exhibitors.csv` with `domain_source = manual`; re-scraping overwrites these, so redo the lookup after a re-scrape
- "Reserved" is a placeholder booth, not a company
