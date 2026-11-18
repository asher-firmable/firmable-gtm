# Marketing — Sub-Agent

## Purpose
Data work for the marketing team (not SDR outbound): company and contact lists used to build custom ad audiences and other marketing segments, plus market maps of GTM communities.

## What goes in
- Scraped or sourced lists (e.g. G2 categories), scoped per audience folder under `audiences/`
- Web research for community maps, scoped per folder under `communities/`

## What goes out
- Audience CSVs in each audience folder's `output/` (gitignored)
- Community CSVs in each community folder's `output/` (gitignored)

## Scripts / tools
- `audiences/g2-marketing-automation/` — every product in G2's Marketing Automation category with vendor domains
- `communities/gtm-communities/`: GTM engineering and adjacent GTM communities (US and ANZ) with founder, title and LinkedIn

## Conventions
- One folder per audience under `audiences/`, each with its own `CLAUDE.md`, `scripts/` and `output/`
- One folder per community map under `communities/`, each with its own `CLAUDE.md` and `output/`
- Outbound campaigns belong in `campaigns/`, not here
- Apply `knowledge/exclusions.md` before an audience is used for any outreach (not needed for ad-only audiences)
