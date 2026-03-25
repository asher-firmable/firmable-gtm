---
name: signal-research
description: Use this skill when finding buying signals for accounts or contacts. Triggers include researching companies for outreach angles, finding recent news, job postings, technology changes, funding events, or any trigger event that justifies outreach timing.
---

# Signal Research

## Signal types (ranked by outreach value)

### Tier 1: High-intent
- **Hiring sales roles** — scaling outbound, need data (especially SDR/BDR Manager, Head of Sales)
- **Funding round** — have budget and growth pressure, reviewing tool stack
- **APAC expansion** — entering AU/NZ market, need APAC data immediately
- **New sales leadership** — VP/Head of Sales joined within 90 days → likely reviewing tech stack

### Tier 2: Moderate
- **RevOps/Sales Ops hiring** — investing in sales infrastructure
- **Technology changes** — new CRM, new outbound tools (Outreach, Salesloft, Apollo, Smartlead)
- **Firmable competitor tech detected** — ZoomInfo, Apollo, Lusha, Cognism → displacement opportunity
- **Conference/event attendance in APAC** — shows APAC market interest

### Tier 3: Contextual
- Industry news, competitor moves, market trends that affect their pipeline
- New product launches that expand their ICP

## Research process

### Step 1: Identify available signals per account
For each company, check:
- LinkedIn: recent job postings, employee count changes, leadership hires
- Funding: Crunchbase, recent news
- Technology: technographic data from Firmable API (`scripts/firmable_api.py`)
- Web: company news, press releases

### Step 2: Score signal quality
Tier 1 signal → use signal-based email framework
Tier 2 signal → mention in opening, use pain-led body
Tier 3 signal → contextual reference only, not primary hook

### Step 3: Extract and structure
For each account, capture:
- `signal_type`: hiring/funding/expansion/tech_change/competitor
- `signal_detail`: specific description (e.g., "Hiring 3 SDRs in Sydney based on 2 active job posts")
- `signal_date`: when detected
- `signal_source_url`: LinkedIn post URL, news article, etc.
- `suggested_angle`: one sentence on how to connect signal to Firmable value prop

### Step 4: Map to email framework
Signal → framework from `knowledge/messaging-frameworks.md`
Pass enriched CSV to email-copywriting skill.

## When you learn something new
If a new signal type proves valuable, propose adding it to `knowledge/messaging-frameworks.md`.
