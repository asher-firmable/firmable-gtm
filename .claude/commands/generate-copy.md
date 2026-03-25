# Generate Email Copy

1. Ask which campaign this is for
2. Check if validated contacts exist in `campaigns/[region]/[name]/data/validated/`. If not, suggest running `/qualify-list` first.
3. Ask: "Any specific angle or framework preference, or should I select based on the campaign brief?"
4. Read `knowledge/messaging-frameworks.md`, `knowledge/firmable-product.md`, and the campaign's `brief.md`
5. Read `knowledge/competitors.md` if doing competitive displacement
6. Use the `.claude/skills/email-copywriting/SKILL.md` skill

## Copy generation
- Select framework based on: signal available → signal-based | no signal → pain-led | known competitor → displacement
- Generate 3–5 sample emails first and show them for review
- Ask: "Happy with these, or want to adjust tone/angle/length?"
- After approval, generate the full batch
- Output CSV to campaign's `data/final/` with columns: `email`, `first_name`, `company`, `subject`, `body`, `sequence_step`

## If generating a sequence (2–3 steps)
- Step 1: Primary outreach
- Step 2 (+3 days): New angle or value add
- Step 3 (+5 days): Short breakup email

## After generating
- Ask: "Ready to push to SmartLead? Or want to review the full CSV first?"
- If pushing: use `.claude/skills/smartlead-push/SKILL.md` — always confirm before activating
- Ask: "Should I commit the generated emails to Git?"

## Hard rules (always enforce)
- Max 100 words per email
- Lead with pain, not product
- No fluff: no "leverage", "synergy", "best-in-class", "cutting-edge"
- One CTA per email
- Never start with "I" or "We"
- Match tone to segment: Enterprise = formal/direct | Mid-market = conversational | SMB = casual

## References
- Email frameworks: `knowledge/messaging-frameworks.md`
- Product info: `knowledge/firmable-product.md`
- Competitor angles: `knowledge/competitors.md`
- Customer proof points: `projects/outbound/customer-stories-and-use-cases.md`
- Email templates (full examples): `projects/outbound/email-templates-examples.md`
- Email copywriting skill: `.claude/skills/email-copywriting/SKILL.md`
- SmartLead push skill: `.claude/skills/smartlead-push/SKILL.md`
