## Purpose
Scrape FTI Consulting's experts directory filtered to Asia Pacific + Strategic Communications to build a contact list for outreach.

## What goes in
- FTI Consulting experts listing page (Coveo-powered, filter: Strategic Communications + Asia Pacific)

## What goes out
- `output/fti_consulting_experts.csv` — one row per person with columns: Name, Practice Area, Title, Email, LinkedIn link, Location, Profile URL

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_people.py` | Playwright scraper — loads Coveo-filtered listing, collects profile URLs, visits each profile to extract person data including email and LinkedIn |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/fti-consulting/scrape_people.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Rows with missing fields are included with empty values — no data is silently dropped
- 0.75 s delay between profile requests
- Email is extracted from `mailto:` link on each profile page
- LinkedIn is blank if not present on the profile
