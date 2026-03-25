---
name: account-qualification
description: Use this skill whenever you need to check if a company/account is a good fit for Firmable. Triggers include qualifying leads, filtering account lists, checking if a company matches ICP, or evaluating accounts from any data source. Also use when the user uploads a CSV of companies and wants them scored or filtered.
---

# Account Qualification

## Before you start
1. Read `knowledge/icp-definition.md` — current ICP criteria and qualification tiers
2. Read `knowledge/competitors.md` — disqualification signals (locked into multi-year contracts)
3. Read `knowledge/exclusions.md` — DNC rules to apply before scoring
4. Check which region — regional variations apply (ANZ vs US vs SEA)

## Qualification process

### Step 1: Basic firmographic check
For each account, evaluate employee count, industry, and region against the ICP definition.

### Step 2: Sales team signals
Look for indicators of an active sales function: job postings for sales roles, CRM/outbound tool usage, tech stack data.

### Step 3: Disqualification check
Reject if: no sales team evidence, financial distress, already a Firmable customer, below minimum employee threshold, locked into long-term competitor contract.

### Step 4: Score each account
- **A (Strong fit)**: Meets all firmographic criteria + clear sales team signals
- **B (Good fit)**: Meets most criteria, some signals present
- **C (Marginal)**: Meets basic criteria but missing key signals
- **D (No fit)**: Fails disqualification criteria

## Working with CSV data
1. Load CSV with pandas
2. Apply qualification logic row by row
3. Add columns: `fit_score`, `fit_reason`, `disqualification_reason`
4. Save qualified output to `data/qualified/` in the relevant campaign folder
5. Summarise: "X qualified (A: n, B: n, C: n), Y disqualified"

## API enrichment
If data is incomplete, use `scripts/firmable_api.py` to enrich missing fields. Use `scripts/utils.py` → `reason_about()` for reasoning about ambiguous cases.

## When you learn something new
If you notice a qualification pattern that isn't in the ICP definition, propose an update to `knowledge/icp-definition.md`.
