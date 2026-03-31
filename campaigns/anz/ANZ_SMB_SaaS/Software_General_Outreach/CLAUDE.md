# ANZ SMB SaaS / Software — General Outreach

## Purpose
ANZ outbound campaign targeting SMB SaaS and Software companies. General outreach (not signal-driven). Filters to companies with APAC sales team size ≤ 4.

## What goes in
- Company/contact CSV dropped into `input/` (columns required: `email`, `domain`)
- Source: Firmable export or manual upload

## What goes out
- `data/qualified/` — contacts that passed all eligibility gates, enriched with sales team size
- `data/validated/` — after DNC and contact validation
- `data/final/` — ready for SmartLead upload

## Qualification Pipeline

Run in this order:

### Step 1 — HubSpot eligibility + Firmable enrichment
```bash
PYTHONPATH=. python3 scripts/hubspot_eligibility.py \
  --input campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach/input/contacts.csv \
  --output-dir campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach/data/qualified/
```

Exclusion rules applied automatically:
- Active Trial or Paying Customer → excluded
- Company contacted in last 30 days → excluded
- Contact contacted in last 30 days → excluded
- Active tasks/sequences on contact or company → excluded
- DNC Register = "Yes" → excluded

Enrichment added automatically:
- `au_sales_team_size`, `nz_sales_team_size`, `sea_sales_team_size`, `apac_sales_team_size`

### Step 2 — ANZ SMB size filter (manual, post-pipeline)
After reviewing `eligible_contacts_<timestamp>.csv`:
- **Keep** rows where `apac_sales_team_size` is 0–4
- **Remove** rows where `apac_sales_team_size` ≥ 5
- **Flag for review** rows where `apac_sales_team_size` is blank/unknown

Move the filtered file to `data/validated/` before uploading.

## Conventions
- Do NOT upload to SmartLead until size filter has been manually applied and confirmed
- Always confirm lead count, campaign name, and sender before activating SmartLead
- Input CSV must have `email` and `domain` columns at minimum
