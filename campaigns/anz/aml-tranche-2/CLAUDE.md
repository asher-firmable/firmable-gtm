# AML Tranche 2 — Sub-Agent

## Purpose
Qualify and triage companies that sell into the AML/compliance space as outreach targets, following AUSTRAC's Tranche 2 reforms (effective 1 July 2026). Two-phase pipeline: AI description check, then HubSpot deal + owner enrichment.

## Context
From 1 July 2026, ~80,000 Australian firms (law firms, accountants, conveyancers, real estate agencies, precious metal dealers) must comply with AUSTRAC AML/CTF rules. We target companies selling *to* those firms: compliance/regtech software, ID-verification, AML training providers, legal & accounting SaaS, AML consultants. Their addressable market grew overnight — Firmable can hand them the full newly-regulated list with the right contacts.

Do not pitch Firmable as an AML tool to the regulated firms themselves. Stay focused on vendors selling into them.

## What goes in
- **Phase 1 input:** CSV downloaded from Firmable, filtered by AML-related keywords (compliance, regtech, KYC, identity verification, AML, legal software, accounting software). Drop in `campaigns/company-checks/description-check/input/`.
- **Phase 2 input:** Approved CSV from Phase 1 (False/No rows removed). Drop in `campaigns/anz/aml-tranche-2/input/`.

## What goes out
- **Phase 1 output:** `campaigns/company-checks/description-check/output/<file>.csv` — Yes/No per company + reason
- **Phase 2 output:** `campaigns/anz/aml-tranche-2/output/aml_hubspot_<timestamp>.csv` — same rows enriched with HubSpot deal status, owner, last contacted, engagement status

## Pipeline

### Phase 1 — Description Check (AI true/false)
1. Drop the Firmable CSV in `campaigns/company-checks/description-check/input/`
2. Run `/description-check`
3. When prompted for the question, use:
   > "Does this company sell compliance software, regtech, AML or KYC tools, identity verification, or related services that would help law firms, accountants, conveyancers, real estate agencies, or precious metal dealers meet their new AML/CTF obligations under AUSTRAC Tranche 2?"
4. Review the output CSV. Remove rows where `result = No`. Save the approved shortlist.

### Phase 2 — HubSpot Enrichment (read-only)
1. Drop the approved CSV in `campaigns/anz/aml-tranche-2/input/`
2. Run:
```bash
PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/hubspot_check.py \
  --input campaigns/anz/aml-tranche-2/input/<approved_file>.csv
```
Output written to `campaigns/anz/aml-tranche-2/output/aml_hubspot_<timestamp>.csv`.

## Scripts
- `scripts/hubspot_check.py` — read-only HubSpot enrichment: deal status, owner, last contacted, engagement status

## Output Columns (Phase 2)
| Column | Values |
|---|---|
| `hs_exists` | Yes / No |
| `hs_deal_status` | open / closed-won / closed-lost / none (blank if not in HubSpot) |
| `hs_deal_stage` | Human-readable pipeline stage label |
| `hs_account_owner` | Owner full name (blank if unowned) |
| `hs_last_contacted` | D Mon YYYY format (blank if never contacted) |
| `hs_engagement_status` | HubSpot outreach engagement status value |

## Conventions
- Phase 2 is read-only. No writes to HubSpot.
- Requires `HUBSPOT_ACCESS_TOKEN` in `.env`
- Output files are gitignored
- For follow-up deal reopening, hand the `hs_deal_status = closed-lost` rows to the relevant account owner (`hs_account_owner`) with the AML angle from the Head of Sales message
