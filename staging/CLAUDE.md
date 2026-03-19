# Staging — Sub-Agent

## Role
I am the staging environment. Everything here is for testing and experimentation before changes go to production. Nothing in this folder affects live workflows.

---

## Rules
- Changes here do NOT affect production (e.g. `event-scraping-bot/`, `find-contacts/`)
- When a staged change is ready for production, use `Replicate-to-prod-skill.md`
- Scripts here start as copies of production scripts — modify freely
- Always confirm intent before promoting staging changes to prod

---

## What Lives Here

| Folder / File | Purpose |
|---|---|
| `Replicate-to-prod-skill.md` | Skill for promoting staging → production safely |
| `event-scraping-bot-staging/` | Staging version of the event scraping pipeline |

---

## How to Use Staging

1. **Start a test:** Copy the production script you want to modify into the relevant staging folder (or it's already there)
2. **Make changes:** Experiment freely — try new scraping logic, enrichment steps, prompts
3. **Validate:** Run the staging version against a test event URL or sample data
4. **Promote:** When happy, use `Replicate-to-prod-skill.md` to apply the change to production

---

## Adding a New Staging Project

When starting a new experiment:
1. Create a new folder inside `staging/` named `[workflow-name]-staging/`
2. Copy the relevant production scripts in as the starting point
3. Add a `CLAUDE.md` in the staging folder explaining what's being tested

---

## Skill
See `Replicate-to-prod-skill.md` for instructions on promoting changes from staging to production.
