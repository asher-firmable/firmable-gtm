## Purpose
Scrape and process exhibitors/sponsors from AsiaTechX Singapore 2025 for outbound outreach.

## What goes in
- Exhibitor list page: https://asiatechxsg.com/sponsors/sponsor-exhibitor-list/ (plain HTML)
- Individual exhibitor profile pages: https://asiatechxsg.com/sponsors/sponsors/{slug}/

## What goes out
- `output/exhibitors.csv` — `name`, `domain`, `event` columns; one row per exhibitor/sponsor
  - `event` values: BroadcastAsia, CommunicAsia, SatelliteAsia, TechXLR8Asia, The AI Summit Singapore, ATxSG
  - Rows with no domain (LinkedIn-only contact) are included with an empty `domain` field

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — fetches listing page, follows each profile link to extract domain |

## Run command
```bash
PYTHONPATH=. python3 campaigns/sea-conferences/asiatechx-sg-2025/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Rows with no domain are included with an empty `domain` field — no data is silently dropped
- LinkedIn URLs in the Contact section → domain recorded as empty string
- After scraping, feed `output/exhibitors.csv` into the event-scraper enrichment pipeline (`projects/slack-bots/event-scraper/scripts/`)
