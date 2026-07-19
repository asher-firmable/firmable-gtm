# HP Reseller Locator — ANZ

## Purpose
Scrape all Australian partner/reseller companies from HP's partner locator and enrich each with a LinkedIn company profile URL via Firmable.

## What goes in
- HP partner locator page: `https://locator.hp.com/au/en/`
- No manual input file needed — scraper fetches directly from the live site

## What goes out
- `output/hp_partners.csv` — one row per AU HP partner with columns:
  `company_name`, `website`, `domain`, `address`, `phone`, `hp_partner_type`,
  `linkedin_url`, `linkedin_source`, `firmable_id`

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_and_enrich.py` | Phase 1: Playwright browser automation → scrape HP locator (intercepts JSON API responses). Phase 2: Firmable domain lookup → extract LinkedIn URL. |

## How to run
```bash
PYTHONPATH=. python3 campaigns/anz/hp-reseller-locator/scrape_and_enrich.py
```

## Env vars required
- `FIRMABLE_API_KEY` — standard key from `.env`
- No `FIRMABLE_OS_API_KEY` needed (LinkedIn lookup only, no sales team sizes)

## Conventions
- `output/` is gitignored — never commit enriched files
- The HP locator is JS-rendered (SPA) and returns 403 to plain HTTP; Playwright with a real browser UA is required
- If `linkedin_source` shows mostly `not_found`, a Google search fallback can be added
- If only a viewport's worth of companies is scraped, the script may need to iterate over AU bounding boxes — check the console for record count vs expected
