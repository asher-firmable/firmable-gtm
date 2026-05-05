## Purpose
Scrape and process sponsors/exhibitors from HR Tech Festival Asia 2026 for outbound outreach.

## What goes in
- Main listing page: https://www.hrtechfestivalasia.com/sponsors-partners (server-rendered HTML)
- A-Z paginated pages: `?azletter=X` (catches Supporting Partners not shown on the main page)
- Individual exhibitor profile pages: `https://www.hrtechfestivalasia.com/exhibitors/{slug}`

## What goes out
- `output/exhibitors.csv` — `name`, `domain`, `tier` columns; one row per exhibitor/sponsor
  - `tier` values: Gold Sponsor, Silver Sponsor, Bronze Sponsor, Exhibitor, Startup, Tabletop Showcase, Supporting Partner
  - Rows with no domain are included with an empty `domain` field
- `campaigns/quick-sales-team-size-check/input/hr-tech-festival-asia-2026-exhibitors.csv` — copied by `run_pipeline.py`
- `campaigns/quick-sales-team-size-check/output/hr-tech-festival-asia-2026-exhibitors_enriched.csv` — enriched with Firmable ID + sales team sizes

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — fetches main page + A-Z pages, follows each profile link to extract domain |
| `run_pipeline.py` | Full pipeline: scrape → copy to quick-sales-team-size-check → enrich with ANZ/SEA/APAC/US sales team sizes |

## Run commands
```bash
# Scrape only
PYTHONPATH=. python3 campaigns/sea-conferences/hr-tech-festival-asia-2026/scrape_exhibitors.py

# Full pipeline (scrape + enrich)
PYTHONPATH=. python3 campaigns/sea-conferences/hr-tech-festival-asia-2026/run_pipeline.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Rows with no domain are included with an empty `domain` field — no data is silently dropped
- Domain extracted from Contact section of each profile page; falls back to first external non-social link on the page
- Deduplicates by slug; first occurrence (from main page) wins for tier assignment
