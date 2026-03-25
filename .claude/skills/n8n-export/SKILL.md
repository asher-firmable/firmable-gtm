---
name: n8n-export
description: Use this skill to convert workflows or scripts into n8n automation JSON files, or to create/edit n8n workflows via the REST API. Triggers include requests to automate a manual process, export a pipeline as n8n, set up webhook-triggered automations, or manage existing workflows.
---

# n8n Export & Workflow Management

This skill has two modes:

## Mode 1: Convert a pipeline to n8n JSON

Use when a campaign pipeline has been proven manually and should run on autopilot.

### When to use
- A campaign pipeline has been proven manually and should run on autopilot
- A signal-to-HubSpot workflow needs scheduling
- Any repeatable process that shouldn't require Claude Code every time

### Process
1. Map pipeline as discrete steps (trigger, data processing, API calls, output)
2. Generate valid n8n workflow JSON using the n8n MCP tools
3. Map `.env` variables to n8n credential references
4. Test with `n8n_test_workflow` before deploying
5. Save exported JSON for reference

## Mode 2: Manage existing n8n workflows

For creating, editing, or viewing existing workflows via the API.

See `projects/n8n/N8n-Changes-Skill.md` for the full step-by-step workflow management guide.

### Safety rules (always apply)
- **Always show proposed change before calling PUT or POST** — never modify without review
- **Never auto-activate** — only activate if explicitly asked
- **Deactivate before editing** any active workflow
- **Never delete** without confirming intent twice

## n8n MCP tools available
- `n8n_list_workflows` — see all workflows
- `n8n_get_workflow` — inspect a workflow's JSON
- `n8n_create_workflow` — create from scratch
- `n8n_update_full_workflow` — replace a workflow entirely
- `n8n_update_partial_workflow` — update specific nodes
- `n8n_test_workflow` — test without activating
- `n8n_validate_workflow` — check JSON validity

## References
- n8n sub-agent: `projects/n8n/CLAUDE.md`
- Full management guide: `projects/n8n/N8n-Changes-Skill.md`
