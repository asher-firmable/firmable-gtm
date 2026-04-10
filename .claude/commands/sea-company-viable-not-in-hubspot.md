# SEA Company — Viable, Not in HubSpot

Creates new HubSpot company records for companies that are viable but not yet in HubSpot.
Requires `/sea-company-upload-check` to have been run first.

## Pre-flight check

Confirm `projects/sea-company-upload/output/viable_not_in_hubspot.csv` exists.
If missing, stop and tell the user:
> "Run `/sea-company-upload-check` first — it generates the input file for this command."

Read the file and tell the user how many companies will be created.

## Step 1 — Choose Company Owner and Company Owner (SEA)

Run:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_owners.py
```

Show the output to the user and ask:
> "Who should be the **Company Owner** for these companies? Enter the number from the list above."

Wait for the user's choice. Record the owner ID from the ID column.

Then ask:
> "Who should be the **Company Owner (SEA)** for these companies? Enter the number, or press Enter to use the same as Company Owner."

Wait for the user's choice. Record the SEA owner ID.

## Step 2 — Choose Outreach Engagement Status

Run:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_status_options.py
```

Show the output and ask:
> "What should the **outreach engagement status** be for these new companies? Enter the number from the list above."

Wait for the user's choice. Record the status **value** (not the label — use the right-hand column).

## Step 3 — Confirm before creating

Ask:
> "I'm about to create **N** new companies in HubSpot:
> - Company Owner: [owner name]
> - Company Owner (SEA): [sea owner name]
> - Outreach Engagement Status: [label]
>
> Shall I proceed?"

Only continue if the user confirms.

## Step 4 — Create companies

Run:
```
PYTHONPATH=. python3 projects/sea-company-upload/scripts/create_new_companies.py \
  --owner-id <owner_id> \
  --sea-owner-id <sea_owner_id> \
  --status "<status_value>"
```

Report the summary from the script output.

## Output
Script saves: `projects/sea-company-upload/output/viable_companies_new.csv`

## After both commands complete

Once both `/sea-company-viable-not-in-hubspot` and `/sea-company-viable-already-in-hubspot` have run:
1. Read `projects/sea-company-upload/output/viable_companies_new.csv`
2. Read `projects/sea-company-upload/output/viable_companies_existing.csv`
3. Combine all rows and save as `projects/sea-company-upload/output/Viable Companies.csv`
4. Return the combined CSV to the user with a summary (total rows, new vs. existing breakdown).
