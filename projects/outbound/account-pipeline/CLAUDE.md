# Account Pipeline — Sub-Agent

## Purpose
End-to-end account-based outbound pipeline: takes an Excel of accounts with Firmable IDs, filters junk, finds decision-maker contacts, researches each company's own target market, generates personalised 2-email PQS sequences, and auto-creates a SmartLead campaign with those leads uploaded.

## What Goes In
- Excel or CSV with columns: `account_name`, `firmable_company_id` (plus any other columns, which are preserved)
- Place input files in `data/input/`

## What Goes Out
- `output/filtered_accounts.csv` — accounts that passed the filter
- `output/excluded_accounts.csv` — removed accounts with `filter_reason`
- `output/contacts.csv` — decision-maker contacts (Manager+ with work email)
- `output/contacts_researched.csv` — contacts enriched with `target_market` and `target_titles`
- `output/emails.csv` — contacts with generated `subject_1`, `body_1`, `subject_2`, `body_2`
- `output/upload_results.csv` — SmartLead upload status per lead

## Scripts

| Script | Purpose |
|---|---|
| `scripts/0_filter.py` | Claude-based filter: removes lead-gen companies and suspect/non-English names |
| `scripts/1_find_contacts.py` | Firmable two-pass search (GM + Sales dept, Manager+ seniority, email required) |
| `scripts/2_research.py` | Fetch company website → Claude infers target market + titles they prospect for |
| `scripts/3_generate_emails.py` | Claude generates 2-email PQS sequence per contact (persona-aware) |
| `scripts/4_upload.py` | Creates SmartLead campaign + 2-step sequence + uploads all leads |
| `scripts/run_all.py` | Orchestrator — runs steps 0–4 in order |

## Usage

### Full pipeline
```bash
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx
```

### Run steps individually
```bash
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/0_filter.py --input data/input/accounts.xlsx
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/1_find_contacts.py
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/2_research.py
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/3_generate_emails.py
PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/4_upload.py
```

### Useful flags
- `--dry-run` — preview SmartLead upload without sending (pass to run_all.py or 4_upload.py)
- `--skip-upload` — stop after generating emails.csv for manual review
- `--campaign-id <id>` — use an existing SmartLead campaign (skip auto-creation)

## Config
Edit `config.json` before first run:
```json
{
  "sender": {
    "from_name": "Your Name",
    "from_email": "you@firmable.com",
    "reply_to": "you@firmable.com"
  },
  "sequence": {
    "step_2_delay_days": 3
  }
}
```

## Conventions
- All output goes to `output/` (gitignored)
- Run all scripts from repo root with `PYTHONPATH=.`
- Always load API keys from `.env` via `python-dotenv`
- Import API clients from `scripts/` — never write duplicate API code
- SmartLead campaign creation may be IP-restricted; use `--campaign-id` if 403 errors occur

## Key References
- `knowledge/icp-definition.md` — seniority rules for contact filtering
- `knowledge/persona-definitions.md` — pain angles by persona
- `outbound/email-templates-examples.md` — PQS and Competitor Analysis templates
- `outbound/customer-stories-and-use-cases.md` — proof points used in email generation
- `scripts/firmable_api.py` — `find_contacts()`, `lookup_company_by_id()`
- `scripts/smartlead_client.py` — `create_campaign()`, `add_email_sequence()`, `add_leads_to_campaign()`
