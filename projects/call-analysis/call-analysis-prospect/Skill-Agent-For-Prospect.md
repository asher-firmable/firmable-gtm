# Skill: Prospect Call Analysis

## What This Skill Does
Processes a call transcript with a Firmable prospect (pre-sale, discovery, or demo call). Extracts pain points, objections, qualification signals, buying intent, and exact quotes. Proposes an update to `knowledge/customer-insights.md`.

---

## Logical Steps

1. **Read the transcript** from `call-analysis/call-analysis-prospect/[file]`

2. **Extract the following:**

   **Company context:**
   - Company name, size (SMB/mid-market/enterprise), industry
   - Who was on the call (titles — not just names)
   - What tools they currently use for prospecting/data
   - What market they sell into (AU, NZ, SEA, APAC?)

   **Pain points:**
   - What's broken or frustrating with their current setup
   - Where they're losing time or pipeline to bad data
   - Exact quotes describing the problem in their own words

   **Qualification signals:**
   - ICP fit: do they sell B2B into APAC? Do they have a sales team?
   - Tech stack: are they using ZoomInfo, Apollo, Lusha, Cognism?
   - Budget signals: are they actively evaluating, or just curious?
   - Urgency: what's driving them to look now?

   **Objections raised:**
   - Pricing concerns
   - Integration / CRM concerns
   - Data quality doubts
   - Competition ("we already use X")

   **Buying signals:**
   - Asked about pricing, trial, or next steps
   - Brought in additional stakeholders
   - Referenced a specific use case they want to test

   **Exact quotes:**
   - Pull verbatim phrases for sales copy or ICP validation
   - Tag them: [pain point] [objection] [buying signal] [competitor mention] [social proof request]

3. **Qualify the transcript** — is it worth adding to the knowledge base?
   - Yes: strong ICP fit, new pain point framing, repeatable objection, usable quote
   - No: very short call, low-fit prospect, no new information

4. **Draft a structured entry** in the same format as entries in `knowledge/customer-insights.md`

5. **Present the proposed update** — show the full draft entry
6. **Wait for approval** before writing to `knowledge/customer-insights.md`

---

## Output Format

```markdown
## Call: [Company Name] — [Date]
**Contact:** [Name] ([Title], [X] months in role if known)
**Company:** [Company name] — [brief description]. [Size, location, funding if known].
**Company size:** [headcount range]
**Context:** [type of call — discovery, demo, follow-up, etc.]

### Why they were looking at Firmable
- [what triggered their search]
- [what they've tried before]

### Pain points
- [specific pain, ideally in their words]
- Exact quote: "[verbatim]"

### Qualification signals
- [ICP fit indicators]
- [tech stack detected]
- [urgency drivers]

### Objections raised
- [objection + context]

### Buying signals
- [positive indicators]

### What they value most
1. [feature or outcome they cared about]

### Friction / concerns
- [issue raised]

### Exact phrases for copy
- "[verbatim quote]" — [context]

### Their workflow (useful for integrations)
- [how they currently source, enrich, or use data]
```

---

## Key References
- `knowledge/customer-insights.md` — target file (read-only until approved)
- `knowledge/firmable-product.md` — ICP definition and value prop
- `knowledge/icp-definition.md` — scoring rubric to assess prospect fit
- `outbound/customer-stories-and-use-cases.md` — if this call becomes a case study
