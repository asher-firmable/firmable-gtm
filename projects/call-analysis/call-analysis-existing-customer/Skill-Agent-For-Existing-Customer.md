# Skill: Existing Customer Call Analysis

## What This Skill Does
Processes a call transcript with an existing Firmable customer. Extracts product feedback, satisfaction signals, expansion opportunities, objections, and exact quotes. Proposes an update to `knowledge/customer-insights.md`.

---

## Logical Steps

1. **Read the transcript** from `call-analysis/call-analysis-existing-customer/[file]`

2. **Extract the following:**

   **Company context:**
   - Company name, size (SMB/mid-market/enterprise), industry
   - Who was on the call (titles, not just names)
   - How long they've been a customer
   - What they were using before Firmable

   **Product usage:**
   - Which features they use most
   - Which features they haven't used but should
   - Workflow: how they get data into their CRM/tools

   **Satisfaction signals:**
   - What's working well (direct quotes preferred)
   - Any friction or complaints
   - NPS-style sentiment (positive / neutral / at-risk)

   **Expansion opportunities:**
   - Seats they might add
   - Use cases they haven't explored yet
   - Integrations or features they're waiting for

   **Exact quotes:**
   - Pull verbatim phrases that could appear in sales copy or case studies
   - Tag them: [social proof] [pain point] [product feedback] [competitor mention]

3. **Qualify the transcript** — is it worth adding to the knowledge base?
   - Yes: contains new insights, strong quotes, or updates an existing entry
   - No: duplicate of existing notes, too short to be meaningful

4. **Draft a structured entry** in the same format as entries in `knowledge/customer-insights.md`

5. **Present the proposed update** — show the full draft entry
6. **Wait for approval** before writing to `knowledge/customer-insights.md`

---

## Output Format

```markdown
## Call: [Company Name] — [Date]
**Contact:** [Name] ([Title], [X] months/years at company)
**Company:** [Company name] — [brief description]. [Funding stage if known].
**Company size:** [headcount range]
**Context:** [type of call — QBR, check-in, upsell, support, etc.]

### Published results / quantified outcomes
- [stat or outcome if shared]

### What's working
- [key positive feedback]
- [exact quote if available]

### Friction / complaints
- [issue raised]

### Expansion signals
- [seats, use cases, features they want]

### Exact phrases for copy
- "[verbatim quote]" — [context]

### Product feedback (pass to product team)
- [specific request or issue]
```

---

## Key References
- `knowledge/customer-insights.md` — target file (read-only until approved)
- `knowledge/firmable-context.md` — context for interpreting product feedback
