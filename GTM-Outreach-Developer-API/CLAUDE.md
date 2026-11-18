# GTM Outreach: Developer API

## Purpose
Outreach work for Firmable's data/developer API (AI adoption index, tech intelligence, decision engine), pitched as a way for prospects' own sellers to build better prospect lists.

## What goes in
- A single company domain (per skill run)

## What goes out
- Three API statements (one sentence each) plus one recommended cold outreach line (45 words or fewer)

## Scripts / tools
- `skills/data-api-one-liner/SKILL.md`: domain → research → competitors + integrations → Firmable tech intel counts → API statements + recommended line
- Firmable developer MCP only (`mcp__firmable__*`, not the app connector): filter_search for tech intel counts and samples, get_ai_adoption and make_decision to test both engines on a 16 to 20 company sample

- `.claude/skills/data-api-one-liner` is a symlink to `skills/data-api-one-liner`, so the skill auto-triggers. Edit the file here, not through the symlink path.
- Data API Playbook (internal reference: endpoints, the three engines, all 34 decision tools with inputs and test results, credit pricing): https://claude.ai/artifact/FQsqg3dyp2SeunHUEsaYvM

## Conventions
- Measure counts against the prospect's home market, not ANZ by default.
- 200 rule: technologies under 200 companies stay out of the pitch (try grouping competitors first).
- Competitors come from the prospect's own site first (vs pages, named competitors), then review sites. Never from general knowledge alone.
- Copy rules: no em dashes, no bold, follow knowledge/messaging-frameworks.md tone.
