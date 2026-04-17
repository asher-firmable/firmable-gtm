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
│
├── knowledge/                       ← Shared knowledge base (read by all sub-agents)
│   ├── firmable-product.md          ← Company overview, product, differentiators, messaging & tone
│   ├── firmable-context.md          ← Redirect → firmable-product.md
│   ├── firmable-overview.md         ← Redirect → firmable-product.md
│   ├── icp-definition.md            ← ICP scoring rubric + qualification checklist (A/B/C/D tiers)
│   ├── icp-criteria.md              ← Redirect → icp-definition.md
│   ├── persona-definitions.md       ← 4 buyer personas with messaging angles + persona template
│   ├── persona-messaging.md         ← Redirect → persona-definitions.md
│   ├── messaging-frameworks.md      ← 6 email frameworks + persona→template routing table
│   ├── competitors.md               ← ZoomInfo, Apollo, Lusha, LinkedIn Sales Nav — displacement angles
│   ├── customer-insights.md         ← Synthesised call transcripts (Cotiss, Stripe)
│   ├── firmable-api-reference.md    ← Firmable API endpoints and wrapper methods
│   ├── exclusions.md                ← DNC and outreach exclusion rules
│   ├── enrichment-prompts.md        ← Short prompts for ICP fit, email openers, score justification
│   └── Contact-Classifier-Skill.md  ← Skill: classify contacts against ICP
│
├── scripts/                         ← Shared API wrappers (source of truth — import from here)
│   ├── firmable_api.py              ← FirmableClient — lookup_company, lookup_company_by_id, find_contacts
│   ├── hubspot_client.py            ← HubSpotClient — create_or_update_contact
│   ├── hubspot_eligibility.py       ← Pre-campaign pipeline: HubSpot eligibility + Firmable enrichment
│   ├── normalize_company_names.py   ← Strip legal suffixes, dot-TLDs, parentheticals from company_name
│   ├── enrich_persona_region.py     ← Add persona + region columns via web-fetch + Claude
│   ├── smartlead_client.py          ← SmartLeadClient — add_leads_to_campaign, create_campaign
│   ├── ai.py                        ← ask_claude, ask_claude_with_vision
│   ├── classifier.py                ← classify_contacts, classify_contact
│   └── utils.py                     ← load_csv, save_csv, ensure_dirs, timestamp, read_knowledge_file, reason_about
│
├── applications/                    ← Compatibility shims only — do not delete, do not add new code here
│   ├── firmable.py                  ← re-exports from scripts/firmable_api.py
│   ├── hubspot.py                   ← re-exports from scripts/hubspot_client.py
│   ├── smartlead.py                 ← re-exports from scripts/smartlead_client.py
│   ├── ai.py                        ← re-exports from scripts/ai.py
│   └── classifier.py               ← re-exports from scripts/classifier.py
│
├── data/                            ← Raw upstream input only (Clay CSVs, webhook payloads)
│   └── input/                       ← Source files from Clay or manual upload
│
├── campaigns/                       ← Campaign data organised by region (data only, no scripts)
│   ├── CLAUDE.md                    ← Campaign folder conventions
│   ├── anz/                         ← Australia & New Zealand campaigns
│   │   ├── CLAUDE.md                ← ANZ pipeline docs + command reference
│   │   ├── run_pipeline.py          ← Full ANZ pipeline: eligibility → size filter → normalise → persona → final
│   │   ├── ANZ_SMB_SaaS/
│   │   │   └── Software_General_Outreach/ ← ANZ SMB SaaS/Software general outreach (sales team ≤4)
│   │   └── events-outbound/         ← ANZ event/expo exhibitor outreach campaigns
│   │       ├── CLAUDE.md            ← Events outbound conventions
│   │       └── sydney-build-expo-2026/
│   │           ├── CLAUDE.md        ← Sub-agent: scrape exhibitors from Sydney Build Expo 2026
│   │           ├── scrape_exhibitors.py ← Playwright scraper → output/exhibitors.csv
│   │           └── output/          ← Scraped CSVs (gitignored)
│   ├── us/                          ← US campaigns
│   ├── sea/                         ← South-East Asia campaigns
│   └── company-checks/              ← Pre-campaign HubSpot eligibility gate (any region)
│       ├── CLAUDE.md                ← Sub-agent: filter logic, input/output conventions
│       ├── input/                   ← Drop company CSV here before running /smartlead-pre-campaign-check
│       └── output/                  ← Eligible company CSVs (gitignored)
│
├── projects/                        ← All production bots, pipelines, and internal tools
│   ├── CLAUDE.md                    ← Index of all sub-projects
│   ├── slack-bots/                  ← Slack-integrated bots deployed on Railway
│   │   ├── CLAUDE.md                ← Index of all Slack bot sub-projects
│   │   ├── event-scraper/           ← PRODUCTION: event sponsor outreach pipeline
│   │   │   ├── CLAUDE.md            ← Sub-agent: scrape → enrich → score → personalise → upload
│   │   │   ├── Event-Scraping-Skill.md ← Skill: step-by-step pipeline execution + monitoring
│   │   │   ├── output/              ← Campaign CSVs (gitignored)
│   │   │   └── scripts/             ← 0_scrape_*.py, 1_enrich.py, 2_score.py, 3_personalise.py, 4_upload.py, run_all.py, bot.py
│   │   │
│   │   └── find-contacts/           ← Ad-hoc and batch Firmable contact lookups
│   │       ├── CLAUDE.md            ← Sub-agent: contact lookup role
│   │       ├── Contact-Finding-Skill.md ← Skill: find contacts using Firmable People Search
│   │       ├── output/              ← Contact lookup results (gitignored)
│   │       └── scripts/             ← bot.py, enrich_accounts.py
│   │
│   ├── account-level-enrichment-sea/   ← Enrich accounts with regional headcount + AI notes; sync to HubSpot (SEA)
│   │   ├── CLAUDE.md                    ← Sub-agent: enrichment + HubSpot sync pipeline
│   │   ├── output/                      ← Enriched CSVs (gitignored)
│   │   └── scripts/                     ← enrich_accounts.py, hubspot_check.py, hubspot_sync.py
│   │
│   ├── signal-contact-activation/      ← ICP classify contacts by buying signal type
│   │   ├── CLAUDE.md                    ← Index of signal sub-folders
│   │   └── contacts-new-role/           ← Signal: contacts who started a new role (past 90 days)
│   │       ├── CLAUDE.md                ← Sub-agent: column mapping, BDM rule, classifier usage
│   │       ├── output/                  ← Classified CSVs (gitignored)
│   │       └── scripts/                 ← classify_new_roles.py
│   │
│   └── sea-company-upload/             ← Pre-upload HubSpot audit for company lists
│       ├── CLAUDE.md                    ← Sub-agent: drop CSV in input/, run check, read terminal summary
│       ├── input/                       ← Drop company CSV here before running
│       └── output/                      ← Reserved for future CSV export (gitignored)
│
└── .claude/                         ← Claude Code skills and slash commands
    ├── skills/                      ← Reusable AI capabilities (auto-triggered by task type)
    │   ├── account-qualification/   ← ICP scoring against icp-definition.md
    │   ├── contact-validation/      ← Seniority + DNC filter
    │   ├── email-copywriting/       ← Copy generation (persona-aware, hard rules)
    │   ├── signal-research/         ← Buying signal research
    │   ├── firmable-api/            ← FirmableClient patterns
    │   ├── smartlead-push/          ← SmartLead campaign upload (confirm before activating)
    │   ├── hubspot-sync/            ← CRM create/update (dedup on email/domain)
    │   └── n8n-export/              ← Convert pipelines to n8n JSON
    └── commands/                    ← Slash commands
        ├── new-campaign.md                    ← /new-campaign — campaign setup wizard
        ├── qualify-list.md                    ← /qualify-list — run classifier on CSV
        ├── generate-copy.md                   ← /generate-copy — generate email copy
        └── smartlead-pre-campaign-check.md    ← /smartlead-pre-campaign-check — company eligibility gate
```

---

## Routing Table

| Task | Go to |
|---|---|
| SmartLead pre-campaign eligibility gate (any region — filter trial/comms/tasks) | `campaigns/company-checks/` + `/smartlead-pre-campaign-check` |
| Check company list against HubSpot before upload (SEA or any region) | `projects/sea-company-upload/` |
| Enrich accounts with regional headcount + AI notes + HubSpot sync (SEA) | `projects/account-level-enrichment-sea/` |
| Classify new-role contacts against ICP (job-change signal activation) | `projects/signal-contact-activation/` |
| Scrape event sponsors and run outreach pipeline | `projects/slack-bots/event-scraper/` |
| Find contacts at specific companies | `projects/slack-bots/find-contacts/` |
| Manage campaign data | `campaigns/` |
| ANZ SMB SaaS/Software general outreach (sales team ≤4) | `campaigns/anz/ANZ_SMB_SaaS/Software_General_Outreach/` |
| Scrape ANZ event/expo exhibitor lists | `campaigns/anz/events-outbound/` |
| Sydney Build Expo 2026 exhibitor scrape | `campaigns/anz/events-outbound/sydney-build-expo-2026/` |
| Run full ANZ pre-outreach pipeline (any ANZ campaign) | `campaigns/anz/run_pipeline.py` |
| Run pre-campaign eligibility check + Firmable enrichment | `scripts/hubspot_eligibility.py` |
| Normalise company names in a campaign CSV | `scripts/normalize_company_names.py` |
| Add persona + region to a campaign CSV | `scripts/enrich_persona_region.py` |
| Look up Firmable API endpoints | `knowledge/firmable-api-reference.md` |
| Check ICP scoring logic | `knowledge/icp-definition.md` |
| Check exclusion/DNC rules | `knowledge/exclusions.md` |
| Look up persona messaging | `knowledge/persona-definitions.md` |
| Firmable product context + competitive positioning | `knowledge/firmable-product.md` |
| Email framework selection | `knowledge/messaging-frameworks.md` |

---

## Conventions
- **API keys**: Always load from `.env` using `python-dotenv`. Never hardcode credentials.
- **HTTP**: Use the `requests` library for raw API calls; `hubspot-api-client` for HubSpot.
- **Error handling**: Log errors with context (which record failed, why). Never swallow exceptions silently.
- **Imports**: Always import from `scripts/`. Never write duplicate API code. `applications/` is shims only.
- **Naming**: Python files use `snake_case`. One workflow per file.
- **Output**: Each workflow writes to its own `output/` folder (gitignored). Never write to other workflow folders.
- **Data flow**: Raw Clay/upstream files go to `data/input/`. Processed outputs go to the relevant workflow's `output/`.
- **Clay**: Upstream source only — ingest via CSV in `data/input/` or webhook payloads. No direct Clay API calls.

## Rules
1. **Always check knowledge/ before writing copy or scoring accounts** — icp-definition.md, persona-definitions.md, and messaging-frameworks.md are the source of truth.
2. **Ask before running any script that writes to HubSpot or SmartLead** — confirm lead count, campaign name, and sender before activating.
2a. **HubSpot create safety check** — before creating a new company record, verify the domain is consistent with the company name (domain root should contain or match a word from the company name). If inconsistent, flag to the user and skip creation — never auto-create records with mismatched data. List all flagged cases in the summary output.
3. **Never skip the exclusions check** — always apply `knowledge/exclusions.md` before scoring or uploading any list.
4. **Use skills when available** — check `.claude/skills/` before writing enrichment or scoring logic from scratch.
5. **Update this file when new folders are added** — any new top-level folder needs an entry in the Folder Structure tree and Routing Table.
6. **Git commit prompting** — ask before committing. Never auto-commit without explicit instruction.

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
from scripts.firmable_api import FirmableClient
client = FirmableClient()
company = client.lookup_company(domain="example.com.au")
```

### Call HubSpot
```python
from scripts.hubspot_client import HubSpotClient
hs = HubSpotClient()
contact = hs.create_or_update_contact(email="name@example.com", properties={...})
```

### Call SmartLead
```python
from scripts.smartlead_client import SmartLeadClient
sl = SmartLeadClient()
sl.add_leads_to_campaign(campaign_id="123", leads=[...])
```

### AI enrichment step
```python
from scripts.ai import ask_claude
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
- Run scripts with `PYTHONPATH=.` from the repo root so `scripts/` resolves correctly
- Use `pip3` (not `pip`) for all package installs
- SmartLead API key: `SMARTLEAD_API_KEY` in `.env`
- n8n webhook URL: `N8N_WEBHOOK_URL` in `.env`
- `applications/` is kept as compatibility shims — do not add new code there
