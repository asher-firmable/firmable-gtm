# Skill: Replicate to Production

## What This Skill Does
Compares a staged script (in `staging/`) against its production counterpart, shows the diff, and applies the change to production only after explicit approval.

---

## When to Use
- You've tested a change in `staging/` and it works
- You want to update a production script (e.g. `event-scraping-bot/scripts/0_scrape_exhibitors.py`) with the staged version
- You want to promote a fun project from `fun-projects/` into a production folder

---

## Logical Steps

1. **Identify the files to compare:**
   - Staging script (e.g. `staging/event-scraping-bot-staging/scripts/Scrape.py`)
   - Production counterpart (e.g. `event-scraping-bot/scripts/0_scrape_exhibitors.py`)

2. **Generate a diff:**
   ```bash
   diff staging/event-scraping-bot-staging/scripts/Scrape.py event-scraping-bot/scripts/0_scrape_exhibitors.py
   ```

3. **Present the diff** to the user:
   - Lines added (green/+)
   - Lines removed (red/-)
   - Summarise the change in plain English

4. **Ask for explicit approval:** "Do you want to apply these changes to production?"

5. **Apply only if approved:**
   ```bash
   cp staging/event-scraping-bot-staging/scripts/Scrape.py event-scraping-bot/scripts/0_scrape_exhibitors.py
   ```

6. **Report completion** — confirm which file was updated

---

## Staging → Production Mapping

| Staging file | Production file |
|---|---|
| `staging/event-scraping-bot-staging/scripts/Scrape.py` | `event-scraping-bot/scripts/0_scrape_exhibitors.py` |
| `staging/event-scraping-bot-staging/scripts/Enrich-Company.py` | `event-scraping-bot/scripts/1_enrich.py` |
| `fun-projects/[name]/[file]` | Depends — ask which production folder to target |

---

## Safety Rules
- Never overwrite production without showing the diff first
- Never apply changes without explicit user approval ("yes", "apply it", "go ahead")
- If the staging file doesn't have a clear production counterpart, ask the user before proceeding
- After applying: verify the production file was updated correctly

---

## How to Use This Skill
Tell Claude Code: *"Run the replicate-to-prod skill for [staging file]"*
Claude will read this file, generate the diff, and wait for your approval.
