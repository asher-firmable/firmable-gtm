---
name: smartlead-push
description: Use this skill when pushing campaign data into SmartLead for email sending. Triggers include uploading leads, creating campaigns, setting up sequences, or any SmartLead API interaction.
---

# SmartLead Push

## Setup
- API key in `.env` as `SMARTLEAD_API_KEY`
- Client: `scripts/smartlead_client.py` → `SmartLeadClient`

```python
from scripts.smartlead_client import SmartLeadClient
sl = SmartLeadClient()
```

## Prerequisites
Before pushing, confirm all are present:
1. Account qualification complete (`data/qualified/`)
2. Contact validation complete (`data/validated/`)
3. Email copy generated (`data/final/`)
4. Final CSV has columns: `email`, `first_name`, `company`, `subject`, `body`, `sequence_step`
5. `config.json` has sender details filled in

## Process

### Create campaign
```python
campaign = sl.create_campaign(name="[region]-[angle]-[date]")
campaign_id = campaign["id"]
```

### Add email sequence (2-step example)
```python
sl.add_email_sequence(campaign_id, steps=[
    {
        "subject": "{{subject_1}}",
        "email_body": "{{body_1}}",
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0}
    },
    {
        "subject": "{{subject_2}}",
        "email_body": "{{body_2}}",
        "seq_number": 2,
        "seq_delay_details": {"delay_in_days": 3}
    }
])
```

### Upload leads
```python
leads = [{"email": row["email"], "first_name": row["first_name"], ...} for row in csv_rows]
sl.add_leads_to_campaign(campaign_id, leads)
```

## IMPORTANT: Always confirm before activating
**Never auto-activate a campaign.** Always ask: "Campaign created and leads uploaded. Should I activate it now?"

## Troubleshooting
- **403 on campaign creation**: SmartLead may be IP-restricted. Create the campaign manually in SmartLead UI, then pass `--campaign-id` to the upload script.
- **Lead upload fails**: Check that email field is valid and not empty. SmartLead rejects leads with missing emails silently.
- **Sequence not applying**: Sequences must be added before leads. If leads were added first, remove them, add sequence, re-add leads.

## Known SmartLead gotchas
See memory file `feedback_n8n_api_quirks.md` for full list of SmartLead API quirks.

## References
- Account pipeline upload script: `projects/outbound/account-pipeline/scripts/4_upload.py`
- Event scraper upload script: `projects/event-scraper/scripts/4_upload_to_smartlead.py`
