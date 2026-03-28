# New Campaign Setup

Ask the following questions one at a time:

1. **Campaign title**: "What do you want to call this campaign?" (e.g., "saas-series-b-hiring-sdrs")
2. **Region**: "Which region?" (anz / us / sea / global)
3. **Goal**: "What's the primary goal?" (e.g., "book discovery calls with SDR managers")
4. **Target segment**: "Enterprise, Mid-Market, SMB, or a mix?"
5. **Angle/hook**: "What's the outreach angle or buying signal we're targeting?"
6. **Estimated list size**: "Roughly how many accounts?"
7. **Data source**: "Firmable search, uploaded CSV, or should I source them?"

Then create the campaign folder:

```
campaigns/[region]/[campaign-title]/
├── brief.md          ← filled with answers above
├── data/
│   ├── raw/          ← source list goes here
│   ├── qualified/    ← after account-qualification skill
│   ├── validated/    ← after contact-validation skill
│   └── final/        ← email-ready CSV for SmartLead
└── notes.md          ← decisions, changes, results over time
```

Fill `brief.md` with:
- Campaign goal and angle
- Target segment and region
- ICP criteria specific to this campaign (reference `knowledge/icp-definition.md` for defaults)
- Persona targets (reference `knowledge/persona-definitions.md`)
- Email framework selected (reference `knowledge/messaging-frameworks.md`)
- Data source

Then ask: "Campaign folder is set up. Want to start with step 1 (qualify/source accounts), or do you already have a list ready?"

## Campaign readiness checklist (run before SmartLead upload)

Before uploading any contact list to SmartLead, confirm all steps are complete:

1. **Account qualification** — ICP scoring via `account-qualification` skill
2. **Contact validation** — Persona/title check via `contact-validation` skill
3. **HubSpot eligibility check** — Pre-flight gate via `scripts/hubspot_eligibility.py`
   - Removes customers + active trials
   - Removes contacts with recent comms (calls/emails/meetings in last 30 days)
   - Removes contacts with no scheduled task on their record or account
4. **Classifier** — AI scoring via `scripts/classifier.py`
5. **Copy generation** — via `email-copywriting` skill
6. **SmartLead upload** — confirm lead count, campaign name, and sender before activating

```bash
# Step 3 — HubSpot eligibility check
PYTHONPATH=. python3 scripts/hubspot_eligibility.py \
  --input campaigns/[region]/[campaign]/data/validated/contacts.csv \
  --output campaigns/[region]/[campaign]/data/final/eligible.csv
```

## References
- Account pipeline scripts: `projects/outbound/account-pipeline/scripts/`
- Account pipeline skill: `projects/outbound/account-pipeline/Account-Pipeline-Skill.md`
- HubSpot eligibility skill: `.claude/skills/hubspot-eligibility/SKILL.md`
- ICP criteria: `knowledge/icp-definition.md`
- Persona definitions: `knowledge/persona-definitions.md`
- Email frameworks: `knowledge/messaging-frameworks.md`
- Competitor angles: `knowledge/competitors.md`
