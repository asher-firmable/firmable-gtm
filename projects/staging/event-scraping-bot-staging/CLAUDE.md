# Event Scraping Bot — Staging

## What This Is
A staging copy of the production event scraping pipeline (`projects/event-scraper/`). Use this to test changes to scraping logic, enrichment, or any step before promoting to production.

## Scripts
- `Scrape.py` — copy of `projects/event-scraper/0_scrape_exhibitors.py` (modify freely)
- `Enrich-Company.py` — copy of `projects/event-scraper/1_enrich.py` (modify freely)

## How to Run (staging)
```bash
PYTHONPATH=. python3 projects/staging/event-scraping-bot-staging/scripts/Scrape.py \
  --url "TEST_EVENT_URL" \
  --output "projects/staging/event-scraping-bot-staging/output/test_raw.csv"
```

## When Ready for Production
Use `projects/staging/Replicate-to-prod-skill.md` to diff and promote changes.

## Current Experiment
[Describe what you're testing here when you start an experiment]
