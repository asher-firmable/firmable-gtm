## Purpose
Outbound campaigns targeting exhibitors and sponsors at SEA tech conferences and expos.

## What goes in
- Conference exhibitor/sponsor lists (scraped from event websites)
- Event metadata (name, date, URL)

## What goes out
- `output/exhibitors.csv` — name + domain + event per exhibitor
- Downstream: feeds into enrichment → scoring → SmartLead upload via the main event-scraper pipeline

## Folder structure
Each event gets its own sub-folder named `{event-name}-{year}/`:
```
sea-conferences/
├── asiatechx-sg-2025/
│   ├── CLAUDE.md
│   ├── scrape_exhibitors.py
│   └── output/
│       └── exhibitors.csv
└── hr-tech-festival-asia-2026/
    ├── CLAUDE.md
    ├── scrape_exhibitors.py
    ├── run_pipeline.py
    └── output/
        └── exhibitors.csv
```

## Scripts / tools
- `scrape_exhibitors.py` — per-event scraper; extracts name + domain + event from the conference exhibitor list page
- Downstream enrichment/scoring/upload uses `projects/slack-bots/event-scraper/scripts/` pipeline

## Conventions
- One scraper script per event, named `scrape_exhibitors.py`
- Output always goes to `output/` inside the event folder (gitignored)
- Run from repo root: `PYTHONPATH=. python3 campaigns/sea-conferences/{event-folder}/scrape_exhibitors.py`
- Rows with no domain are included with an empty `domain` field — no data is silently dropped
