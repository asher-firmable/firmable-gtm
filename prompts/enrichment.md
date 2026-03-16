# Enrichment Prompts

## ICP Fit Summary
Given the following company data, write a 2-sentence summary for a sales rep explaining why this company is (or isn't) a good ICP fit.

Focus on: industry, company size, location (Australia preferred), and any signals that suggest they'd benefit from our product.

**Context:** `{company_data}`

---

## Personalised Email Opening Line
Write a single personalised opening line for a cold email to `{first_name}` at `{company_name}`.

Use this context about the company: `{company_data}`

Keep it natural, specific, and under 20 words. Do not start with "I" or "We".

---

## Lead Score Justification
Based on the following lead data, explain in one sentence why this lead received a score of `{score}/100`.

**Lead data:** `{lead_data}`
