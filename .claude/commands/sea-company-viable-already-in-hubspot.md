# SEA Company — Viable, Already in HubSpot

Updates existing HubSpot company records for companies that are viable and already in HubSpot.
Sets Company Owner (SEA) for all of them. For those with no outreach status, sets a chosen status.
Requires `/sea-company-upload-check` to have been run first.

## Pre-flight check

Confirm `projects/sea-company-upload/output/viable_in_hubspot.csv` exists.
If missing, stop and tell the user:
> "Run `/sea-company-upload-check` first — it generates the input file for this command."

Read the file and report:
- Total companies to update
- How many have empty outreach engagement status (these will receive a new status)
- How many already have a status (these will only get Company Owner (SEA) updated)

## Step 1 — Choose Company Owner (SEA)

Run:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_owners.py
```

Show the output and ask:
> "Who should be the **Company Owner (SEA)** for these companies? Enter the number from the list above."

Wait for the user's choice. Record the SEA owner ID.

## Step 2 — Choose Outreach Engagement Status (only if any have empty status)

If any companies have empty outreach status, run:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_status_options.py
```

Show the output and ask:
> "**N** companies have no outreach engagement status set. What should it be? Enter the number from the list above.
> (Companies that already have a status will not be changed.)"

Wait for the user's choice. Record the status **value** (not the label — use the right-hand column).

If no companies have empty status, skip this step.

## Step 3 — Confirm before updating

Ask:
> "I'm about to update **N** companies in HubSpot:
> - Set Company Owner (SEA) to [sea owner name] for all N companies
> - Set outreach status '[label]' for X companies with empty status
>
> Shall I proceed?"

Only continue if the user confirms.

## Step 4 — Update companies

If outreach status was chosen:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/update_existing_companies.py \
  --sea-owner-id <sea_owner_id> \
  --status "<status_value>"
```

If no outreach status chosen (all companies already had a status):
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/update_existing_companies.py \
  --sea-owner-id <sea_owner_id>
```

Report the summary from the script output.

## Output
Script saves: `projects/sea-company-upload/output/viable_companies_existing.csv`

## After both commands complete

Once both `/sea-company-viable-not-in-hubspot` and `/sea-company-viable-already-in-hubspot` have run:
1. Read `projects/sea-company-upload/output/viable_companies_new.csv`
2. Read `projects/sea-company-upload/output/viable_companies_existing.csv`
3. Combine all rows and save as `projects/sea-company-upload/output/Viable Companies.csv`
4. Return the combined CSV to the user with a summary (total rows, new vs. existing breakdown).
