# Skill: Email Copywriting

## What This Skill Does
Given an enriched lead (company data, contact name, job title, detected tech stack), generates a personalised cold email ready for SmartLead upload. Selects the appropriate template based on persona and available signals.

---

## Logical Steps

1. **Identify the persona** from job title:
   - SDR Manager / BDR Manager / Sales Development → Persona 1
   - RevOps / Marketing Ops / Demand Gen / Marketing Manager → Persona 2
   - VP Sales / Head of Sales / Sales Director → Persona 3
   - Recruitment Consultant / Senior Consultant / BD Manager at recruitment firm → Persona 4

2. **Check for competitive tech** (from enrichment data):
   - If ZoomInfo, Apollo, Lusha, or Cognism detected → use Competitor Analysis template
   - This is the strongest trigger — override persona routing if present

3. **Select template** from `outbound/email-templates-examples.md`:
   - Persona 1 (SDR Manager): Competitor Analysis → PQS → Direct Email
   - Persona 2 (RevOps): PQS → Audit Offer → Competitor Analysis
   - Persona 3 (Sales Leader): PQS → Direct Email → Competitor Analysis
   - Persona 4 (Recruitment): Trojan Horse → PQS → Direct Email

4. **Select proof point** from `outbound/customer-stories-and-use-cases.md`:
   - Connect rate pain → Cotiss story (doubled connects)
   - Data quality pain → Cotiss 30% → 85–90% accuracy
   - Marketing owning prospecting → Stripe story
   - Senior buyer → $2M pipeline or $160K/mo per SDR
   - Cost/waterfall pain → "one credit = full profile" angle

5. **Generate email** using the pattern below. Keep it under 100 words.

6. **Generate subject line** — curiosity or direct. Examples:
   - "Quick question about [company]'s AU data"
   - "How [company] is getting [X]% connect rate"
   - "[First name] — your tool for APAC?"

---

## Email Prompt for Claude
```python
from applications.ai import ask_claude

prompt = f"""
Write a cold email to {first_name} at {company_name}.

Their job title: {job_title}
Persona: {persona}
Template to use: {template_name}
Detected tech: {detected_tech}

Company context:
- Industry: {industry}
- Headcount: {headcount}
- Country: {country}

Proof point to use: {proof_point}

Rules:
- Under 100 words
- Problem-first, then proof, then CTA
- Confident, direct, local — no corporate fluff
- No AI clichés ("I came across your profile", "hope this finds you well")
- Never start with "I" or "We"
- End with a low-friction CTA (not "book a 30-minute call")
"""

email = ask_claude(prompt=prompt, context=company_data)
```

---

## Tone Rules
- Problem-first, then proof, then CTA
- Short sentences. No filler. Direct.
- Local Australian voice — not polished US corporate
- Never: "I hope this finds you well", "just reaching out", "touch base", "synergy"
- Never start with "I" or "We"

---

## Output Format (for SmartLead CSV upload)
```
first_name, last_name, email, company_name, subject, email_body
```

---

## Key References
- `outbound/email-templates-examples.md` — 7 template frameworks
- `outbound/customer-stories-and-use-cases.md` — proof points
- `knowledge/persona-definitions.md` — persona details, pain points, KPIs
- `knowledge/firmable-product.md` — Firmable positioning, tone
- `scripts/ai.py` — `ask_claude()` function
- `scripts/smartlead_client.py` — `add_leads_to_campaign()` for upload
