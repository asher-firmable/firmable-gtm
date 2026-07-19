# US Influencer Outreach — Sub-Agent

## Purpose
Classify US sales influencers into outreach buckets and generate personalised first-draft emails for Firmable's US market expansion.

## What goes in
A CSV dropped into `input/` containing at minimum: name, LinkedIn URL, current title, company. Optional useful columns: follower count, headline, bio, experience summary.

## What goes out
1. `output/classified.csv` — original columns + `product_feedback`, `warm_intro`, `influencer` (True/False), `classification_reasoning`
2. `output/with_copy.csv` — classified columns + `copy_product_feedback`, `copy_warm_intro`, `copy_influencer` (blank if not assigned)

## Scripts

| Script | Purpose |
|---|---|
| `scripts/enrich_and_classify.py` | Step 1: classify each person into 1-3 buckets using Claude |
| `scripts/generate_copy.py` | Step 2: generate personalised first-draft email per assigned bucket |

## How to run

```bash
# From repo root
PYTHONPATH=. python3 projects/us-influencer-outreach/scripts/enrich_and_classify.py
PYTHONPATH=. python3 projects/us-influencer-outreach/scripts/generate_copy.py
```

## Buckets

**product_feedback** — Person can give informed feedback on a US sales intelligence product.
Signals: VP Sales, CRO, Head of Sales, RevOps, Sales Ops, Sales Director; prior experience at sales tech companies (ZoomInfo, Outreach, Salesloft, Gong, Apollo, etc.)

**warm_intro** — Person has a broad professional network and can open doors to potential US customers.
Signals: Advisor roles, fractional CRO/exec, sales consultant, partner at advisory firm, founder/CEO with cross-company network breadth

**influencer** — Person has reach and audience in the sales/revenue community.
Signals: LinkedIn follower count >5,000, sales coach/trainer, speaker, author, podcast host, content creator with SDR/RevOps audience

A person can be assigned to multiple buckets. At least one bucket is always assigned.

## Copy CTA per bucket

- product_feedback: 20-minute product feedback call
- warm_intro: soft ask for introductions to their network
- influencer: content angle / collab conversation

## Conventions
- Classification is based purely on CSV data — no external API calls
- Input CSV column names are auto-normalised to lowercase snake_case by `load_csv`
- The script handles any column layout; all non-empty fields are passed to Claude as context
- Copy is signed from Asher; no em dashes, no bullet points, max ~100 words per email body
