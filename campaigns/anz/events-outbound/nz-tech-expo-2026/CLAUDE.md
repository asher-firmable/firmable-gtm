## Purpose
Scrape and process exhibitors from NZ Tech Expo 2026 (18 September 2026, Shed 10, Auckland) for outbound outreach.

## What goes in
- Companies page: https://nztechexpo.co.nz/companies (client-rendered React SPA)

## What goes out
- `output/exhibitors.csv` — `name`, `domain`, `category` columns; one row per exhibitor
  - `category` is one of `Partner`, `Sponsor`, `Company`, `Supporter` (per the page's own sections)

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright scraper — renders the page, walks the DOM tagging each logo `<a href>` with its nearest section heading, dedupes repeated/featured logos |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/nz-tech-expo-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Several Partner logos are re-shown a second time inside the main Companies grid as featured highlights — deduped by (name, href)
- After scraping, run the shared HubSpot + Firmable check: `campaigns/anz/events-outbound/hubspot_check.py`
