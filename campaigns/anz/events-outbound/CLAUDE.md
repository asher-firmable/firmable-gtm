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
└── sydney-build-expo-2026/
    ├── scrape_exhibitors.py
    └── output/
        └── exhibitors.csv
```

## Scripts / tools
- `scrape_exhibitors.py` — Playwright scraper; extracts name + domain from the event's exhibitor list page
- Downstream enrichment/scoring/upload uses `projects/slack-bots/event-scraper/scripts/` pipeline

## Conventions
- One scraper script per event, named `scrape_exhibitors.py`
- Output always goes to `output/` inside the event folder (gitignored)
- Run from repo root: `PYTHONPATH=. python3 campaigns/anz/events-outbound/{event-folder}/scrape_exhibitors.py`
