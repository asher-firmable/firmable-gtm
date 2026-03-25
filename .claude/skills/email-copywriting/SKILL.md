---
name: email-copywriting
description: Use this skill when writing cold outbound emails, follow-up sequences, or any sales copy. Triggers include requests to write copy, create sequences, personalise emails at scale, or generate subject lines.
---

# Email Copywriting

## Before you start
1. Read `knowledge/messaging-frameworks.md` — approved frameworks and persona routing
2. Read `knowledge/firmable-product.md` — accurate product claims, differentiators
3. Read `knowledge/competitors.md` — if doing competitive displacement
4. Read the campaign's `brief.md` for the specific angle and target segment
5. Read `projects/outbound/customer-stories-and-use-cases.md` — proof points
6. Determine target segment — tone varies significantly

## Process

### Step 1: Select framework
Signal available → Signal-based | No signal → Pain-led | Known competitor → Displacement

### Step 2: Personalisation variables
`{first_name}`, `{company}`, `{signal}`, `{pain_point}`, `{social_proof}`, `{competitor}`

### Step 3: Generate copy
Hard rules:
- Max 100 words
- Lead with pain, not product — never open with "Firmable is..."
- One CTA only
- No fluff: "leverage", "synergy", "best-in-class", "cutting-edge", "industry-leading" are banned
- Never start with "I" or "We"
- Short sentences. Scannable.
- Match tone: Enterprise = formal/direct | Mid-market = conversational | SMB = very casual

### Step 4: Sequence (if requested)
Email 1: Primary outreach
Email 2 (+3 days): New angle or value add — do not repeat Email 1
Email 3 (+5 days): Short breakup email (2 sentences max)

### Step 5: Output
CSV with columns: `email`, `first_name`, `company`, `subject`, `body`, `sequence_step`
Save to campaign's `data/final/` folder. Ready for SmartLead import.

## When you learn something new
If a framework works or doesn't, propose an update to `knowledge/messaging-frameworks.md` with what the result was and why.

## References
- Full email templates with examples: `projects/outbound/email-templates-examples.md`
- SmartLead push: `.claude/skills/smartlead-push/SKILL.md`
