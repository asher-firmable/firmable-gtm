# Signal — Contact Activation (Sub-Agent)

## Purpose
Classify and activate contacts surfaced by buying signals. Each sub-folder represents a distinct signal type — contacts are run through the ICP classifier and output a scored CSV ready for outreach.

## Sub-signals

| Folder | Signal | Run Command |
|--------|--------|-------------|
| `contacts-new-role/` | Contacts who started a new role in the past 90 days | `PYTHONPATH=. python3 projects/signal-contact-activation/contacts-new-role/scripts/classify_new_roles.py --input data/input/<file>.csv` |

## Conventions
- Each sub-signal has its own `CLAUDE.md`, `scripts/`, and `output/` folder.
- Import `classify_contacts` from `scripts/classifier.py` — never duplicate classifier logic.
- Classification is based on the contact's primary `position` (title) only. Headline is passed as `summary` solely to support the BDM ambiguity check (team leadership evidence), not to infer secondary roles.
- Output files are gitignored. Never commit classified CSVs.
- Requires `ANTHROPIC_API_KEY` in `.env`.
