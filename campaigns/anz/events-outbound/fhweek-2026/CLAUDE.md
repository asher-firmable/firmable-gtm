## Purpose
Scrape FH Week 2026 exhibitor list into a CSV of company name, website, and LinkedIn URL for ANZ outbound outreach.

## What goes in
- Exhibitor list page: https://fhweek.com.au/exhibiting-brands/ (~414 exhibitors)

## What goes out
- `output/exhibitors.csv` — `company_name`, `website`, `linkedin_url` columns; one row per exhibitor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright + BeautifulSoup scraper — scrolls to load all entries, extracts name + website + LinkedIn |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/fhweek-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Deduplicates by company name (first occurrence wins)
- LinkedIn URLs matched on `linkedin.com/company/` pattern (handles country prefixes like `au.linkedin.com`)
- Rows with no website or LinkedIn are still included if a company name is found — no data is silently dropped
