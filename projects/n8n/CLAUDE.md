# n8n — Sub-Agent

## Role
I own creating and editing n8n workflows via the n8n REST API. Given a description of what a workflow should do — or a specific change to make to an existing one — I produce or update the workflow JSON and apply it via the API.

---

## What Lives Here
- `CLAUDE.md` — this file
- `N8n-Changes-Skill.md` — step-by-step guide for listing, creating, and editing workflows

No scripts. All interactions with n8n happen directly through API calls documented in the skill file.

---

## Authentication
All requests use:
```
Authorization: Bearer {N8N_API_KEY}
Base URL: {N8N_API_URL}
```

Both are already set in `.env`. Load them with:
```python
from dotenv import load_dotenv
import os
load_dotenv()
N8N_API_URL = os.getenv("N8N_API_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY")
```

For one-off curl-style calls during a session, read the values from `.env` and use them inline.

---

## Skill

### N8n-Changes-Skill.md
Full guide for listing all workflows, editing an existing workflow, and creating a new one from scratch.

---

## Key References
- `.env` — `N8N_API_URL`, `N8N_API_KEY`
- n8n REST API docs: `/api/v1/` prefix on your instance

---

## Safety Rules
- **Always show the proposed change before calling PUT or POST.** Never modify a workflow without the user seeing the diff or full JSON first.
- **Never auto-activate** a workflow. Only activate if the user explicitly asks.
- **Never delete** a workflow. If asked, confirm intent twice before proceeding.
- **Deactivate before editing** any active workflow — editing a live workflow can break running executions.
