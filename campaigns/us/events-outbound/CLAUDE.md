## Purpose
Outbound campaigns targeting sponsors and exhibitors at US trade events, conferences, and expos.

## What goes in
- Event sponsor/exhibitor lists (scraped from event websites)
- Event metadata (name, date, URL)

## What goes out
- `output/exhibitors.csv` — company name, domain, sponsor type, Firmable ID per event
- Downstream: feeds into enrichment and SmartLead upload pipeline

## Folder structure
Each event gets its own sub-folder named `{event-name}-{year}/`:
```
events-outbound/
└── blackhat-us-2026/
    ├── scrape_exhibitors.py
    └── output/
        └── exhibitors.csv
```

## Scripts / tools
- `scrape_exhibitors.py` — per-event scraper; extracts company name + website from sponsor list page, adds sponsor tier and Firmable ID

## Conventions
- One scraper script per event, named `scrape_exhibitors.py`
- Output always goes to `output/` inside the event folder (gitignored)
- Run from repo root: `PYTHONPATH=. python3 campaigns/us/events-outbound/{event-folder}/scrape_exhibitors.py`
- Pages behind Cloudflare or JavaScript rendering require Playwright; static pages can use requests + BeautifulSoup
