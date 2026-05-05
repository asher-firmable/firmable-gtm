# Company Checks — Sub-Agent

## Purpose
Pre-campaign eligibility gate for any region. Reads a company CSV, checks each domain against HubSpot, and writes a clean list of eligible companies ready for SmartLead upload.

## What goes in
- Drop one CSV into `input/` before running `/smartlead-pre-campaign-check`
- Required: at least one domain column — accepts `domain`, `website`, `company_website`, `company_domain`
- Optional but recommended: `name` / `company_name`, `firmable company link` / `firmable_link`

## What goes out
- `output/<your-filename>.csv` — eligible companies only
- Columns: `company_name`, `domain`, `firmable_company_link`, `firmable_company_id`

## Scripts
| Script | Purpose |
|---|---|
| `scripts/smartlead_pre_campaign_check.py` | Shared — audit CSV against HubSpot, write eligible list |

## Filter logic
A company is filtered out if ANY of the following are true:
1. `trial_status` = "Active Trial" or "Paying Customer from Trial"
2. `outreach_engagement_status` is set and NOT "Pool" or "Time Out"
3. `notes_last_contacted` (company level) is within the last 30 days
4. Any active (NOT_STARTED, future/open due date) company-level task exists
5. Any open (non-closed) deal exists on the company

Companies NOT found in HubSpot are treated as eligible by default.

## Domain matching
Domains with ccTLDs (e.g. `shopify.com.au`) are reduced to their root domain (`shopify.com`) before the HubSpot lookup, using a CONTAINS search — so both `shopify.com` and `shopify.com.au` stored in HubSpot will match.

## Conventions
- Drop one CSV into `input/` at a time; the script picks the most recently modified one
- `output/` is gitignored — never commit output files
- `input/*.csv` is gitignored — never commit input data
- Required env var: `HUBSPOT_ACCESS_TOKEN` in `.env`
- Run from repo root with `PYTHONPATH=.`
