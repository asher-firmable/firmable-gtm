# Account Enrichment Skill

## Purpose
Enrich a company/account list with HubSpot account intel and/or Firmable ANZ sales team sizes.

## When to use which mode

**Sales team size only** — use when the user asks for headcount, sales team size, or Firmable enrichment with no mention of HubSpot. Only return Firmable columns. Script: `enrich_sales_team_size.py` or `enrich_us_au_nz_sales.py`.

**Full account enrichment** — use when the user asks for HubSpot data (owner, deal status, paying customer, last contacted) OR asks for "account check" / "account intel". Return all columns below. Script: `enrich_account_check.py` or `enrich_hubspot_refresh.py`.

---

## Standard Output Columns

### Sales team size only (Firmable)
| Column | Source |
|---|---|
| `Firmable ID` | Firmable company lookup by domain |
| `AU Sales Team Size` | Firmable OS Search API |
| `NZ Sales Team Size` | Firmable OS Search API |
| `Total ANZ Sales Team Size` | Computed: AU + NZ |

### Full account enrichment (HubSpot + Firmable)
All four Firmable columns above, plus:

### HubSpot
| Column | Source | Notes |
|---|---|---|
| `Exists in HubSpot?` | HubSpot company search by domain | Yes / No |
| `Paying Customer?` | `lifecyclestage` on HubSpot company | Yes if `lifecyclestage = "customer"`, No otherwise |
| `Open Deal?` | Associated deals on HubSpot company | Yes if at least one open (non-closed) deal exists |
| `HubSpot Deal Stage` | Deal `dealstage` property | Only populated when Open Deal? = Yes; blank otherwise |
| `HubSpot Account Owner` | `hubspot_owner_id` → owner name lookup | Blank if unowned |
| `HubSpot Engagement Status` | `outreach_engagement_status` property on company | Raw value from HubSpot |
| `Last Contacted` | `notes_last_contacted` on **associated contacts** (not the company record) | Steps: fetch associated contact IDs for the company → batch-read `notes_last_contacted` → take the most recent. HubSpot returns ISO 8601 strings for this property (e.g. `2026-07-08T03:33:50Z`). Output format: D Mon YYYY. Blank if no outreach has been logged. Reflects real outreach only (email/call/meeting) — HubSpot does not update `notes_last_contacted` for tasks or notes. |
| `HubSpot Link` | Constructed from portal ID + company ID | Format: `https://app.hubspot.com/contacts/{portalId}/company/{companyId}`. Blank for companies not in HubSpot. |

### Firmable
| Column | Source | Notes |
|---|---|---|
| `Firmable ID` | Firmable company lookup by domain | Resolved from domain if not already in file |
| `AU Sales Team Size` | Firmable OS Search API | 0 if company found but no AU sales team |
| `NZ Sales Team Size` | Firmable OS Search API | 0 if company found but no NZ sales team |
| `Total ANZ Sales Team Size` | Computed: AU + NZ | 0 if both are 0 |

## Scripts
- **`campaigns/quick-sales-team-size-check/scripts/enrich_account_check.py`** — full combined run: HubSpot + Firmable from scratch on any company CSV/Excel. Note: produces `hs_*` prefixed column names and does not yet include `Paying Customer?` or contact-level `Last Contacted`. Follow with a refresh pass to get the full standard column set.
- **`campaigns/quick-sales-team-size-check/scripts/enrich_hubspot_refresh.py`** — HubSpot refresh on an already-enriched file. Adds `Paying Customer?`, `Open Deal?`, `Last Contacted` (contact-level); removes `HubSpot Deal Status?`. Skips companies not in HubSpot. Use this after `enrich_account_check.py`, or on any existing file that needs the standard columns.

## Recommended workflow for a new file
1. Run `enrich_account_check.py` — gets HubSpot owner/deal/engagement + Firmable sales sizes
2. Run `enrich_hubspot_refresh.py` on the output — upgrades to full standard column set (adds Paying Customer?, Open Deal?, contact-level Last Contacted)

## Input Requirements
Drop file into `campaigns/quick-sales-team-size-check/input/`. The file needs at least one of:
- `domain` / `website` / `domain_name` — company domain (recommended)
- `firmable_id` / `firmable_company_url` / `firmable_company_link` — Firmable identifier
- `company_name` / `name` — last resort (cannot resolve Firmable without domain/ID)

## How to Run

### Full enrichment (new file, no prior HubSpot data)
```bash
PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_account_check.py
# or with explicit path:
PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_account_check.py --input path/to/file.csv
```

### HubSpot refresh only (already-enriched file, update HubSpot columns)
```bash
PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_hubspot_refresh.py
# or with explicit path:
PYTHONPATH=. python3 campaigns/quick-sales-team-size-check/scripts/enrich_hubspot_refresh.py --input path/to/file.xls
```

## Performance notes
- HubSpot pass is sequential (respects rate limits + domain cache)
- Firmable pass is parallel (5 workers)
- Companies marked `Exists in HubSpot? = No` are skipped in refresh mode (saves ~API calls for the majority not in HubSpot)
- `Last Contacted` requires two API calls per unique company (get associated contacts → batch-read their `notes_last_contacted`)
- Both scripts are idempotent: re-running on an already-enriched file drops and rewrites the output columns

## Output
Written to `campaigns/quick-sales-team-size-check/output/<stem>_account_check.csv` or `<stem>_refreshed.csv`.
