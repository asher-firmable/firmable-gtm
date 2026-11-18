# Firmable Signal Webhook — ICP Check

## Purpose

Receives Firmable's own "signal agent" webhook (fired when a company posts a business-development/sales-development job listing) and immediately runs an ICP fit check on that company, so hiring signals get triaged continuously instead of piling up for manual review.

**This folder deviates from every other `projects/` sub-folder: it is TypeScript authored for Deepline, not Python.** There is no `scripts/*.py`, no `PYTHONPATH=.` invocation — everything runs through the `deepline` CLI (installed locally at `.deepline/runtime/`, see repo-root `CLAUDE.md`).

## What goes in

An HTTP POST from Firmable's signal agent, HMAC-signed, matching this shape (nulls are common — Firmable's test events populate few fields):

```json
{
  "agent_id": 2934,
  "agent_name": "Asher Market Signal Test - Find companies actively hiring in sales",
  "event_type": "signal.found",
  "category": "company",
  "company_id": "f000000253689",
  "company_name": "MartianLogic",
  "id": "fs2d713c92fd2cd59514bf86b1c4b74e23",
  "signal": "company-new-job-posted",
  "signal_type_name": "New job posted",
  "signal_type_slug": "company-new-job-posted",
  "source_url": null,
  "summary": null,
  "website": null,
  "...": "see firmable-bdr-signal-icp-check.play.ts for the full type"
}
```

Only `category: "company"` + `signal_type_slug: "company-new-job-posted"` events are scored; anything else returns `{ skipped: true, reason }` without spending on enrichment/AI.

## What goes out

- **Deepline's own play-run log** — every invocation's input/output is inspectable via `deepline runs list --play firmable-bdr-signal-icp-check --json` and `deepline runs get <run-id> --full --json`.
- **A row in `analytics.firmable_signal_icp_checks`** (customer_db/Postgres) — `firmable_event_id, company_id, company_name, signal_type, enrichment_status, icp_tier, icp_score, icp_reasons, disqualified, disqualification_reason, created_at`. This is the queryable log and the input a future activation step would read from.

**v1 explicitly does not write to HubSpot, SmartLead, or Slack.** No outreach action is taken on any verdict yet — that's deferred to a later iteration.

## Scripts / tools

- `firmable-bdr-signal-icp-check.play.ts` — the play. On a matching event: enrich the company via the connected `firmable_company_lookup` tool (Deepline's live equivalent of `scripts/firmable_api.py::FirmableClient.lookup_company_by_id()`), score it against `knowledge/icp-definition.md`'s rubric via `ai_inference` (same rubric `.claude/skills/account-qualification/` uses — do not invent new scoring criteria here), then persist the verdict to `query_customer_db`.
- Useful `deepline` CLI commands:
  - `deepline plays check ./firmable-bdr-signal-icp-check.play.ts` — type-check/bundle without running.
  - `deepline plays run --file ./firmable-bdr-signal-icp-check.play.ts --input '{...}' --json` — local dry run against a synthetic payload, no HMAC or public URL needed.
  - `deepline plays publish ./firmable-bdr-signal-icp-check.play.ts` then `deepline plays get firmable-bdr-signal-icp-check --json` — publish and read the live webhook URL (only known after first publish).
  - `deepline runs list --play firmable-bdr-signal-icp-check --json` / `deepline runs get <run-id> --full --json` — inspect past runs.
  - `deepline tools execute query_customer_db --input '{"sql":"SELECT * FROM analytics.firmable_signal_icp_checks ORDER BY created_at DESC LIMIT 20"}' --json` — read the log directly.

## Conventions

- `FIRMABLE_WEBHOOK_SECRET` lives in **Deepline's own secret store** (`deepline secrets set FIRMABLE_WEBHOOK_SECRET`), not this repo's `.env` — the play runs in Deepline's cloud runtime, which never sees this repo's local env.
- The HMAC header name (currently configured as `x-firmable-signature`, algorithm `sha256`) is unconfirmed against Firmable's actual outbound webhook signing scheme — verify with Firmable's dashboard/docs before pointing production traffic at the published play, and update the `webhook.hmac` binding if it differs.
- `query_customer_db` takes one raw SQL string with no parameter binding, so every interpolated value in the play goes through `sqlString()`/`escapeSqlLiteral()` first. That helper also strips semicolons from string values (not just SQL-escapes quotes) — the tool's own statement-count guard flags any semicolon in the raw SQL text, even one inside a quoted literal, as a second statement.
- Model id format for `ai_inference` is `provider/model` with a **dot**, not a dash, in the version (e.g. `anthropic/claude-sonnet-4.6`, not `claude-sonnet-4-6`) — confirm against the live AI Gateway catalog if a call 422s with "No AI Gateway pricing metadata."
- Known v1 gap: `knowledge/exclusions.md`'s "Future Rules" (existing customers, competitor orgs) aren't checked here. Acceptable for now since this stage only logs — no outreach action follows a verdict yet.
