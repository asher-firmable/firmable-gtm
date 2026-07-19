## Purpose
Scrape and process exhibitors from Asia Business Show for outbound outreach.

## What goes in
- Main listing page: https://www.asiabusinessshow.com/our-exhibitors (static HTML, no JS rendering needed)
- Individual exhibitor profile pages: `https://www.asiabusinessshow.com/exhibitors/{slug}`

## What goes out
- `output/exhibitors.csv` — `company_name`, `website`, `linkedin_url` columns; one row per exhibitor
  - Rows with no website or LinkedIn are included with empty fields — no data is silently dropped

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — fetches listing page, then concurrently fetches each profile to extract website + LinkedIn via JSON-LD |

## Run command
```bash
PYTHONPATH=. python3 campaigns/sea-conferences/asia-business-show-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- JSON-LD (`<script type="application/ld+json">`) is the primary extraction method; DOM selectors used as fallback
- LinkedIn extracted from `sameAs` array in JSON-LD, or `aria-label="Linkedin"` link as fallback
- ThreadPoolExecutor (5 workers) for concurrent profile fetches; 0.3s stagger between submissions
