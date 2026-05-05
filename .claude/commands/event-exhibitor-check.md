# Event Exhibitor Check

Run this whenever you have a list of event exhibitors and want a full HubSpot + Firmable enrichment overview. Works for any ANZ (or other region) event.

The output is a `hubspot_check.csv` with 15 columns plus a live preview table in chat:
- Exists in HubSpot (YES/NO)
- Found in Firmable (YES/NO)
- Company name, website, HubSpot URL
- Company owner, SDR (AU/NZ/SEA)
- Outreach Engagement Status (AU + SEA)
- Sales Team Size (AU/NZ/SEA) — real-time from Firmable
- Last Contacted (DD Mon YYYY)

---

## Step 1 — Identify the input

The user will give you one of:

**A) An event URL** (e.g. `https://sectechroadshow.com.au/exhibitors-sectech/`)
→ Ask: "What should I call this event folder? (e.g. `SecTech-Roadshow-Australia`)"
→ Scrape the exhibitor page using Playwright or requests+BeautifulSoup (check if JS-rendered first)
→ Save the result as `campaigns/anz/events-outbound/<EventFolder>/output/exhibitors.csv` with columns `name`, `website`
→ Continue to Step 2.

**B) A CSV file path** already containing company names + domains
→ Ask: "What should I call this event folder?" if no folder exists yet
→ Use the CSV directly as the `--input` for `hubspot_check.py` — no pre-processing needed as long as it has a recognisable domain column (`website`, `domain`, `company_website`, or `url`)
→ Continue to Step 2.

**C) A typed/pasted list** of company names and domains
→ Ask: "What should I call this event folder?"
→ Write the list to `campaigns/anz/events-outbound/<EventFolder>/output/exhibitors.csv` with columns `name`, `website`
→ Continue to Step 2.

---

## Step 2 — Create the folder structure

```
campaigns/anz/events-outbound/<EventFolder>/
├── output/
│   ├── exhibitors.csv       ← input for the check
│   └── hubspot_check.csv    ← enriched output (written by script)
```

Create the folder and `output/` subdirectory if they don't exist yet.

---

## Step 3 — Run the HubSpot + Firmable check

```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  campaigns/anz/events-outbound/<EventFolder>/output/exhibitors.csv \
  --output campaigns/anz/events-outbound/<EventFolder>/output/hubspot_check.csv
```

The script handles:
- Domain normalisation (strips protocol, path, www.)
- HubSpot lookup: exact domain EQ first, CONTAINS_TOKEN SLD fallback
- Real-time Firmable sales team size (AU/NZ/SEA)
- Owner ID → name resolution
- Date formatting (DD Mon YYYY)

---

## Step 4 — Show the preview table

After the script finishes, display all rows as a markdown table with these columns:

| In HS | In Firmable | Company Name | Website | Company Owner | SDR (AU) | SDR (NZ) | SDR (SEA) | Engagement Status | Engagement Status (SEA) | Sales Team AU | Sales Team NZ | Sales Team SEA | Last Contacted |

Then report the summary line:
> **HubSpot: X/Y found | Firmable: X/Y found** → `output/hubspot_check.csv`

---

## Notes

- Script: `campaigns/anz/events-outbound/hubspot_check.py`
- The script auto-detects the name column (`name`, `company_name`, `company`) and domain column (`website`, `domain`, `company_website`, `url`) — no fixed column names required in the input CSV.
- Companies not found in HubSpot or Firmable still appear in the output with YES/NO flags and blank enrichment fields.
- If the same event has been run before, re-running will overwrite `hubspot_check.csv` with fresh data.
- For SEA or US events, the same script works — just change the output folder path accordingly.
- Rate: ~0.2s per company for HubSpot + Firmable combined. Expect ~1 min for 30 companies.
