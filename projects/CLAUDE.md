# Projects — Index

All production bots, pipelines, and internal tools live here. Each sub-folder has its own `CLAUDE.md` sub-agent.

## Projects

| Folder | Purpose | Run Command |
|---|---|---|
| `event-scraper/` | Event sponsor outreach pipeline (scrape → enrich → score → personalise → upload) | `PYTHONPATH=. python3 projects/event-scraper/scripts/bot.py` |
| `find-contacts/` | Firmable contact lookups — Slack bot + batch enrichment | `PYTHONPATH=. python3 projects/find-contacts/scripts/bot.py` |
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
