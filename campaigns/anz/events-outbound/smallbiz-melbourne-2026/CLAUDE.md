## Purpose
Scrape Small Biz Melbourne 2026 exhibitor list into a CSV of company name, website, domain, LinkedIn URL, and Firmable company ID for ANZ outbound outreach.

## What goes in
- Exhibitor listing page: https://www.smallbizmelbourne.com.au/exhibit
- Individual profile pages: https://www.smallbizmelbourne.com.au/exhibit/{slug}

## What goes out
- `output/exhibitors.csv` — `company_name`, `website`, `domain`, `linkedin_url`, `firmable_id` columns; one row per 2026 exhibitor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright (listing page) + requests (profile pages) — extracts 2026 exhibitors only, resolves website URL from each profile page, looks up Firmable ID |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/smallbiz-melbourne-2026/scrape_exhibitors.py
```

## Conventions
- Filters to 2026 exhibitors only (year badge must equal "2026")
- Website URL sourced from the exhibitor's individual profile page (first non-social external link)
- LinkedIn matched on `linkedin.com/company/` or `linkedin.com/showcase/` patterns
- Rows with no website are still included — no data is silently dropped
- After scraping, feed `output/exhibitors.csv` into `hubspot_check.py` for HubSpot enrichment
