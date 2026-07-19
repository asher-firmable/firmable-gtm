# US Founding 100 — SaaS Segment

## Purpose
Enrich SaaS companies from the US Founding 100 list with Firmable descriptions.

## What goes in
CSV with `Firmable Company ID` and `Company Domain` columns. Drop in `input/`.

## What goes out
`company_with_descriptions_<timestamp>.csv` in `output/` — same columns as input plus a `description` column.

## How to run

```bash
PYTHONPATH=. python3 campaigns/us/founding-100/saas/scripts/enrich_descriptions.py \
  --file "campaigns/us/founding-100/saas/input/<file>.csv"
```

Test on first 10 rows:
```bash
PYTHONPATH=. python3 campaigns/us/founding-100/saas/scripts/enrich_descriptions.py \
  --file "campaigns/us/founding-100/saas/input/<file>.csv" \
  --limit 10
```

## Conventions
- Run from repo root with `PYTHONPATH=.`
- Input CSVs are gitignored; only `.gitkeep` is committed
- Output CSVs are gitignored
