# Qualify a List

1. Ask which campaign this is for (to find the right `campaigns/[region]/[name]/` folder)
2. Ask if a CSV is ready in `data/raw/` or if they need to upload one
3. Ask: account qualification, contact validation, or both?
4. Read `knowledge/icp-definition.md` and `knowledge/persona-definitions.md` before proceeding
5. Read `knowledge/exclusions.md` — apply DNC rules before scoring

## Account Qualification
Use the `.claude/skills/account-qualification/SKILL.md` skill.
- Input: raw account CSV
- Output: save to campaign's `data/qualified/` with `fit_score`, `fit_reason`, `disqualification_reason` columns
- Summarise: "X qualified (A: n, B: n, C: n), Y disqualified"

## Contact Validation
Use the `.claude/skills/contact-validation/SKILL.md` skill.
- Input: qualified accounts
- Output: save to campaign's `data/validated/` with `persona_tier`, `persona_type`, `validation_notes` columns
- Use `scripts/classifier.py` → `classify_contacts()` for ICP classification

## After qualifying
- Show summary of results
- Ask: "Based on what we filtered, should we update any ICP or persona criteria in the knowledge files?"
- If yes, propose the specific update to `knowledge/icp-definition.md` or `knowledge/persona-definitions.md`
- Ask: "Want me to commit these results to Git?"

## References
- Classifier: `scripts/classifier.py`
- ICP criteria: `knowledge/icp-definition.md`
- Persona definitions: `knowledge/persona-definitions.md`
- DNC rules: `knowledge/exclusions.md`
- Account qualification skill: `.claude/skills/account-qualification/SKILL.md`
- Contact validation skill: `.claude/skills/contact-validation/SKILL.md`
