# Contact + Account Enrichment

## Purpose
Enrich an arbitrary contact list with full HubSpot account status (customer/deal/owner/engagement/last-contacted), the contact's HubSpot location, and Firmable ANZ sales team size — the "full account enrichment" column set referenced in prior sessions.

## What goes in
Drop a CSV or Excel (`.xlsx`) file into `input/`. Required/expected columns (case-insensitive):
- `email` (or `primary_work_email` / `work_email`) — required
- `domain` (or `company_website` / `website` / `fqdn`) — required for HubSpot company-level and Firmable columns; rows without a resolvable domain get those columns left blank

## What goes out
A CSV written to `output/<original_filename>_enriched.csv` with the original columns preserved plus:

| Column | Description |
|---|---|
| `Exists in HubSpot?` | Yes/No — company found by domain |
| `Paying Customer?` | Yes if company `lifecyclestage == customer` |
| `Open Deal?` | Yes if any associated deal is in a non-closed stage |
| `HubSpot Deal Stage` | Open deal stage label(s); blank unless Open Deal? = Yes |
| `HubSpot Account Owner` | Resolved from `hubspot_owner_id` via HubSpot owners list |
| `HubSpot Engagement Status` | `outreach_engagement_status` company property |
| `Last Contacted` | Most recent `notes_last_contacted` across all contacts associated with the company, `D Mon YYYY` |
| `Location` | Contact's HubSpot `city, state, country` (blank if contact not in HubSpot or fields unset) |
| `Firmable ID` | Firmable company ID resolved from domain |
| `AU Sales Team Size` / `NZ Sales Team Size` / `Total ANZ Sales Team Size` | Firmable regional headcount (AU + NZ) |

## Scripts / tools
- `scripts/enrich_contacts.py` — the enrichment pipeline described above. Read-only against HubSpot and Firmable (no CRM writes).

## How to run
```bash
PYTHONPATH=. python3 campaigns/contact-account-enrichment/scripts/enrich_contacts.py
PYTHONPATH=. python3 campaigns/contact-account-enrichment/scripts/enrich_contacts.py --input path/to/contacts.xlsx
```
Run once per input file.

## Conventions
- Requires `HUBSPOT_ACCESS_TOKEN`, `FIRMABLE_API_KEY`, `FIRMABLE_OS_API_KEY` in `.env`.
- `output/` and `input/*.csv|*.xlsx` are gitignored — never commit contact data.
- Company/Firmable lookups are cached per domain within a run to avoid repeat API calls when multiple contacts share a company.
- Open/closed deal-stage detection is inferred from stage label text containing "closed" — verify against this portal's actual pipeline labels if `Open Deal?` looks wrong.
- Contact-level `city`/`state`/`country` are only as populated as this HubSpot portal's contact records — many contacts may have no location set, which shows up as a blank `Location`.
