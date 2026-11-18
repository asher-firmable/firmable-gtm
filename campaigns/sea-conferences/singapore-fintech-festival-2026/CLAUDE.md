## Purpose
Scrape the Singapore FinTech Festival 2026 exhibitor list (Singapore EXPO, 18 to 20 Nov 2026) and run it through the standard event exhibitor check.

## What goes in
- Source page: https://www.fintechfestival.sg/exhibitors (server-rendered, all ~466 exhibitors on one page)
- Each card links to a detail view `/exhibitors?sff_website_url=<slug>` with the company website ("Visit website" button) and LinkedIn

## What goes out
- `output/exhibitors.csv`: name, website, linkedin, country, stand, hall, category, profile_url
- `output/hubspot_check.csv`: HubSpot + Firmable check (from `campaigns/anz/events-outbound/hubspot_check.py`)
- `output/eligible_companies.csv` and `output/<name>.xlsx`: standard event check deliverables
- `output/sff_2026_eligible_tech_intel.html`: SDR/AE tech intel battlecard for the eligible exhibitors (GovWare format), plus `.artifact.html` for publishing as a claude.ai page
- `output/tech_intel_research.jsonl`, `tech_list.txt`, `tech_counts_mcp.json`: tech intel intermediates and caches

## Scripts / tools
- `scrape_exhibitors.py`: requests + BeautifulSoup. Parses list cards, then fetches each detail page (4 threads) for website + LinkedIn. Dedupes on (name, website).
- Downstream: `/event-exhibitor-check` (hubspot_check.py, build_workbook.py in `campaigns/anz/events-outbound/`)

```bash
PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/scrape_exhibitors.py
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/sea-conferences/singapore-fintech-festival-2026/output/exhibitors.csv \
  --output campaigns/sea-conferences/singapore-fintech-festival-2026/output/hubspot_check.csv
PYTHONPATH=. python3 campaigns/anz/events-outbound/build_workbook.py \
  --input  campaigns/sea-conferences/singapore-fintech-festival-2026/output/hubspot_check.csv \
  --output campaigns/sea-conferences/singapore-fintech-festival-2026/output/sff_2026_exhibitors.xlsx
```

## Tech intel page (eligible exhibitors)

Reusable version of the GovWare 2026 battlecard. Three steps:

1. Research (Python): `research_tech_intel.py` reads the Eligible rows of `hubspot_check.csv` (joined to `exhibitors.csv` by row order), scrapes each homepage with Firecrawl (Firmable description as fallback), and makes one Claude call per company for bucket (saas/services/na), a one-line description, competitors and integrations/partner platforms. Pick names are matched to the Firmable technology counts CSV with `scripts/tech_matcher.TechCounts` (exact, else shortlist + LLM confirm). Keeps up to 2 competitors + 2 integrations with 100+ global companies. `BAD_MATCHES` drops known name collisions (e.g. Copper CRM for the Copper custodian). Cache: `output/tech_intel_research.jsonl`; writes `output/tech_list.txt`.
2. ANZ + SG+MY counts (Firmable MCP, not scriptable from Python): for each name in `tech_list.txt`, `get_filter_options(identifier="tech_intelligence", searchTerm=name)` for the option id, then `filter_search` with that tech + `hq_country` AU,NZ and again with SG,MY, reading `totalCompany`. Free and read-only. Run as 3 parallel agents over slices of the list; merge into `output/tech_counts_mcp.json` as `{tech: {"id", "matched_text", "anz", "sgmy"}}`. Reuse the existing JSON and only query new technologies on reruns.
3. Page (Python): `build_tech_intel_page.py --downloads` merges everything into the HTML page and copies it to ~/Downloads. Global counts come from `GLOBAL_MATCHING` in the counts CSV. ⚠ = over 50,000 ANZ or 3M global. Opener = the largest non-⚠ pick by ANZ + SG+MY.

```bash
PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/research_tech_intel.py --count 10   # dry run
PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/research_tech_intel.py
# step 2 via Firmable MCP -> output/tech_counts_mcp.json
PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/build_tech_intel_page.py --downloads
```

Counts CSV default: `campaigns/anz/tech-intel-outbound/input/technology_companies_by_region_90d_2026-10-16-0950.csv` (override with `--counts`). For another event, copy both scripts into the event folder; only the input loading and header text are event-specific.

## Conventions
- `category` is the first focus area shown on the card (extra areas are hidden behind "+N" on the site)
- No ExpoFP feed: `sgfintechfestival2026.expofp.com/data/data.js` has booths but an empty exhibitors array, so scrape the main site
- Rows with no website are kept with a blank `website`
- 16 HubSpot false matches (domain-word fallback, e.g. State Bank of India -> Judo Bank) were reset to "not in HubSpot" in `hubspot_check.csv` for this run; the raw output was kept in the session scratchpad
- Read-only against HubSpot and Firmable
