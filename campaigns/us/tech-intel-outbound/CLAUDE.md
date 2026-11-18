# US Tech Intel Outbound

## Purpose
Qualify US SaaS vendors for a technographics pitch. For each company the pipeline:
1. Checks whether it is a SaaS vendor.
2. Picks at least 2 (up to 3) competitors and one integration partner (up to 2 alternates kept for reference).
3. Attaches Firmable's NA company counts for those technologies, so the email can say "we track X companies on {competitor1}".

v1 covers SaaS vendors only. Tech partners, resellers and MSPs are dropped; they will be handled later with their own copy variant.

## What goes in
Files in `input/` (gitignored):
- **Company CSV or XLSX.** It needs a company name and a website. A Firmable ID is optional; the script uses it to fetch the company description if Firecrawl can't scrape the site. Extra columns are ignored. Column names are detected automatically: `company_name`/`name`/`company`, `website`/`domain`/`url`, `firmable_id`/`company_id`.
- **Technology counts CSV.** This is the `technology_companies_by_region*.csv` export from Firmable, with columns `TECHNOLOGY_NAME, CATEGORY_NAME, NA_MATCHING, ...`. The counts come from `NA_MATCHING`.

## What goes out
`output/tech_intel_<input stem>.csv`, one row per input company:

| Column | Meaning |
|---|---|
| `company_name` | Normalised name for `{company}` merge fields (see below) |
| `company_name_original` | Name exactly as it came in |
| `website`, `firmable_id` | From the input |
| `is_saas` | Yes / No |
| `personas` | Who the company sells to, formatted "X or Y" (feeds `{personas}`) |
| `competitor1..3` | Matched technology names, in the model's relevance order (most direct competitor first) |
| `partner1..3` | Matched integration partners, best buyer fit first. Only products with 500-150,000 NA companies, excluding `GENERIC_PARTNERS` (Salesforce, Microsoft 365, AWS etc.) and the company's own products |
| `partner_source`, `integrations_url` | `integrations_page` if partners were read off the company's integrations page (URL given), else `model_knowledge` |
| `competitor1_count`, `competitor2_count`, `partner1_count` | NA_MATCHING for those picks, comma-formatted |
| `email_subject`, `email_body` | Rendered email (template `EMAIL_SUBJECT` / `EMAIL_BODY` in `run_pipeline.py`). `{firstname}` is left as a literal placeholder for SmartLead. Blank for dropped rows |
| `drop_reason` | Blank = keep. Otherwise: Not SaaS / Not enough picks (fewer than `--min-competitors` or `--min-partners` matched above `--min-count`) / Error |

`output/research_cache.jsonl` caches the research per domain. It holds the raw LLM picks, the matches to the counts CSV, and a version field `v`; records from an older version get the partner step re-run automatically. Delete a line to force that domain to be re-researched from scratch.

## Scripts / tools
- `scripts/run_pipeline.py` is the main workflow. Its stages:
  0. Normalise company names with `scripts/normalize_company_names.normalize` (strips legal suffixes, dot-TLDs, parentheticals). Names still 3+ words afterwards are replaced with the `brand_name` the research call reads off the website.
  1. Scrape the homepage with Firecrawl, or fall back to the Firmable description.
  2. Make one LLM call (`scripts/ai.ask_claude`, which routes through Bifrost) for SaaS yes/no, brand name, competitors and personas.
  3. Partner step: find the integrations/marketplace page from the homepage links (or try `/integrations`), scrape it, and have the model pick up to 6 partners listed there, specialised tools first. Falls back to model knowledge when no page exists. Also returns the company name as shown on the site, which replaces the input name when that name is 3+ words or doesn't match the domain.
  4. Match all product names to the counts CSV; the confirm call gets the company context and category so short names ("Pearl", "IMS") don't match unrelated products.
  5. Competitor top-up: if fewer than `--min-competitors` matched, one extra call asks for more. Runs once per domain; `topped_up` is cached. Partners are never topped up with guesses.
  6. Filter and render the email. The partner paragraph names partner1 only; if no partner qualifies it is left out and the email is competitor-only.
- `scripts/tech_matcher.py` (repo root, shared with `campaigns/anz/tech-intel-outbound/`) holds `TechCounts`. It does an exact normalised match first; if that fails, it builds a fuzzy shortlist and a small LLM call confirms the pick. The model can only choose a name from the shortlist, so every output name exists verbatim in the counts CSV.

Run from the repo root:
```bash
# Sample batch (creates output file)
PYTHONPATH=. python3 campaigns/us/tech-intel-outbound/scripts/run_pipeline.py --start 0 --count 20

# Next batches
PYTHONPATH=. python3 campaigns/us/tech-intel-outbound/scripts/run_pipeline.py --start 20 --count 500 --append
```
Flags:
- `--input` / `--counts`: default to the newest matching files in `input/`.
- `--min-count`: a technology must have at least this many NA companies to be used. Default 100.
- `--min-competitors` / `--min-partners`: rows with fewer usable picks are dropped. Defaults: 2 competitors, 0 partners (companies without a usable partner still get a competitor-only email). On the first 100 rows: 67 kept, 45 with a partner, 22 competitor-only.
- `--partner-min` / `--partner-max`: NA company range for a partner to be used. Default 500 / 150,000.
- `--workers`: number of parallel workers. Default 4.

## Conventions
- Email copy lives in `EMAIL_SUBJECT` / `EMAIL_BODY` in `run_pipeline.py`. It uses competitor1-2, partner1-2, their counts, `{company}` (normalised name) and `{personas}`. Edit the template there; re-running from cache re-renders without new API calls.
- This pipeline makes no HubSpot or SmartLead writes. Before upload, source contacts, then run `/smartlead-pre-campaign-check` and apply `knowledge/exclusions.md`.
