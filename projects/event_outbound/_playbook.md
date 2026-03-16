# Event Outbound Playbook

## Overview
This playbook targets sponsors of a specific event. We scrape the sponsor list, enrich each company via Firmable, score against ICP criteria, generate personalised outreach copy, and upload qualified leads to a SmartLead campaign.

## How to Start a New Campaign
1. Copy the `_template/` folder and rename it to the event (e.g. `gitex_asia_2026/`)
2. Edit `config.json` with the event name, URL, SmartLead campaign ID, and ICP filters
3. Run each step below in order

---

## Steps

### Step 0 — Scrape sponsors
```bash
python workflows/event_outbound/0_scrape_sponsors.py \
  --project projects/event_outbound/gitex_asia_2026
```
- Input: `config.json` (reads `event_url`)
- Output: `data/input/sponsors_raw.csv` (company_name, website, linkedin_url)

### Step 1 — Enrich with Firmable
```bash
python workflows/event_outbound/1_enrich.py \
  --project projects/event_outbound/gitex_asia_2026
```
- Input: `data/input/sponsors_raw.csv`
- Output: `data/output/enriched.csv` (adds Firmable fields: industry, headcount, etc.)

### Step 2 — Score leads
```bash
python workflows/event_outbound/2_score.py \
  --project projects/event_outbound/gitex_asia_2026
```
- Input: `data/output/enriched.csv`
- Output: `data/output/scored.csv` (adds `icp_score`, `qualified` flag)

### Step 3 — Generate personalised copy
```bash
python workflows/event_outbound/3_personalise.py \
  --project projects/event_outbound/gitex_asia_2026
```
- Input: `data/output/scored.csv` (qualified leads only)
- Output: `data/output/personalised.csv` (adds `email_opener` column)

### Step 4 — Upload to SmartLead
```bash
python workflows/event_outbound/4_upload_to_smartlead.py \
  --project projects/event_outbound/gitex_asia_2026
```
- Input: `data/output/personalised.csv`
- Uploads leads to the campaign ID set in `config.json`

### Run all steps at once
```bash
python workflows/event_outbound/run_all.py \
  --project projects/event_outbound/gitex_asia_2026
```

---

## config.json Reference
| Field | Description |
|---|---|
| `event_name` | Display name of the event |
| `event_url` | Homepage URL to scrape sponsors from |
| `smartlead_campaign_id` | SmartLead campaign ID to upload leads into |
| `icp.min_headcount` | Minimum company headcount to qualify |
| `icp.max_headcount` | Maximum company headcount to qualify |
| `icp.target_industries` | List of qualifying industries (empty = all) |
| `icp.target_countries` | List of country codes to target |
| `outreach.sender_name` | Name used in personalised email copy |
| `outreach.value_prop` | One-line value prop for Claude to use in copy |
