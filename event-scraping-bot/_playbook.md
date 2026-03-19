# Event Outbound Playbook

## Overview
This playbook targets sponsors of a specific event. We scrape the sponsor list, enrich each company via Firmable, score against ICP criteria, generate personalised outreach copy, and upload qualified leads to a SmartLead campaign.

## How to Start a New Campaign
1. Create a `config.json` for the event (use `_template/config.json` as the base if available)
2. Edit `config.json` with the event name, URL, SmartLead campaign ID, and ICP filters
3. Run each step below in order

---

## Steps

### Step 0 — Scrape sponsors
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "event-scraping-bot/output/EVENT_NAME_raw.csv"
```
- Output: `event-scraping-bot/output/EVENT_NAME_raw.csv` (company_name, domain, linkedin_url, firmable_company_id)

### Step 1 — Enrich with Firmable
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/1_enrich.py \
  --input "event-scraping-bot/output/EVENT_NAME_raw.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_enriched.csv"
```
- Output: `enriched.csv` (adds Firmable fields: industry, headcount, etc.)

### Step 2 — Score leads
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/2_score.py \
  --input "event-scraping-bot/output/EVENT_NAME_enriched.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_scored.csv"
```
- Output: `scored.csv` (adds `icp_score`, `qualified` flag)

### Step 3 — Generate personalised copy
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/3_personalise.py \
  --input "event-scraping-bot/output/EVENT_NAME_scored.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_personalised.csv"
```
- Output: `personalised.csv` (adds `email_opener` column)

### Step 4 — Upload to SmartLead
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/4_upload_to_smartlead.py \
  --input "event-scraping-bot/output/EVENT_NAME_personalised.csv" \
  --campaign-id CAMPAIGN_ID
```

### Run all steps at once
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/run_all.py --project [event_name]
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
