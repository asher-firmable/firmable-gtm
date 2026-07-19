# ZoomInfo Displacement — US

## Purpose
Two-email outbound sequence targeting US startups and mid-market companies where ZoomInfo is detected in the tech stack. Email 1 drives a demo booking; Email 2 drives a trial.

## Skill
`.claude/skills/us-competitor-displacement/SKILL.md` — read this before editing any copy or templates.

## What goes in
- `input/` — CSV or Excel exported from Clay after running both AI columns on the company table.
  Required columns: `first_name`, `title`/`job_title`, `email`, `company_name`, `company_niche`, `signal_play_1`, `signal_play_2`.

## What goes out
- `output/` — `copy_<timestamp>.csv` with columns: first_name, email, company, title, persona, company_niche, signal_play_1, signal_play_2, needs_enrichment, email_1_subject, email_1_body, email_1_ps

## Clay setup (run before generate_copy.py)
1. **Company table — Column A (Niche Classifier)**: outputs `company_niche` + `company_icp` from company description.
2. **Company table — Column B (Signal Plays)**: outputs `signal_play_1` + `signal_play_2` from `company_niche` + `company_icp`.

Both Clay prompts are in `.claude/skills/us-competitor-displacement/SKILL.md`.

## Scripts
- `scripts/generate_copy.py` — classifies persona per contact, renders fixed email template with `signal_play_1` + `signal_play_2`, flags rows missing signal columns as `needs_enrichment=True`

## How to run
```bash
PYTHONPATH=. python3 campaigns/us/zoominfo-displacement/scripts/generate_copy.py
```

## Conventions
- Persona detection is rule-based from job title keywords. Uncertain contacts get no copy.
- Rows with empty `signal_play_1` or `signal_play_2` are flagged `needs_enrichment=True` — run Clay columns first.
- This campaign uses US English. Do not adapt copy for AU/NZ audiences.
- HubSpot eligibility check is required before any SmartLead upload — run `scripts/hubspot_eligibility.py` first.
