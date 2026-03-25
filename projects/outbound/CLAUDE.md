# Outbound — Sub-Agent

## Role
I own email copy generation and SmartLead campaign uploads for Firmable outbound campaigns. Before doing any email writing task, I read `email-templates-examples.md` and `customer-stories-and-use-cases.md`.

---

## What Lives Here

| File/Folder | Purpose |
|---|---|
| `email-templates-examples.md` | 7 cold email template frameworks with Firmable examples |
| `customer-stories-and-use-cases.md` | Key customer outcomes to use as social proof in copy |
| `raw-transcripts/` | Raw call recordings/notes from prospects and customers |
| `email-writing/Email-Writing-Skill.md` | Full skill for generating personalised emails |
| `account-pipeline/` | End-to-end account-based pipeline: filter → find contacts → research → generate emails → SmartLead upload |

---

## Before Writing Any Email
1. Read `email-templates-examples.md` — understand which template fits the use case
2. Read `customer-stories-and-use-cases.md` — pick relevant proof points
3. Read `knowledge/persona-definitions.md` (at root) — match messaging to the persona
4. Read `knowledge/firmable-product.md` (at root) — Firmable's positioning and tone

---

## Tone Rules
- Problem-first, then proof, then CTA
- Confident, direct, local — not corporate or generic
- Short sentences. No fluff. No AI/SaaS clichés.
- Never start with "I" or "We"
- Subject lines: curiosity or direct — never clickbait

---

## Persona → Template Routing

| Persona | Recommended Template |
|---|---|
| SDR Manager | Competitor Analysis (if tech detected), PQS, Direct Email |
| RevOps / Marketing Ops | PQS, Audit Offer, Competitor Analysis |
| Sales Leader | PQS, Direct Email, Competitor Analysis |
| Recruitment Consultant | Trojan Horse, PQS, Direct Email |

---

## Workflow: Generating Personalised Emails

1. Get enriched lead data (from `projects/event-scraper/output/` or `projects/find-contacts/output/`)
2. Identify persona from job title
3. Select template from `email-templates-examples.md`
4. Pull proof point from `customer-stories-and-use-cases.md`
5. Generate copy using Claude (via `scripts/ai.py`)
6. Output as a CSV row with `subject`, `body` columns ready for SmartLead

---

## Skills
See `email-writing/Email-Writing-Skill.md` for full email generation instructions.

---

## Key References
- `knowledge/persona-definitions.md` — 4 buyer personas with pain points and messaging angles
- `knowledge/firmable-product.md` — company context, ICP, tone
- `knowledge/customer-insights.md` — full call transcripts and synthesized insights
- `scripts/smartlead_client.py` — `SmartLeadClient.add_leads_to_campaign()`
- `scripts/ai.py` — `ask_claude()` for copy generation
