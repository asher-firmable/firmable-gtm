# Partner Identification — Sub-Agent

## Purpose
Categorize a list of ~3000 companies as potential Firmable GTM partners, assigning each to one of 8 categories based on company name and description.

## What goes in
- CSV or Excel with at minimum `company_name` and `description` columns (column names are detected case-insensitively)
- Drop the file in `input/` before running

## What goes out
- `output/partner_categories.csv` — original columns plus `partner_category` and `category_reason`
- `output/` is gitignored

## Scripts / tools
- `scripts/categorize_partners.py` — main script; calls Claude API per company, writes results in batches

## Categories
| Category | Definition |
|---|---|
| GTM Recruitment | Recruits or headhunts for sales, SDR, RevOps, or GTM roles |
| Training | Sales training, SDR coaching, GTM enablement education |
| Implementation Partner | RevOps/GTM implementation services (HubSpot setup, outsourced SDR, sales process design) |
| Consulting / Advisory | GTM strategy advisors, sales transformation consultants, RevOps advisory |
| Community | Practitioner groups, associations, professional networks, or events for sales/RevOps/GTM |
| Media | Podcasts, newsletters, content creators, publications focused on sales/GTM/RevOps |
| Other | Plausible Firmable partner that doesn't fit a named category (includes reason) |
| Disqualified | No GTM/sales relevance; clearly not a partner fit |

## How to run (iterative batches)

```bash
# First batch — creates output file
PYTHONPATH=. python3 campaigns/partner-identification/scripts/categorize_partners.py \
  --start 0 --count 20

# Review output/partner_categories.csv, give feedback, then continue:
PYTHONPATH=. python3 campaigns/partner-identification/scripts/categorize_partners.py \
  --start 20 --count 100 --append

# Run all remaining rows from a given offset:
PYTHONPATH=. python3 campaigns/partner-identification/scripts/categorize_partners.py \
  --start 120 --count 9999 --append
```

## Conventions
- Requires `ANTHROPIC_API_KEY` in `.env`
- Run from repo root with `PYTHONPATH=.`
- `--append` flag appends to the existing output file; omit on first run
- One input file in `input/` at a time (script auto-selects the latest if `--input` not provided)
- Adjust the prompt inside `categorize_partners.py` between batches if categories need tuning
