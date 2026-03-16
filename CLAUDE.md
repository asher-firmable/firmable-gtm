## On Session Start
Always read the following files before starting any work:
- `FIRMABLE_CONTEXT.md` — company context, ICP, messaging, and role
- `prompts/email_templates.md` — outreach template frameworks and applicability notes
- `research/customer_insights.md` — synthesised themes from real customer calls

Do not proceed with any task until these files have been read.

---

# GTM Engineering — Claude Context

## Role
GTM (Go-to-Market) engineer building sales and marketing automations. Clay handles upstream enrichment and passes data in — Claude Code takes it from there to process, score, sync to CRM, and trigger outreach.

## Stack
- **Firmable** — Australian B2B data platform for company and contact enrichment
- **HubSpot** — CRM for contacts, companies, deals, and sequences
- **SmartLead** — Cold email outreach platform (sequences, campaigns, inbox management)
- **Python** — Default scripting language for all automations
- **Claude API (Anthropic)** — AI enrichment steps (summaries, ICP scoring, personalisation)
- **Clay** — Upstream data source; passes enriched CSVs or webhooks into this workflow (no direct API calls to Clay needed)
- **n8n** — Used where appropriate for orchestration; Claude Code can generate payloads for n8n webhooks

## Project Structure
```
workflows/
  crm_sync/        # HubSpot sync (create/update contacts, companies, deals)
  lead_scoring/    # ICP fit scoring, intent signals
  outreach/        # SmartLead campaign creation, lead upload, personalised copy

utils/
  firmable.py      # Firmable API wrapper — always import from here
  hubspot.py       # HubSpot API wrapper — always import from here
  smartlead.py     # SmartLead API wrapper — always import from here
  ai.py            # Claude/AI helper for enrichment prompts

prompts/           # Reusable prompt templates (markdown files)

data/
  input/           # CSVs from Clay or other upstream sources
  output/          # Results (gitignored, never commit)
```

## Conventions
- **API keys**: Always load from `.env` using `python-dotenv`. Never hardcode credentials.
- **HTTP**: Use the `requests` library for raw API calls; use `hubspot-api-client` for HubSpot where possible.
- **Error handling**: Log errors with context (which record failed, why). Don't silently swallow exceptions.
- **Logging**: Use `print()` for simple scripts; use Python `logging` module for longer-running jobs.
- **Data flow**: Scripts read from `data/input/`, write results to `data/output/`.
- **Naming**: Script files use `snake_case`. One workflow per file. Name by action, e.g. `score_leads.py`, `sync_contacts_to_hubspot.py`, `upload_to_smartlead.py`.
- **Imports**: Shared utils live in `utils/`. Always reuse existing wrappers before writing new API code.

## Common Patterns

### Load environment variables
```python
from dotenv import load_dotenv
import os
load_dotenv()
API_KEY = os.getenv("FIRMABLE_API_KEY")
```

### Call Firmable
```python
from utils.firmable import FirmableClient
client = FirmableClient()
company = client.lookup_company(domain="example.com.au")
```

### Call HubSpot
```python
from utils.hubspot import HubSpotClient
hs = HubSpotClient()
contact = hs.create_or_update_contact(email="name@example.com", properties={...})
```

### Call SmartLead
```python
from utils.smartlead import SmartLeadClient
sl = SmartLeadClient()
sl.add_leads_to_campaign(campaign_id="123", leads=[...])
```

### AI enrichment step
```python
from utils.ai import ask_claude
summary = ask_claude(prompt="Summarise this company for a sales rep", context=company_data)
```

## Workflow Types
- **CRM Sync**: Take enriched data (from Clay CSVs or Firmable) → create or update records in HubSpot
- **Lead Scoring**: Apply ICP criteria (industry, headcount, tech stack) → score and rank leads
- **Outreach**: Generate personalised email copy using Claude → upload leads to SmartLead campaigns

## Notes
- Update this file as new patterns and tools are established
- Clay is an upstream source only — ingest its output via CSV in `data/input/` or webhook payloads
- SmartLead API key is stored as `SMARTLEAD_API_KEY` in `.env`
