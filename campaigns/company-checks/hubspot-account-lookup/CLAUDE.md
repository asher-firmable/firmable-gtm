## Purpose
Ad-hoc HubSpot account lookup for a company list (any region/segmentation) — appends owner, SDR, open deal, and paying-customer columns without altering the rest of the input CSV.

## What goes in
- Any company CSV/Excel with a `website`/`domain` column and/or a `firmable_id` column.

## What goes out
- Same CSV with 9 columns appended at the end (all existing columns preserved as-is).

## Scripts / tools
- `scripts/hubspot_account_lookup.py` — matches each row to a HubSpot company by domain (Firmable ID used only to resolve a domain when the row has none), then appends:
  - `account_owner` — HubSpot `hubspot_owner_id`
  - `account_owner_anz` — HubSpot `company_owner_nz`
  - `account_owner_sea` — HubSpot `company_owner_sea`
  - `sdr_anz` — HubSpot `sdr__new_`
  - `sdr_sea` — HubSpot `sdr_sea`
  - `open_deal` — Yes/No, any deal not in `closedwon`/`closedlost`
  - `deal_owner` — owner(s) of open deal(s), `; `-joined if more than one
  - `paying_customer` — Yes if `customer_status` == "Paying Customer", else No
  - `hubspot_url` — direct link to the matched HubSpot company record

### Run
```bash
PYTHONPATH=. python3 campaigns/company-checks/hubspot-account-lookup/scripts/hubspot_account_lookup.py \
  --input  campaigns/company-checks/hubspot-account-lookup/input/<file>.csv \
  --output campaigns/company-checks/hubspot-account-lookup/output/<file>_enriched.csv
```

## Conventions
- Read-only against HubSpot — no writes.
- Matching is domain-first (exact, then same-SLD `CONTAINS_TOKEN` fallback); HubSpot has no `firmable_id` property to match on directly, so a Firmable ID is only used to resolve a domain via the Firmable API when the row is missing one.
- Unmatched rows get blank values in all 9 new columns, not dropped.
