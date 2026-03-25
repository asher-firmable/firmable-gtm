---
name: contact-validation
description: Use this skill to validate whether contacts are the right personas to target. Triggers include checking titles, validating contact lists, filtering by seniority or role, or scoring contacts against persona definitions.
---

# Contact Validation

## Before you start
1. Read `knowledge/persona-definitions.md` — current persona criteria by segment
2. Read `knowledge/exclusions.md` — DNC rules (always apply first)
3. Determine target segment (Enterprise/Mid-Market/SMB) from account size
4. Check region — title conventions vary (ANZ vs US vs SEA)

## Validation process

### Step 1: DNC check
Apply `knowledge/exclusions.md` rules. Remove any contacts that are on DNC or exclusion lists before further processing.

### Step 2: Segment determination
500+ employees → Enterprise | 50–500 → Mid-Market | 20–50 → SMB

### Step 3: Title matching
Compare against persona definitions. Use fuzzy matching — titles are not standardised.
Common equivalences: "Head of" ≈ "Director of" ≈ "VP of" (size-dependent).

### Step 4: Seniority validation
Cross-reference title with company size. A "VP" at 30 people ≠ "VP" at 500 people.
Use the BDM ambiguity rule from `knowledge/icp-definition.md`.

### Step 5: Regional adjustments
Apply regional rules from `knowledge/persona-definitions.md`.

### Step 6: Categorise
- **T1 (Target)**: Primary buyer persona
- **T2 (Target)**: Champion/influencer persona
- **M (Maybe)**: Ambiguous title — flag for manual review
- **S (Skip)**: Anti-persona, wrong seniority, or DNC

## For large lists
Use `scripts/classifier.py` → `classify_contacts()` for batch AI-powered classification. This runs a two-pass approach: initial classification, then website fetch for low-confidence cases.

## CSV output
Add columns: `persona_tier`, `persona_type`, `validation_notes`
Save to campaign's `data/validated/` folder.

## When you learn something new
Propose updates to `knowledge/persona-definitions.md`.
