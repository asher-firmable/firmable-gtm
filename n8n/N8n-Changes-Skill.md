# Skill: n8n Workflow Changes

## What This Skill Does
Given a request to create a new n8n workflow or modify an existing one, this skill:
1. Authenticates with the n8n REST API using credentials from `.env`
2. Lists or fetches the target workflow
3. Builds or modifies the workflow JSON
4. Shows the full change to the user and waits for approval
5. Applies the change via PUT or POST

---

## Authentication
Read from `.env`:
- `N8N_API_URL` — base URL (e.g. `https://your-instance.railway.app`)
- `N8N_API_KEY` — API key for Bearer auth

All requests use:
```
Authorization: Bearer {N8N_API_KEY}
Content-Type: application/json
```

---

## Step-by-Step: Edit an Existing Workflow

### 1. List all workflows
```
GET {N8N_API_URL}/api/v1/workflows
Authorization: Bearer {N8N_API_KEY}
```
Find the target workflow by name. Note its `id`.

### 2. Fetch the full workflow JSON
```
GET {N8N_API_URL}/api/v1/workflows/{id}
Authorization: Bearer {N8N_API_KEY}
```
Response contains `nodes`, `connections`, `settings`, `name`, `active`.

### 3. Apply the requested change
Modify the workflow JSON in memory:
- **Add a node** — append to `nodes[]`, wire it in `connections`
- **Change a parameter** — find the node in `nodes[]` by `name` or `type`, update `parameters`
- **Rewire** — update the `connections` object (source node → output index → target node + input index)
- **Rename** — update `name` at the top level

### 4. Show the diff and wait for approval
Present the before/after for the changed section (node parameters, connections, or name). Do not proceed until the user confirms.

### 5. Deactivate if the workflow is active
```
POST {N8N_API_URL}/api/v1/workflows/{id}/deactivate
Authorization: Bearer {N8N_API_KEY}
```
Required before editing a live workflow to avoid broken executions.

### 6. Apply the update
```
PUT {N8N_API_URL}/api/v1/workflows/{id}
Authorization: Bearer {N8N_API_KEY}
Content-Type: application/json

{ ...full updated workflow JSON... }
```
The body must be the **complete** workflow object, not a partial patch.

### 7. Confirm the change
```
GET {N8N_API_URL}/api/v1/workflows/{id}
```
Verify the node/parameter change is reflected in the response.

### 8. Reactivate (only if user asks)
```
POST {N8N_API_URL}/api/v1/workflows/{id}/activate
```

---

## Step-by-Step: Create a New Workflow

### 1. Clarify with the user
Before building anything, confirm:
- Workflow name
- Trigger type (webhook, schedule, manual, another node type)
- Each node needed and what it does
- How nodes connect (linear chain or branching)

### 2. Build the workflow JSON
Construct the full object:
```json
{
  "name": "My Workflow",
  "nodes": [ ...node objects... ],
  "connections": { ...connection map... },
  "settings": {}
}
```
See **Workflow JSON Structure** below for the schema.

### 3. Show the full JSON and wait for approval
Display the complete payload. Do not POST until the user confirms.

### 4. Create the workflow
```
POST {N8N_API_URL}/api/v1/workflows
Authorization: Bearer {N8N_API_KEY}
Content-Type: application/json

{ ...workflow JSON... }
```
Response includes the new workflow `id`.

### 5. Activate (only if user asks)
```
POST {N8N_API_URL}/api/v1/workflows/{id}/activate
```

---

## n8n REST API Reference

| Action | Method | Endpoint |
|---|---|---|
| List all workflows | GET | `/api/v1/workflows` |
| Get a workflow | GET | `/api/v1/workflows/{id}` |
| Create a workflow | POST | `/api/v1/workflows` |
| Update a workflow | PUT | `/api/v1/workflows/{id}` |
| Delete a workflow | DELETE | `/api/v1/workflows/{id}` |
| Activate | POST | `/api/v1/workflows/{id}/activate` |
| Deactivate | POST | `/api/v1/workflows/{id}/deactivate` |
| List executions | GET | `/api/v1/executions` |
| Get execution | GET | `/api/v1/executions/{id}` |

Query params for list workflows: `?limit=100&active=true`

---

## Workflow JSON Structure

Minimal annotated example:
```json
{
  "name": "Example Workflow",
  "active": false,
  "nodes": [
    {
      "id": "uuid-1",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "parameters": {
        "path": "my-webhook",
        "responseMode": "onReceived"
      }
    },
    {
      "id": "uuid-2",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [500, 300],
      "parameters": {
        "url": "https://api.example.com/data",
        "method": "POST"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          { "node": "HTTP Request", "type": "main", "index": 0 }
        ]
      ]
    }
  },
  "settings": {}
}
```

**Key rules:**
- `nodes[].id` — unique UUID per node; generate a new one when adding a node
- `nodes[].name` — used as the key in `connections`; must be unique within the workflow
- `connections` — keyed by source node name → `main` → array of output arrays → list of `{ node, type, index }` targets
- `position` — `[x, y]` pixel coordinates; space nodes ~250px apart horizontally
- PUT requires the full object — partial updates are not supported

---

## Safety Rules
- Always show proposed changes before calling PUT or POST
- Never auto-activate — only activate on explicit request
- Never delete a workflow
- Deactivate before editing any active workflow
- If unsure which workflow to edit, list all and confirm with the user before fetching

---

## How to Use This Skill in a New Session
Tell Claude Code: *"Run the n8n changes skill — [describe what you want to create or change]"*

Claude will read `n8n/CLAUDE.md`, then this file, then proceed through the relevant steps.
