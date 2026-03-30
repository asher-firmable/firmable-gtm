---
name: enrich-persona-region
description: Use this skill to add persona and region columns to a campaign CSV. Triggers include requests to find what persona a company targets, determine geographic scope from contact titles, or prepare custom fields for email copy personalisation.
---

# Persona & Region Enrichment

## When to use
Run this after company name normalisation and before copy generation. Adds two custom fields used in subject lines and email body personalisation (e.g. "find {persona} leaders in {region}").

## What it adds

| Column | Description | Example |
|---|---|---|
| `persona` | Type of leader this company sells to (1-2 words, slash-separated if multiple) | `Cybersecurity`, `Finance/Risk`, `HR` |
| `region` | Geographic scope from the contact's position + headline | `APAC`, `SEA`, `ASEAN`, `ANZ`, `APJ` |

## Region logic (parsed from position + headline)
| Condition | Returns |
|---|---|
| SEA + ANZ in same text | APAC |
| ASEAN + ANZ in same text | APAC |
| ASEAN | ASEAN |
| SEA / South-East Asia | SEA |
| ANZ | ANZ |
| APJ | APJ |
| APAC / Asia Pacific | APAC |
| Nothing found | APAC (default) |

## Persona logic
- Fetches each unique company's homepage (one call per domain, cached)
- Asks Claude: "What type of professional leader does this company sell to? 1-2 words."
- Multiple words joined with `/` (e.g. `Finance/Risk`)
- Falls back gracefully if domain is unreachable

## How to run

```bash
PYTHONPATH=. python3 scripts/enrich_persona_region.py \
  --input campaigns/<region>/<campaign>/data/eligible/eligible_contacts_<ts>.csv
```

Input CSV must have: `company_name`, `domain`, `position`, `headline` columns.
Overwrites input by default; use `--output path` to write elsewhere.

## Campaign workflow position
```
hubspot_eligibility.py (eligible CSV)
→ normalize_company_names.py
→ enrich_persona_region.py   ← THIS STEP
→ copy generation
→ SmartLead upload
```
