# Fun Projects — Sub-Agent

## Role
I am the experimentation sandbox. This is where you build, reverse-engineer, and test new ideas before they become production workflows. Nothing here is expected to be polished.

---

## Rules
- No pressure to productionise everything — some experiments just live here
- When something is ready for production, use `Write-To-Relevant-Folder-Skill.md`
- Keep each experiment in its own sub-folder with a short CLAUDE.md explaining what it does

---

## What Lives Here
Each project gets its own folder:
```
fun-projects/
├── CLAUDE.md                          ← This file
├── Write-To-Relevant-Folder-Skill.md  ← Skill: promote to production
└── [project-name]/
    ├── CLAUDE.md                      ← What is this experiment?
    └── files...
```

---

## Starting a New Experiment
1. Create a folder named after the experiment (e.g. `linkedin-scraper/`, `reverse-engineered-clay/`)
2. Add a brief `CLAUDE.md` explaining: what it is, what it does, what production folder it might go to
3. Build freely

---

## Promoting to Production
When an experiment is ready:
- Use `Write-To-Relevant-Folder-Skill.md` to identify the right production folder
- Or use `staging/Replicate-to-prod-skill.md` if you've already moved it to staging

---

## Skill
See `Write-To-Relevant-Folder-Skill.md` for instructions on deploying a fun project to production.
