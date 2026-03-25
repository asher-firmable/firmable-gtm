# Event Scraping Bot — Sub-Agent

## Role
I own the end-to-end event sponsor outreach pipeline: scrape → enrich → find contacts → score → personalise → upload to SmartLead.

When working in this folder, read this file first. Do not touch scripts without understanding the sequencing below.

---

## Pipeline Overview

Each campaign runs against a specific event. Steps execute in order — each step's output feeds the next.

```
Step 0: Scrape sponsors from event website
        Output: sponsors_raw.csv (company_name, domain, linkedin_url, firmable_company_id)

Step 1a: Find contacts at each company (Firmable People Search)
         Output: contacts.csv (contact details for sales-relevant people)

Step 1b: Enrich companies with Firmable data
         Output: enriched.csv (industry, headcount, country, description)

Step 2a: Score leads against ICP criteria
         Output: scored.csv (icp_score, tier, qualified flag)

Step 2b: Sync to HubSpot (optional)
         Output: HubSpot records updated

Step 3: Generate personalised email openers using Claude
        Output: personalised.csv (email_opener column added)

Step 4: Upload leads to SmartLead campaign
        Output: leads live in SmartLead campaign
```

---

## Scripts (in order)

| Script | Purpose |
|---|---|
| `scripts/0_scrape_exhibitors.py` | Primary scraper — multi-layer (Playwright → Vision → HTML) |
| `scripts/0_scrape_sponsors.py` | Alt scraper (simpler sites) |
| `scripts/1_find_contacts.py` | Find sales contacts via Firmable People Search |
| `scripts/1_enrich.py` | Pull full company enrichment from Firmable |
| `scripts/2_score.py` | ICP fit scoring |
| `scripts/2_sync_to_hubspot.py` | Sync contacts/companies to HubSpot |
| `scripts/3_personalise.py` | Claude-powered personalised email openers |
| `scripts/4_upload_to_smartlead.py` | Upload leads to SmartLead campaign |
| `scripts/run_all.py` | Run steps 0–4 in sequence |
| `scripts/bot.py` | Interactive CLI for managing campaigns |

---

## How to Run a Campaign

### 1. Create a campaign config
Create a `config.json` for the event — see `_playbook.md` for the field reference.

### 2. Run the scraper
```bash
PYTHONPATH=. python3 projects/slack-bots/event-scraper/scripts/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "projects/slack-bots/event-scraper/output/EVENT_NAME_raw.csv"
```

### 3. Run subsequent steps
```bash
PYTHONPATH=. python3 projects/slack-bots/event-scraper/scripts/1_find_contacts.py \
  --input "projects/slack-bots/event-scraper/output/EVENT_NAME_raw.csv" \
  --output "projects/slack-bots/event-scraper/output/EVENT_NAME_contacts.csv"
```

### 4. Or run all at once
```bash
PYTHONPATH=. python3 projects/slack-bots/event-scraper/scripts/run_all.py --project [event_name]
```

---

## Output Location
All CSVs write to `projects/slack-bots/event-scraper/output/` (gitignored).

Naming convention: `EVENT_NAME_[step].csv`
- `EVENT_NAME_raw.csv`
- `EVENT_NAME_contacts.csv`
- `EVENT_NAME_enriched.csv`
- `EVENT_NAME_scored.csv`
- `EVENT_NAME_personalised.csv`

---

## API Wrappers
All wrappers live in `scripts/`:
- `scripts/firmable_api.py` — `FirmableClient` (lookup_company, search_by_linkedin, find_contacts)
- `scripts/smartlead_client.py` — `SmartLeadClient` (add_leads_to_campaign)
- `scripts/hubspot_client.py` — `HubSpotClient` (create_or_update_contact)
- `scripts/ai.py` — `ask_claude`, `ask_claude_with_vision`

Import pattern:
```python
from scripts.firmable_api import FirmableClient
```

---

## Key References
- `knowledge/icp-definition.md` — scoring rubric (sales team size, industry, competitive tech)
- `knowledge/firmable-product.md` — ICP definition, value prop
- `knowledge/firmable-api-reference.md` — Firmable API endpoints and wrapper methods
- `knowledge/exclusions.md` — DNC and exclusion rules (always apply before scoring)

---

## Skills Available

### Event-Scraping-Skill.md
Full step-by-step guide for running the scraper, handling edge cases, and chaining to downstream steps.

---

## Sequencing Rules
- Never skip a step — each depends on the previous output
- Always apply `knowledge/exclusions.md` rules before scoring or uploading
- If a step fails: check which records failed and why before re-running
- Never auto-fix scripts — report the error and wait for approval

---

## n8n Integration
Add `--send-to-n8n` to the scraper to POST all rows to the webhook defined in `N8N_WEBHOOK_URL` in `.env`.

Use the production webhook URL (`/webhook/...`), not the test URL (`/webhook-test/...`).
