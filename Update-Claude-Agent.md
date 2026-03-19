# Update Claude Agent — Meta-Skill

## What This Does
Keeps the root `CLAUDE.md` (Big Brother) accurate whenever a new folder, file, or sub-agent is added to the project. Run this whenever you create something new.

---

## When to Run
- A new top-level folder is created (e.g. `crm-sync/`, `lead-scoring/`)
- A new sub-agent `CLAUDE.md` is added inside a folder
- A new skill file is created
- A folder or file is renamed or removed

---

## Logical Steps

1. **Read the current root `CLAUDE.md`** — understand what's already documented

2. **Identify what changed:**
   - New folder(s) added?
   - New skill doc(s) added?
   - Folder renamed?
   - Folder removed?

3. **Determine where to update in `CLAUDE.md`:**
   - New top-level folder → add to the folder structure tree AND the routing table
   - New skill → add to the relevant sub-agent's folder entry in the tree
   - Rename → update all references (tree, routing table, conventions)
   - Removal → remove from tree and routing table

4. **Draft the proposed update:**
   - Show exactly which lines in `CLAUDE.md` will change
   - Keep descriptions brief (one line per entry)

5. **Apply the update** — edit `CLAUDE.md` directly with the changes

6. **Confirm** — state which entries were added, changed, or removed

---

## Format for New Folder Entry

In the tree section:
```
├── [folder-name]/                   ← Brief one-line description
│   ├── CLAUDE.md                    ← Sub-agent: [what it does]
│   └── [Skill-Name.md]              ← Skill: [what it does]
```

In the routing table:
```
| [What user wants to do] | `[folder-name]/` |
```

---

## Example
User creates a new `crm-sync/` folder with a `CLAUDE.md` and `Sync-Contacts-Skill.md`.

**Tree addition:**
```
├── crm-sync/                        ← HubSpot CRM sync workflows
│   ├── CLAUDE.md                    ← Sub-agent: create/update contacts, companies, deals
│   └── Sync-Contacts-Skill.md       ← Skill: sync enriched leads to HubSpot
```

**Routing table addition:**
```
| Sync contacts or companies to HubSpot | `crm-sync/` |
```

---

## How to Use This
Tell Claude Code: *"Update the Big Brother CLAUDE.md — I just created [folder/file]"*
Claude will read this file and update `CLAUDE.md` accordingly.
