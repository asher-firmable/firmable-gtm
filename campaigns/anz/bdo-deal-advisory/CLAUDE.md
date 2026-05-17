## Purpose
Scrape BDO Australia's "Our People" directory filtered to Deal Advisory to build a contact list for outreach.

## What goes in
- BDO "Our People" listing page filtered by `serviceArea=Deal%20Advisory`

## What goes out
- `output/people.csv` — one row per person with columns: `full_name`, `title`, `practice_area`, `city`, `linkedin_url`, `bio_url`

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_people.py` | Playwright scraper — loads listing, clicks "Show more" until all results visible, visits each profile to extract person data |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/bdo-deal-advisory/scrape_people.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Rows with missing fields are included with empty values — no data is silently dropped
- Add 0.5 s delay between profile requests for polite scraping
