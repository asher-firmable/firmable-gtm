## Purpose
Scrape and process sponsors from CyberCon Melbourne 2026 (AISA) for outbound outreach.

## What goes in
- Sponsors page: https://melbourne2026.cyberconference.com.au/sponsors (server-rendered Webflow site)

## What goes out
- `output/exhibitors.csv` — `name`, `domain`, `tier` columns; one row per sponsor
  - `tier` is one of `Ruby`, `Diamond`, `Platinum`, `Gold`, `Silver`, `Bronze`, `Startup`, `Special Category`

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — reads the tiered sponsor listing, then visits each sponsor's detail page (`/sponsors/<slug>`) to pull their website from the "Visit <Company>" link |

## Run command
```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/cybercon-melbourne-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Some companies appear in both a paid tier and the closing "Sponsors" (special-category) section — deduped by slug, keeping the first (highest) tier seen
- Zoho Corporation has no "Visit" link on its detail page — domain filled as `zoho.com` manually
- Cisco's "Visit" link resolves to `splunk.com` (Cisco owns Splunk) — not a scraping error
- After scraping, run the shared HubSpot + Firmable check: `campaigns/anz/events-outbound/hubspot_check.py`
- Thales Cyber Services' domain on the sponsors page changed from `tesserent.com` to `thalesgroup.com` between scrapes

## Tech Intel page

A self-contained SDR/AE battlecard page for the event:

`output/cybercon_sponsor_tech_intel.html`

Covers all 154 sponsors (as of Oct 2026 re-scrape): 101 SaaS vendors, 28 service providers, 25 not applicable. Each SaaS card shows 2 competitors and 2 integration platforms with ANZ and global Firmable technographic counts. Each service provider card shows 2 partner platforms with counts. HubSpot links and Firmable links are included per card.

### To regenerate the tech intel page

1. Re-run the scraper to pick up new sponsors.
2. Re-run `hubspot_check.py` to refresh HubSpot status.
3. Ensure the Firmable MCP (`claude.ai Firmable` at agents.firmable.com) is connected.
4. Ask Claude Code to regenerate the tech intel page — it will re-classify sponsors, re-resolve technographic IDs, and recount ANZ and global totals.
