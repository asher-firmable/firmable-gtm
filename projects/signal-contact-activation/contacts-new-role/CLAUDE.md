# Contacts — New Role (Sub-Agent)

## Purpose
Classify Firmable-exported contacts who recently started new roles against Firmable's ICP definition. The new-role event is the buying signal — a job change creates a window to reach decision-makers before they lock in existing vendor relationships.

## What goes in
- A Firmable-exported contacts CSV/XLSX from `data/input/` containing people who started new roles.
- Required columns: `First name`, `Last name`, `Position`, `Headline`, `Company name`, `Company website`

## What goes out
- An enriched CSV written to `output/classified_<timestamp>.csv` with three new columns:

| Column | Values | Description |
|--------|--------|-------------|
| `icp_match` | Yes / No | Whether the contact qualifies against Firmable's ICP |
| `icp_reason` | string | One-sentence explanation of the classification decision |
| `confidence` | high / low | Low = company type was ambiguous; website re-fetch was triggered |

## Scripts
- `scripts/classify_new_roles.py` — Step 1: maps CSV columns to classifier fields, runs the two-pass ICP classifier, writes output with `icp_match`, `icp_reason`, `confidence`
- `scripts/enrich_headcount.py` — Step 2: takes the classified CSV, fetches Firmable sales headcount for ICP Yes contacts, writes enriched CSV and prints a summary table

## Column Mapping
`load_csv()` normalises all column names to `snake_case`. The script maps to classifier fields as follows:

| CSV column (normalised) | Classifier field | Notes |
|-------------------------|-----------------|-------|
| `first_name` | `first_name` | |
| `last_name` | `last_name` | |
| `position` | `title` | Primary seniority signal — this is the only role used |
| `headline` | `summary` | Passed solely for the BDM ambiguity check (team leadership evidence). Does NOT trigger secondary-role inference. |
| `company_name` | `company` | |
| `company_website` | `website` | Used for website re-fetch on low-confidence contacts |

## Usage
```bash
# Step 1 — classify contacts
PYTHONPATH=. python3 projects/signal-contact-activation/contacts-new-role/scripts/classify_new_roles.py \
  --input "data/input/Contacts - Started new role (Past 90 days).xlsx"

# Step 2 — enrich ICP Yes contacts with headcount (requires FIRMABLE_OS_API_KEY in .env)
PYTHONPATH=. python3 projects/signal-contact-activation/contacts-new-role/scripts/enrich_headcount.py \
  --input "projects/signal-contact-activation/contacts-new-role/output/classified_<timestamp>.csv"
```

## Classifier behaviour notes
- **Co-Founder / Owner at a non-B2B company** → classified as No even if the headline mentions other roles. Only the primary `position` column is used for seniority.
- **Business Development Manager** → classified as No unless the headline explicitly contains team leadership language ("leading a team", "managing a team of X", "player-coach", etc.).
- Contacts are processed in batches of 20 (default) to stay within Claude API token limits.
