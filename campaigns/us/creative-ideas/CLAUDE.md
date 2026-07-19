# US Creative Ideas Campaign

## Purpose
Wide outbound campaign targeting US B2B SMB companies (sales team 4 or fewer). Generates 2-3 personalised Firmable ideas per company via Clay AI enrichment, ready to drop into SmartLead.

## Skill
`.claude/skills/creative-ideas-campaign-us/SKILL.md` — read this before editing any copy, column prompts, or slot logic.

## What goes in
- `input/` — company CSV exported from Firmable. Required columns: `company_name`, `domain`, `description`, `sales_team_size`, `technographics` (optional but enables competitor routing).

## What goes out
- Clay table — `three_ideas_copy` column with bridge_line + idea_1 + idea_2 + idea_3 per row
- SmartLead campaign — assembled from Clay output after HubSpot eligibility check

## How to run
1. Pull US B2B companies from Firmable: sales team <= 4, exclude recruitment vertical
2. Run HubSpot eligibility check: `PYTHONPATH=. python3 scripts/hubspot_eligibility.py`
3. Drop eligible CSV into `input/`
4. Build Clay table following the 8-column order in the skill
5. Spot-check Column 8 on 10-15 rows before running full table
6. Upload to SmartLead after confirming lead count, campaign name, and sender

## Conventions
- US English only. No ANZ/APAC references.
- Input CSVs go in `input/` (gitignored)
- Output CSVs go in `output/` (gitignored)
- Run scripts from repo root with `PYTHONPATH=.`
