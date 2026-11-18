## Purpose
Scrape and process exhibitors/sponsors from Tech Week Singapore 2026 for outbound outreach.

## What goes in
- Main listing page: https://www.singaporetechnologyweek.com/exhibitor-list-2026 (server-rendered ASP.events "SHOWOFF" platform)
- Paginated via `?page=1..16` (50 exhibitors/page, 16th page partial) — same `filters.events` / `sortby` / `azLetterField` query params on every page
- Individual exhibitor detail pages: `https://www.singaporetechnologyweek.com/exhibitors/{slug}`

## What goes out
- `output/exhibitors.csv` — `name`, `domain`, `tier`, `stand` columns; one row per exhibitor/sponsor
  - `tier` values: Diamond Sponsor, Platinum Sponsor, VIP Lounge Sponsor, Theatre Sponsor, Mainstage Sponsor, Knowledge Partner, Gold Sponsor, Delegate Sponsor, Executive Lunch Sponsor, Lunch Host, Coffee Point Sponsor, Exhibitor
  - Rows with no domain are included with an empty `domain` field — no data is silently dropped

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | requests + BeautifulSoup scraper — fetches all 16 listing pages, then visits each exhibitor detail page's "Website" section to resolve the domain |

## Run command
```bash
PYTHONPATH=. python3 campaigns/sea-conferences/tech-week-singapore-2026/scrape_exhibitors.py
```

## Conventions
- Output writes to `output/` (gitignored)
- Deduplicated by slug across listing pages
- Domain resolved from the detail page's labeled "Website" link; falls back to first external non-excluded link on the page
- After scraping, run `/event-exhibitor-check` (or the shared HubSpot/Firmable enrichment step) for the eligibility breakdown

## Known issues (2026-09-09 scrape)
784 exhibitors scraped (781 after deduping 3 exact double-listings: Vertiv, LHS Electronics Enterprise, Shanghai New Power Automotive Technology), 32 left with a blank domain after cleanup:
- **28 companies** (GE Vernova, Nutanix, ClickHouse, ENERVEX, Netwrix Corporation, 888 Tech Exchange Ventures, Owl Cyber Defense, Resecurity, Ablerex SG, Anord Mardix, Apex Fire Systems, BAND-IT, BAOYU, FANGSHENG, GEPLEADER, HANSA-FLEX AG, JIKA EPC Services, Movexx, NETONX, NFS, OFEX(Guangdong)Co.,Ltd, QINGDAO QINGFLEX HOSE FACTORY, SANSIN, Suzhou Magnox Hygienic Materials Co., Ltd, SYSLAB, SYSTEX, Troax Safety Systems, Valex Semiconductor Materials (Zhejiang) Co., Ltd., Zhongchuang Meizong Information Technology (Chongqing) Co., Ltd.) had no "Website" section on their detail page — the scraper's fallback picked up a sitewide Singapore Airlines travel-partner ad link (`singaporeair.com`) instead.
- **2 companies** (Ningbo Hongwu Pipe Industry Co., Ltd., NINGBO MERRY MEGA) had a malformed `Http:` href on their detail page.
- **1 company** (Wonderful) had a `mailto:info@wonderful.ai` link picked up instead of a website.

**Recovered via Firmable name search (same session):** of the 32 above, 15 were re-matched by searching Firmable on company name and accepting only high-confidence (exact/near-exact name + plausible industry) results — GE Vernova, Nutanix, ClickHouse, ENERVEX, Netwrix Corporation, 888 Tech Exchange Ventures, Owl Cyber Defense, Resecurity, Ablerex SG, Apex Fire Systems, BAND-IT, HANSA-FLEX AG, Movexx, SYSTEX, Troax Safety Systems. Their domains, Firmable IDs, and sales team sizes are filled in; 5 of them (GE Vernova, Nutanix, ClickHouse, Netwrix, Resecurity) turned out to already exist in HubSpot. The remaining 17 (Anord Mardix, BAOYU, FANGSHENG, GEPLEADER, JIKA EPC Services, NETONX, Ningbo Hongwu Pipe Industry, NINGBO MERRY MEGA, OFEX(Guangdong), QINGDAO QINGFLEX HOSE FACTORY, SANSIN, Suzhou Magnox Hygienic Materials, SYSLAB, Valex Semiconductor Materials, Zhongchuang Meizong Information Technology, NFS, Wonderful) had no confident match and stay domain-less.

**Firmable domain-match failures beyond the blank-domain set:** ~345 exhibitors have a real domain but no Firmable record found by domain. Per user decision (2026-09-09), these were left as-is (status: Ineligible — No Firmable match) rather than running the same name-search sweep across all of them — expected low hit rate (mostly small Chinese/Korean industrial manufacturers likely outside Firmable's ANZ-focused coverage) versus the cost of ~345 individual searches.

## Output — combined deliverable
`output/tech_week_singapore_2026_exhibitors.xlsx` is the authoritative single file: all 781 deduped exhibitors, one row each, with `status` (Eligible/Ineligible) + `reason` computed per the standard event-exhibitor-check priority order (customer/trial → open deal → contacted <30d → next step scheduled → no Firmable match), plus tier, stand, HubSpot fields (owner, SDR AU/NZ/SEA, engagement status, customer status, open deal + deal owner, last contacted), and Firmable fields (found/ID/sales team AU/NZ/SEA). `firmable_id` and the HubSpot link are clickable. `output/eligible_companies.csv` predates the 15-company name-match fix and the sdr_sea/deal_owner columns — treat the xlsx as current, not the CSV.
