# Marketing — Sub-Agent

## Purpose
Data work for the marketing team (not SDR outbound): company and contact lists used to build custom ad audiences and other marketing segments.

## What goes in
- Scraped or sourced lists (e.g. G2 categories), scoped per audience folder under `audiences/`

## What goes out
- Audience CSVs in each audience folder's `output/` (gitignored)

## Scripts / tools
- `audiences/g2-marketing-automation/` — every product in G2's Marketing Automation category with vendor domains

## Conventions
- One folder per audience under `audiences/`, each with its own `CLAUDE.md`, `scripts/` and `output/`
- Outbound campaigns belong in `campaigns/`, not here
- Apply `knowledge/exclusions.md` before an audience is used for any outreach (not needed for ad-only audiences)
