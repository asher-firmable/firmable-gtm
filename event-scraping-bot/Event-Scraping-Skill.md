# Skill: Event Scraping Bot

## What This Skill Does
Given a conference or event sponsors/exhibitors page URL, this skill:
1. Scrapes the listing (handles infinite scroll, pagination, click-through profiles)
2. Extracts: company name, domain (root domain)
3. Resolves missing LinkedIn URLs via Firecrawl domain-based search
4. Looks up each company in Firmable (LinkedIn URL first, domain fallback)
5. Outputs: `company_name, domain, linkedin_url, firmable_company_id`
6. Then chains through: find contacts → enrich → score → personalise → upload to SmartLead

## Monitoring
If any step fails or produces unexpected output (empty rows, zero Firmable IDs, etc.):
1. Report which step failed and which records were affected
2. Diagnose root cause (API error? Empty HTML? Rate limit?)
3. Propose a fix
4. **Wait for approval before modifying any script**

---

## How to Run

### Step 0 — Scrape sponsors
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "event-scraping-bot/output/EVENT_NAME_raw.csv"
```

### Dry run first (no API calls)
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "event-scraping-bot/output/EVENT_NAME_raw.csv" \
  --skip-linkedin-resolve \
  --skip-firmable
```

### Send to n8n after scraping
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "event-scraping-bot/output/EVENT_NAME_raw.csv" \
  --send-to-n8n
```

### Step 1a — Find contacts
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/1_find_contacts.py \
  --input "event-scraping-bot/output/EVENT_NAME_raw.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_contacts.csv"
```

### Step 1b — Enrich companies
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/1_enrich.py \
  --input "event-scraping-bot/output/EVENT_NAME_raw.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_enriched.csv"
```

### Step 2 — Score leads
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/2_score.py \
  --input "event-scraping-bot/output/EVENT_NAME_enriched.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_scored.csv"
```

### Step 3 — Personalise copy
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/3_personalise.py \
  --input "event-scraping-bot/output/EVENT_NAME_scored.csv" \
  --output "event-scraping-bot/output/EVENT_NAME_personalised.csv"
```

### Step 4 — Upload to SmartLead
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/4_upload_to_smartlead.py \
  --input "event-scraping-bot/output/EVENT_NAME_personalised.csv" \
  --campaign-id CAMPAIGN_ID
```

### Run all steps
```bash
PYTHONPATH=. python3 event-scraping-bot/scripts/run_all.py --project [event_name]
```

---

## Tips for Finding the Right URL
- Use the sponsors/exhibitors sub-page directly, not the homepage
- Common patterns: `/sponsors`, `/partners`, `/exhibitors`, `/sponsors-partners`
- If homepage given, the scraper will try to navigate automatically

---

## What Good Output Looks Like (Step 0)
```
Total exhibitors:   15+
Domain found:       100%
LinkedIn found:     85–100%
Firmable ID found:  85–100%
```
- LinkedIn < 85%: unusual domains or brand names
- Firmable < 85%: companies may be too small or non-APAC

---

## Known Edge Cases

| Issue | Cause | Fix |
|---|---|---|
| Company name shows tier label ("PLATINUM PARTNER") | Logo has empty alt text | Name falls back to domain-derived label; check page HTML |
| Domain shows subdomain (e.g. `aboutus.ft.com`) | "Visit" link points to sub-page | Script auto-strips known junk subdomains; check `_JUNK_SUBDOMAINS` in script if new ones appear |
| Firecrawl timeout | API connection issue | Script retries 3x with backoff automatically |
| Firmable 500 error on LinkedIn URL | Regional LinkedIn URLs (e.g. `uk.linkedin.com`) not supported | Script falls back to domain lookup automatically |
| Missing companies | Cards had empty alt text AND description starts with "Visit" | Add company manually or inspect page HTML |

---

## Scoring Logic
Reference `knowledge/icp-criteria.md` for the full rubric:
- Sales team size (0–25 pts)
- Company type/industry (0–25 pts)
- Sales function signals (0–20 pts)
- Competitive tech stack (0–20 pts)

Tier 1 (70+): priority, call-first if competitive tech detected
Tier 2 (40–69): standard email sequence
Tier 3 (20–39): nurture or hold
DQ (<20): do not contact

Competitive tech detected (ZoomInfo, Apollo, Lusha, Cognism) → always route to competitor displacement track regardless of tier.

---

## Exclusions
Always apply `knowledge/exclusions.md` before scoring or uploading:
- DNC Register flag = exclude from all outreach (legal requirement in AU)
- Existing customers, unsubscribes, competitor orgs

---

## Key Files
- Script: `event-scraping-bot/scripts/0_scrape_exhibitors.py`
- Firmable wrapper: `applications/firmable.py`
- API reference: `knowledge/firmable-api-reference.md`
- ICP scoring: `knowledge/icp-criteria.md`
- Exclusion rules: `knowledge/exclusions.md`
- API keys in `.env`: `FIRMABLE_API_KEY`, `FIRECRAWL_API_KEY`, `SMARTLEAD_API_KEY`, `ANTHROPIC_API_KEY`

---

## How to Use This Skill in a New Session
Tell Claude Code: *"Run the event scraper skill for [event name], the sponsors page is [URL]"*
Claude will read this file and run the workflow from scratch.
