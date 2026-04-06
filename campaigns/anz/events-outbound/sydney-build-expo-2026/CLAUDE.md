## Purpose
Scrape and process exhibitors from Sydney Build Expo 2026 for outbound outreach.

## What goes in
- Exhibitor list page: https://www.sydneybuildexpo.com/exhibitor-list (JS-rendered via anchor.js)

## What goes out
- `output/exhibitors.csv` — `name`, `domain` columns; one row per exhibitor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright scraper — loads exhibitor list, clicks each card to extract website domain |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/sydney-build-expo-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Rows with no domain are included with an empty `domain` field — no data is silently dropped
- After scraping, feed `output/exhibitors.csv` into the event-scraper enrichment pipeline (`projects/slack-bots/event-scraper/scripts/`)
