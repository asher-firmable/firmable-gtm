## Purpose
Outbound campaign targeting exhibitors at GovWare 2026 Singapore (SICW). Covers competitor installs, integration platforms, and HubSpot status for all 211 sponsors.

## What goes in
- `govware_2026_exhibitors.csv` (from Downloads) — 211 exhibitors: name, domain, tier, booth
- Firmable MCP technographic counts (resolved during page build)

## What goes out
- `output/govware_sponsor_tech_intel.html` — self-contained SDR/AE battlecard page

## Scripts / tools
| Script | Purpose |
|---|---|
| `campaigns/anz/events-outbound/hubspot_check.py` | Shared HubSpot + Firmable enrichment |
| Scratchpad merge scripts | Research + HubSpot merge, tech normalization, HTML build |

## How to regenerate the tech intel page

Scripted version (Nov 2026): `campaigns/sea-conferences/singapore-fintech-festival-2026/` has `research_tech_intel.py` and `build_tech_intel_page.py`, which build this same page format from an event's HubSpot check. Use those for new events instead of scratchpad scripts. The manual steps below describe how this GovWare page was made.

1. Drop the updated exhibitor CSV in Downloads (name, domain, tier, booth columns).
2. Run hubspot_check.py against the CSV (use scratchpad as output dir).
3. Ensure the Firmable MCP (`claude.ai Firmable` at agents.firmable.com) is connected.
4. Ask Claude Code to regenerate the tech intel page — it will re-classify sponsors, re-resolve technographic IDs, count ANZ and global totals, and build the HTML.

## Tier breakdown (Oct 2026)
Diamond (4), Platinum Plus (10), Platinum (9), Gold (12), Sponsor (34), Exhibitor (95), Singapore Pavilion (13), Startup Pavilion (11), French Pavilion (10), IHL Pavilion (9), Italy Pavilion (8), Partner Pavilion (8), CyberSG (7), Czech Pavilion (7), IMDA (4)

## Conventions
- ANZ counts = companies headquartered in AU or NZ (same as all Firmable tech intel pages)
- Counts above 50,000 ANZ or 3M global are flagged ⚠ as inflated (generic tags like Microsoft 365, AWS, Cloudflare)
- "Talk to owner first" = active customer, trial, or open deal in HubSpot
- Output goes to `output/` (gitignored)
