---
name: hubspot-eligibility
description: Use this skill to check whether contacts are eligible for cold outbound before uploading to SmartLead. Triggers include pre-campaign checks, filtering known customers or active trials, or verifying no recent comms exist on a contact list.
---

# HubSpot Eligibility Check

## When to use
Run this after contact validation and before copy generation — any time you're preparing a list for cold outreach. It is a required pre-flight step in the `/new-campaign` workflow.

## What it checks

**Gate 1 — Lifecycle (company-level)**
- Excludes contacts where `lifecyclestage == "customer"`
- Excludes contacts where the associated company's `trial_status` is `"Active Trial"` or `"Paying Customer from Trial"`

**Gate 2 — Engagement (contact-level, last 30 days)**
- Requires at least one scheduled task (`NOT_STARTED`, future or open due date) on the contact or associated company
- Rejects contacts with any logged call, email, or meeting in the last 30 days

## How to run

```bash
PYTHONPATH=. python3 scripts/hubspot_eligibility.py \
  --input path/to/contacts.csv \
  --output path/to/eligible.csv
```

Input CSV must have an `email` column. Output path is optional — defaults to `output/eligible_<timestamp>.csv`.

## Output columns

| Column | Description |
|---|---|
| `status` | PASS / FAIL / NOT_FOUND / ERROR |
| `eligible` | True / False |
| `fail_reasons` | Pipe-separated failure codes (blank if PASS) |
| `contact_id` | HubSpot contact ID |
| `company_id` | Associated company ID |
| `lifecyclestage` | Raw lifecycle value from HubSpot |
| `trial_status` | Raw trial_status value from company record |
| `scheduled_tasks` | Count of NOT_STARTED tasks found (contact + company) |
| `recent_comms` | Count of calls/emails/meetings in the last 30 days |

## After running

Filter to `eligible == True` rows and pass to the classifier:

```bash
# Filter in Python
df = pd.read_csv("eligible.csv")
ready = df[df["eligible"] == True]
ready.to_csv("ready_for_classifier.csv", index=False)
```

Then continue with `scripts/classifier.py` → copy generation → SmartLead upload.

## Campaign workflow position

```
Clay CSV → data/input/
→ account-qualification (ICP scoring)
→ contact-validation (persona/title check)
→ hubspot-eligibility check  ← THIS STEP
→ classifier (AI scoring)
→ copy generation
→ SmartLead upload
```
