---
name: normalize-company-names
description: Use this skill to normalise the company_name column in a campaign CSV. Triggers include requests to clean up company names, strip legal suffixes, or prepare a contact list for copy generation.
---

# Company Name Normalisation

## When to use
Run this after the pre-campaign pipeline (`hubspot_eligibility.py`) and before copy generation or SmartLead upload. Company names from Firmable exports often include legal suffixes or long descriptors that look unnatural in email copy.

## What it does
Strips legal suffixes, dot-TLDs, and parenthetical descriptors from `company_name`. Shows a diff of what changed.

Rules applied in order:
1. **Manual overrides** — domain-verified corrections (e.g. "Archer Integrated Risk Management" → "Archer")
2. **Parentheticals** — `LSEG (London Stock Exchange Group)` → `LSEG`
3. **Dot-TLDs** — `H2O.ai` → `H2O`, `Accedo.tv` → `Accedo`
4. **Legal suffixes** — Pte Ltd, Pty Ltd, Sdn Bhd, Limited, Ltd, Inc, Corp, Corporation, LLC, GmbH, PLC, AG, BV, SA, NV, Co. (loops ×3 for stacked suffixes)
5. **Domain check** (optional flag) — for names still ≥3 words, fetches homepage and asks Claude for the short brand name. Prefers the full readable name over generic abbreviations (e.g. "Public Sector Network" not "PSN")

## How to run

```bash
# Standard run (rule-based only)
PYTHONPATH=. python3 scripts/normalize_company_names.py \
  --input campaigns/<region>/<campaign>/data/eligible/eligible_contacts_<ts>.csv

# With domain check for long names
PYTHONPATH=. python3 scripts/normalize_company_names.py \
  --input campaigns/<region>/<campaign>/data/eligible/eligible_contacts_<ts>.csv \
  --check-domains
```

Input CSV must have a `company_name` column. `domain` column required only for `--check-domains`.
Overwrites input by default; use `--output path` to write elsewhere.

## Adding manual overrides
Edit the `OVERRIDES` dict in `scripts/normalize_company_names.py`:
```python
OVERRIDES: dict[str, str] = {
    "Archer Integrated Risk Management": "Archer",
    "Info Tech Research Group": "Info Tech",
    # Add new entries here
}
```

## Campaign workflow position
```
hubspot_eligibility.py (eligible CSV)
→ normalize_company_names.py   ← THIS STEP
→ enrich_persona_region.py
→ copy generation
→ SmartLead upload
```
