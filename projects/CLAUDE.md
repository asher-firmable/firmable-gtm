# Projects — Index

All production bots, pipelines, and internal tools live here. Each sub-folder has its own `CLAUDE.md` sub-agent.

## Projects

| Folder | Purpose | Run Command |
|---|---|---|
| `account-level-enrichment-sea/` | Enrich Firmable accounts with regional headcount + AI notes; sync ICP Match (SEA) and owner to HubSpot | `PYTHONPATH=. python3 projects/account-level-enrichment-sea/scripts/enrich_accounts.py --input data/input/<file>.csv` |
| `signal-contact-activation/contacts-new-role/` | Classify new-role contacts (Firmable export) against ICP definition; surfaces managerial-level buyers for activation | `PYTHONPATH=. python3 projects/signal-contact-activation/contacts-new-role/scripts/classify_new_roles.py --input data/input/<file>.csv` |
| `slack-bots/event-scraper/` | Event sponsor outreach pipeline (scrape → enrich → score → personalise → upload) | `PYTHONPATH=. python3 projects/slack-bots/event-scraper/scripts/bot.py` |
| `slack-bots/find-contacts/` | Firmable contact lookups — Slack bot + batch enrichment | `PYTHONPATH=. python3 projects/slack-bots/find-contacts/scripts/bot.py` |
| `outbound/` | Email copy generation + SmartLead campaign upload | `PYTHONPATH=. python3 projects/outbound/account-pipeline/scripts/run_all.py --input data/input/accounts.xlsx` |
| `call-analysis/` | Call transcript processing and knowledge base maintenance | See `call-analysis/CLAUDE.md` |
| `n8n/` | Create and edit n8n workflows via REST API | See `n8n/CLAUDE.md` |
| `staging/` | Test environment — changes here don't affect production | See `staging/CLAUDE.md` |
| `fun-projects/` | Personal experiments and reverse-engineering sandbox | See `fun-projects/CLAUDE.md` |

## Conventions

- All scripts run with `PYTHONPATH=.` from the repo root
- Import API clients from `scripts/` (e.g. `from scripts.firmable_api import FirmableClient`)
- Each project writes outputs to its own `output/` folder (gitignored)
- Campaign data lives in `campaigns/`, not here
