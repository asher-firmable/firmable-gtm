# Event Scraping Bot — Staging

## What This Is
A staging copy of the production event scraping pipeline (`event-scraping-bot/`). Use this to test changes to scraping logic, enrichment, or any step before promoting to production.

## Scripts
- `Scrape.py` — copy of `event-scraping-bot/0_scrape_exhibitors.py` (modify freely)
- `Enrich-Company.py` — copy of `event-scraping-bot/1_enrich.py` (modify freely)

## How to Run (staging)
```bash
PYTHONPATH=. python3 staging/event-scraping-bot-staging/scripts/Scrape.py \
  --url "TEST_EVENT_URL" \
  --output "staging/event-scraping-bot-staging/output/test_raw.csv"
```

## When Ready for Production
Use `staging/Replicate-to-prod-skill.md` to diff and promote changes.

## Current Experiment
[Describe what you're testing here when you start an experiment]
