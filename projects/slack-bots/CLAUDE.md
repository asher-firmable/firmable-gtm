# Slack Bots

Slack-integrated bots deployed on Railway. Each sub-folder is a self-contained project with its own scripts and output folder.

## Sub-projects

| Folder | Purpose | Railway Project |
|---|---|---|
| `event-scraper/` | End-to-end event sponsor outreach pipeline (scrape → enrich → score → personalise → upload) | event-scraping-bot |
| `find-contacts/` | Ad-hoc and batch Firmable contact lookups | find-contacts |

## Conventions
- Start commands are documented in each bot's `scripts/bot.py` docstring
- Railway config lives in the Railway dashboard — no `railway.toml` in this repo
- Any time a folder or entry point is renamed, update the Railway start command manually: **Settings > Deploy > Start Command**
- All scripts run with `PYTHONPATH=.` from the repo root
- Each bot writes outputs to its own `output/` folder (gitignored)
