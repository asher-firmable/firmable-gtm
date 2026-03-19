# Skill: Write to Relevant Production Folder

## What This Skill Does
Takes a completed fun project and deploys it to the correct production folder. Figures out where it belongs, shows the plan, and waits for approval before moving anything.

---

## Logical Steps

1. **Read the project's CLAUDE.md** to understand what it does and what it's for

2. **Identify the target production folder:**

   | Project type | Target folder |
   |---|---|
   | Event scraping or sponsor outreach | `event-scraping-bot/` |
   | Contact lookup or people search | `find-contacts/` |
   | Email copy generation or outreach | `outbound/` |
   | Call transcript processing | `call-analysis/` |
   | New workflow that doesn't fit existing folders | Ask the user — may need a new folder |

3. **Identify what specifically needs to move:**
   - Python scripts → copy to target folder
   - Skill docs → copy to target folder
   - CLAUDE.md updates → propose changes to target folder's CLAUDE.md
   - New folder needed → propose structure and wait for confirmation

4. **Present the deployment plan:**
   - List exactly which files will be copied or created where
   - Show any proposed changes to existing files (e.g. target CLAUDE.md updates)

5. **Wait for explicit approval** before moving or creating anything in production folders

6. **Execute the approved plan** and confirm completion

7. **Optionally move the experiment to staging first** — if the project needs more testing before hitting production directly, route through `staging/` and use `Replicate-to-prod-skill.md`

---

## Safety Rules
- Never write to production folders without showing the plan first
- Never overwrite existing production files without showing a diff
- If unsure which folder a project belongs in, ask

---

## After Deployment
- Update root `CLAUDE.md` if a new production folder was created
- Use `Update-Claude-Agent.md` at root to run the update process
- Consider whether the fun project folder should stay or be cleaned up

---

## How to Use This Skill
Tell Claude Code: *"Deploy [project-name] from fun-projects to production"*
Claude will read this file, identify the target, show the plan, and wait for your approval.
