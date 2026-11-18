# ANZ Tech Intel

## Purpose
Review sheet for an ANZ company list (first use: ~100 energy companies). For each company it finds competitor and integration-partner products, then attaches Firmable's US and APAC company counts for them. The point is to see whether a technographics outreach angle exists before writing any copy. It is adapted from `campaigns/us/tech-intel-outbound/`, but there is no SaaS gate, no rows are dropped and no email is written.

## What goes in
Files in `input/` (gitignored):
- **Company CSV or XLSX.** It needs a website/domain column. Company name and Firmable ID are optional; a URL-only list works, and the name is then read off the website. Column names are detected automatically: `company_name`/`name`/`company`, `website`/`domain`/`domain_name`/`url`, `firmable_id`/`company_id`/`firmable_company_link`.
- **Technology counts CSV.** This is the `technology_companies_by_region*.csv` export from Firmable. Counts come from `NA_MATCHING` (shown as US) and `APAC_MATCHING`. The export has no ANZ-only column.

## What goes out
`output/tech_intel_<input stem>.csv`, one row per input company:

| Column | Meaning |
|---|---|
| `company_name`, `company_name_original` | Normalised name and the name as it came in |
| `website`, `firmable_id` | From the input |
| `company_type` | Software vendor / Hardware or equipment / Energy retailer or generator / Services or installer / Other |
| `what_they_do` | One sentence |
| `personas` | Who they sell to, "X or Y" |
| `competitor1..3` + `_us_count`, `_apac_count` | Matched competitor products, most direct first |
| `partner1..3` + `_us_count`, `_apac_count` | Partner technologies, best buyer pool first, picked straight from the counts CSV (see partner step below) |
| `partner1..3_relationship` | `integrates (website)` = site shows the integration; `integrates (standard)` = standard for that product type (e.g. Modbus for inverters); `complementary` = companies running it are this company's buyers (e.g. electrical contractors on Simpro/AroFlo) |
| `partner1..3_why` | One-sentence reason from the model |
| `integrations_url` | Integrations/partners page used as evidence, if one was found |
| `competitors_unmatched`, `partners_unmatched` | Names the model suggested that were not used: `(not tracked)` = not in the counts CSV; `(..., filtered)` = tracked but below `--min-count`, generic, or over `--partner-max`; `(..., also fits)` = usable but outside the top 3 |
| `outreach_fit` | Strong = 2+ usable picks, Weak = 1, None = 0 (or no website data / error). On the energy list nearly every row is Strong, so filter on the partner columns instead |
| `fit_note` | Pick counts and the largest pool, or why there is nothing |
| `copy` | The `{copy}` block for the All Energy Australia 2026 email (sits between "Curious how your team is generating leads..." and "Our team will also be attending..."). Paragraphs separated by a blank line |
| `copy_competitors`, `copy_partners` | Which picks the copy actually names |
| `copy_error` | Blank = fine. "fallback used" = nothing survived selection, so `FALLBACK_COPY` was used; anything else = the copy failed the number check twice and is blank |

The terminal summary also lists the most common competitors and partners across the file with their counts, since a product shared by many companies on the list can be the angle.

`output/research_cache.jsonl` caches research per domain. Delete a line to re-research that domain.

## Scripts / tools
- `scripts/run_pipeline.py`: Firecrawl homepage (fallback: Firmable description by ID or domain), then one LLM call for type, description, personas and competitors. It matches competitors to the counts CSV and makes one competitor top-up call if fewer than 2 matched. Partner step: the model gets the homepage, any integrations/partners page, and every tracked technology in `PARTNER_CATEGORIES` (OT/ICS, IoT, facility devices, Industry Operations) with `--min-count` to `--partner-max` companies, about 1,700 names. It picks up to 5 from that list with a relationship label. Names outside the list are dropped. Energy retailers skip this step: every business buys power, so no technology predicts their buyers.
- Copy step (`write_copy`): one strict selection call picks up to 2 competitors plus 1 partner, or up to 2 partners when there are no competitors (`SELECT_PROMPT`). `COPY_EXCLUDE` names are never offered to it. One writing call then produces the block (`COPY_PROMPT`). Each technology has a kind, and the kind sets why the number matters: competitor (companies already paying for this kind of product), integrates (the products integrate with or work with it), buyer_signal (`complementary` partners: software the company's own customers run, so the count is a list of potential customers; never called a competitor or partner). Each technology gets two sentences: a hedged guess, then the APAC and North America counts and what they mean. "Firmable's tech intelligence dataset" appears once per block.
  Code checks run before the copy is accepted. Every number must be an exact count of a selected pick, with product names like ServiceM8 stripped first, and no repeats. The block is also rejected for dashes, any "talk"/"speak"/"plug into" wording, competitor framing when nothing is a competitor, the company's own name, more than 2 sentences per technology, or more than 2 paragraphs. A rejected block gets up to 3 attempts with feedback. Then one of `CLOSING_LINES` is appended (going beyond company data to the decision-makers, never hedged). Retailers and rows with nothing usable get `FALLBACK_COPY`. Copy is cached in the research cache and regenerated when the picks or `COPY_VERSION` change; `--no-copy` skips the step.
- `scripts/tech_matcher.py` (repo root, shared with the US pipeline): `TechCounts`, which does exact match, then fuzzy shortlist plus an LLM confirm. Every output name exists verbatim in the counts CSV.

Run from the repo root:
```bash
PYTHONPATH=. python3 campaigns/anz/tech-intel-outbound/scripts/run_pipeline.py --start 0 --count 10
PYTHONPATH=. python3 campaigns/anz/tech-intel-outbound/scripts/run_pipeline.py --start 10 --append
```
Flags: `--input`, `--counts` (default newest in `input/`), `--min-count` (default 100, US or APAC), `--partner-max` (default 150,000), `--workers` (default 4).

## Conventions
- Read-only: no HubSpot or SmartLead writes. Before outreach, source contacts, run `/smartlead-pre-campaign-check` and apply `knowledge/exclusions.md`.
- Partner picks are a starting point for review, not verified integrations. Common failure modes on the energy list: SolarEdge picked as a "partner" for inverter makers (it is a competitor) or racking makers, and tools the company itself would use (BloombergNEF, Google Drive, PTC Windchill) labelled complementary.
- Copy is a draft for review before upload. Check rows naming SolarEdge for inverter/battery makers (it's a competitor there) and any partner outside the main pools (trade job software, SCADA/Modbus/BACnet, fleet, construction, maintenance).
- `REC_VERSION` bumps re-run only the partner step for cached records (competitor research is kept); the homepage is re-scraped for context.
- The counts CSV tracks detectable technology (software, OT/industrial systems, some devices). Retailers, installers and consultancies often have no trackable competitors; check `*_unmatched` before concluding a company has none.
