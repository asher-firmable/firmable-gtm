## Purpose
Scrape the Black Hat US 2026 sponsor list into a CSV of company name, domain, sponsor tier, and Firmable company ID for US outbound targeting.

## What goes in
- Sponsor list page: https://blackhat.com/us-26/event-sponsors.html

## What goes out
- `output/exhibitors.csv` — `company_name`, `domain`, `sponsor_type`, `firmable_id` columns; one row per sponsor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright scraper — loads page (bypasses Cloudflare), parses sponsor tiers + links, normalises domains, enriches with Firmable IDs |

## Run command
```bash
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py
```

Inspect rendered HTML without running Firmable lookups:
```bash
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py --debug
```

## Conventions
- Output writes to `output/` (gitignored)
- `sponsor_type` is the raw tier heading text from the page (e.g. "Titanium Sponsors", "Platinum Plus")
- Domains are bare (no `www.`, no `https://`)
- Rows with no domain are still included — no data is silently dropped
- Firmable IDs are blank if no match found for the domain
