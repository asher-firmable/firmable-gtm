## Purpose
Scrape and process exhibitors from SecTech Roadshow Australia for outbound outreach.

## What goes in
- Exhibitor list page: https://sectechroadshow.com.au/exhibitors-sectech/ (static HTML, Elementor/WordPress)

## What goes out
- `output/exhibitors.csv` — `name`, `website` columns; one row per unique exhibitor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — fetches exhibitor page, extracts name + website from each exhibitor card |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/SecTech-Roadshow-Australia/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Deduplicates on `(name, website)` — first occurrence wins
- Rows with no website are included with an empty `website` field — no data is silently dropped
- After scraping, feed `output/exhibitors.csv` into the event-scraper enrichment pipeline (`projects/slack-bots/event-scraper/scripts/`)
