# Skill: Event Exhibitor Scraper → Firmable ID Lookup

## What This Does
Given a conference or event website URL, this skill:
1. Scrapes the exhibitors/sponsors listing (handles infinite scroll, pagination, click-through profiles)
2. Extracts: company name, domain (root domain, not subdomains)
3. Resolves missing LinkedIn URLs via Firecrawl domain-based search
4. Looks up each company in Firmable (LinkedIn URL first, domain fallback)
5. Outputs a single clean CSV: `company_name, domain, linkedin_url, firmable_company_id`

## How to Run

### Step 1 — Navigate to project root
```bash
cd "/Users/asherchua/Desktop/Claude Code/Firmable GTM Engineering"
```

### Step 2 — Full pipeline (recommended)
```bash
PYTHONPATH=. python3 workflows/event_outbound/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "data/output/EVENT_NAME.csv"
```

### Dry run first (scraping only, no API calls)
```bash
PYTHONPATH=. python3 workflows/event_outbound/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "data/output/EVENT_NAME.csv" \
  --skip-linkedin-resolve \
  --skip-firmable
```

## Tips for Finding the Right URL
- Give the **sponsors/exhibitors sub-page** directly, not the homepage
- Common patterns: `/sponsors`, `/partners`, `/exhibitors`, `/sponsors-partners`
- If you give the homepage, the scraper will try to find the right page automatically

## What Good Output Looks Like
```
Total exhibitors:   15+
Domain found:       100%
LinkedIn found:     85–100%
Firmable ID found:  85–100%
```
- LinkedIn < 85%: some companies may have unusual domains or brand names
- Firmable < 85%: companies may be too small or non-APAC to be in Firmable

## Known Edge Cases & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Company name shows tier label ("PLATINUM PARTNER") | Logo has empty alt text and no description text | Check the page HTML; name falls back to domain-derived |
| Domain shows subdomain (e.g. `aboutus.ft.com`) | "Visit" link on the page points to a sub-page | Script auto-strips known junk subdomains; check `_JUNK_SUBDOMAINS` in the script if a new one appears |
| Firecrawl timeout | API connection issue | Script retries up to 3x with backoff automatically |
| Firmable 500 error on LinkedIn URL | Firmable doesn't support regional LinkedIn URLs (e.g. `uk.linkedin.com`) | Script falls back to domain lookup automatically |
| Missing companies (page had more than CSV shows) | Cards had both empty alt text AND description starts with "Visit" | Add company manually or check the page HTML |

## Output File
- Saved to `data/output/` with the name you specify in `--output`
- Columns: `company_name`, `domain`, `linkedin_url`, `firmable_company_id`
- Empty string if not found — never blank-errored rows

## Key Files
- Script: `workflows/event_outbound/0_scrape_exhibitors.py`
- Firmable wrapper: `utils/firmable.py` — `lookup_company(domain)`, `search_by_linkedin(url)`
- API reference: `research/firmable_api_reference.md`
- API keys in `.env`: `FIRMABLE_API_KEY`, `FIRECRAWL_API_KEY`

## Sending to n8n

Add `--send-to-n8n` to POST all rows to the webhook defined in `N8N_WEBHOOK_URL` in `.env`:

```bash
PYTHONPATH=. python3 workflows/event_outbound/0_scrape_exhibitors.py \
  --url "EVENT_SPONSORS_PAGE_URL" \
  --output "data/output/EVENT_NAME.csv" \
  --send-to-n8n
```

Payload sent:
```json
{ "companies": [ { "company_name": "...", "domain": "...", "linkedin_url": "...", "firmable_company_id": "..." }, ... ] }
```

**Important:** Use the production webhook URL (`/webhook/...`), not the test URL (`/webhook-test/...`).
The test URL only works when you're actively listening in the n8n editor.

---

## Next Steps After This CSV
This CSV feeds into the rest of the event outbound playbook:
- **Step 1** (`1_find_contacts.py`) — find sales contacts at each company via Firmable People Search
- **Step 2** (`2_enrich.py`) — pull full Firmable enrichment (industry, headcount, country, description)
- **Step 3** (`3_score.py`) — ICP fit scoring
- **Step 4** (`4_personalise.py`) — Claude-powered email openers
- **Step 5** (`5_upload_to_smartlead.py`) — upload to SmartLead campaign

### Run Step 1 (find contacts)
```bash
PYTHONPATH=. python3 workflows/event_outbound/1_find_contacts.py \
  --input "data/output/EVENT_NAME.csv" \
  --output "data/output/EVENT_NAME_contacts.csv"
```

## How to Use This Skill in a New Session
Tell Claude Code: *"Run the event scraper skill for [event name], the sponsors page is [URL]"*
Claude will read this file and run the workflow from scratch with a clean context.
