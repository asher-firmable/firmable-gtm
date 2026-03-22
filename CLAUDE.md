# GTM Engineering — Big Brother

## Who I Am
GTM (Go-to-Market) engineer at Firmable. I build outbound systems and internal revenue workflows. Clay handles upstream enrichment and passes data in — Claude Code takes it from there to process, score, sync to CRM, and trigger outreach.

## Stack
- **Firmable** — Australian B2B data platform for company and contact enrichment (APAC focus)
- **HubSpot** — CRM for contacts, companies, deals, and sequences
- **SmartLead** — Cold email outreach platform (sequences, campaigns, inbox management)
- **Python** — Default scripting language for all automations
- **Claude API (Anthropic)** — AI enrichment steps (summaries, ICP scoring, personalisation)
- **Clay** — Upstream data source; passes enriched CSVs or webhooks (no direct API calls to Clay)
- **n8n** — Orchestration; Claude Code can generate payloads for n8n webhooks

---

## Folder Structure & Sub-Agents

Each domain folder has its own `CLAUDE.md` sub-agent. Read the relevant sub-agent's CLAUDE.md when working on a specific task.

```
firmable-gtm-engineering/
├── CLAUDE.md                        ← You are here (Big Brother)
├── Update-Claude-Agent.md           ← Meta-skill: update this file when new folders/files are created
│
├── knowledge/                       ← Shared knowledge base (read by all sub-agents)
│   ├── firmable-context.md          ← Company, ICP, messaging, tone
│   ├── customer-insights.md         ← Synthesised call transcripts (Cotiss, Stripe)
│   ├── firmable-overview.md         ← Competitive analysis and product positioning
│   ├── firmable-api-reference.md    ← Firmable API endpoints and wrapper methods
│   ├── icp-criteria.md              ← ICP scoring rubric (sales team size, industry, tech)
│   ├── exclusions.md                ← DNC and outreach exclusion rules
│   ├── persona-messaging.md         ← 4 buyer personas with messaging angles
│   └── enrichment-prompts.md        ← Short prompts for ICP fit, email openers, score justification
│
├── applications/                    ← Platform API wrappers (always import from here)
│   ├── firmable.py                  ← FirmableClient — lookup_company, search_by_linkedin, find_contacts
│   ├── hubspot.py                   ← HubSpotClient — create_or_update_contact
│   ├── smartlead.py                 ← SmartLeadClient — add_leads_to_campaign
│   └── ai.py                        ← ask_claude, ask_claude_with_vision
│
├── data/                            ← Raw upstream input only (Clay CSVs, webhook payloads)
│   └── input/                       ← Source files from Clay or manual upload
│
├── event-scraping-bot/              ← PRODUCTION: event sponsor outreach pipeline
│   ├── CLAUDE.md                    ← Sub-agent: owns scrape → enrich → score → personalise → upload
│   ├── Event-Scraping-Skill.md      ← Skill: step-by-step pipeline execution + monitoring
│   ├── output/                      ← Campaign CSVs (gitignored)
│   └── scripts/                     ← 0_scrape_*.py, 1_enrich.py, 2_score.py, 3_personalise.py, 4_upload.py, run_all.py, bot.py
│
├── find-contacts/                   ← Ad-hoc and batch Firmable contact lookups
│   ├── CLAUDE.md                    ← Sub-agent: contact lookup role
│   ├── Contact-Finding-Skill.md     ← Skill: find contacts using Firmable People Search
│   ├── output/                      ← Contact lookup results (gitignored)
│   └── bot.py                       ← Interactive CLI / Slack bot
│
├── n8n/                             ← Create and edit n8n workflows via REST API
│   ├── CLAUDE.md                    ← Sub-agent: n8n workflow management
│   └── N8n-Changes-Skill.md         ← Skill: list, create, edit workflows
│
├── outbound/                        ← Email copy generation and SmartLead campaign upload
│   ├── CLAUDE.md                    ← Sub-agent: reads templates + customer stories before any email task
│   ├── email-templates-examples.md  ← 7 cold email templates (PVP, PQS, Competitor Analysis, etc.)
│   ├── customer-stories-and-use-cases.md  ← Cotiss, Stripe, internal proof points for copy
│   ├── raw-transcripts/             ← Raw call recordings for outbound context
│   └── email-writing/
│       └── Email-Writing-Skill.md   ← Skill: persona-aware email generation
│
├── call-analysis/                   ← Call transcript processing and knowledge base maintenance
│   ├── CLAUDE.md                    ← Sub-agent: goals, folder structure, approval process
│   ├── call-analysis-existing-customer/
│   │   └── Skill-Agent-For-Existing-Customer.md  ← Satisfaction, product gaps, expansion signals
│   └── call-analysis-prospect/
│       └── Skill-Agent-For-Prospect.md           ← Pain points, objections, qualification signals
│
├── staging/                         ← Test environment — changes here don't affect production
│   ├── CLAUDE.md                    ← Sub-agent: staging rules and purpose
│   ├── Replicate-to-prod-skill.md   ← Skill: diff + promote staging → production (approval required)
│   └── event-scraping-bot-staging/  ← Staging copy of event scraping pipeline
│       ├── CLAUDE.md
│       ├── Event-Scraping-Skill.md
│       ├── Scrape.py                ← Copy of 0_scrape_exhibitors.py (modify freely)
│       └── Enrich-Company.py        ← Copy of 1_enrich.py (modify freely)
│
└── fun-projects/                    ← Personal experiments and reverse-engineering
    ├── CLAUDE.md                    ← Sub-agent: experimentation sandbox
    └── Write-To-Relevant-Folder-Skill.md  ← Skill: deploy a fun project to the right production folder
```

---

## Routing Table

| Task | Go to |
|---|---|
| Scrape event sponsors and run outreach pipeline | `event-scraping-bot/` |
| Find contacts at specific companies | `find-contacts/` |
| Create or edit n8n workflows | `n8n/` |
| Write or improve cold email copy | `outbound/` |
| Process a call transcript | `call-analysis/` |
| Test a change before pushing to production | `staging/` |
| Build something new or experimental | `fun-projects/` |
| Look up Firmable API endpoints | `knowledge/firmable-api-reference.md` |
| Check ICP scoring logic | `knowledge/icp-criteria.md` |
| Check exclusion/DNC rules | `knowledge/exclusions.md` |
| Look up persona messaging | `knowledge/persona-messaging.md` |

---

## Conventions
- **API keys**: Always load from `.env` using `python-dotenv`. Never hardcode credentials.
- **HTTP**: Use the `requests` library for raw API calls; `hubspot-api-client` for HubSpot.
- **Error handling**: Log errors with context (which record failed, why). Never swallow exceptions silently.
- **Imports**: Always import from `applications/`. Never write duplicate API code.
- **Naming**: Python files use `snake_case`. One workflow per file.
- **Output**: Each workflow writes to its own `output/` folder (gitignored). Never write to other workflow folders.
- **Data flow**: Raw Clay/upstream files go to `data/input/`. Processed outputs go to the relevant workflow's `output/`.
- **Clay**: Upstream source only — ingest via CSV in `data/input/` or webhook payloads. No direct Clay API calls.

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
from applications.firmable import FirmableClient
client = FirmableClient()
company = client.lookup_company(domain="example.com.au")
```

### Call HubSpot
```python
from applications.hubspot import HubSpotClient
hs = HubSpotClient()
contact = hs.create_or_update_contact(email="name@example.com", properties={...})
```

### Call SmartLead
```python
from applications.smartlead import SmartLeadClient
sl = SmartLeadClient()
sl.add_leads_to_campaign(campaign_id="123", leads=[...])
```

### AI enrichment step
```python
from applications.ai import ask_claude
summary = ask_claude(prompt="Summarise this company for a sales rep", context=company_data)
```

---

## New Folder Convention
Every new top-level folder must follow this checklist:
1. **CLAUDE.md required** — create a `CLAUDE.md` inside the folder covering: purpose, what goes in/out, scripts or tools used, and folder-specific conventions.
2. **Ask first if no context** — if you are creating a folder and the user has not explained what it is for, stop and ask: "What is this folder for and what should go in it?"
3. **Update root CLAUDE.md** — add the new folder to the Folder Structure tree and Routing Table above.
4. **Standard template for a new folder's CLAUDE.md:**
   - `## Purpose` — one sentence on what this folder does
   - `## What goes in` — inputs / sources
   - `## What goes out` — outputs / destinations
   - `## Scripts / tools` — list scripts and their roles (if any)
   - `## Conventions` — any folder-specific rules

---

## Notes
- Run scripts with `PYTHONPATH=.` from the repo root so `applications/` resolves correctly
- When a new folder or file is created, run `Update-Claude-Agent.md` to keep this file current
- SmartLead API key: `SMARTLEAD_API_KEY` in `.env`
- n8n webhook URL: `N8N_WEBHOOK_URL` in `.env`
