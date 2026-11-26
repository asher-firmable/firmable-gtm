# Event Exhibitor Check

Run this whenever you have a list of event exhibitors and want a full HubSpot + Firmable enrichment overview. Works for any ANZ (or other region) event.

The output is a `hubspot_check.csv`, a live preview table in chat, a categorized summary breakdown, an `eligible_companies.csv` export, and a combined Excel workbook covering every exhibitor (eligible + ineligible) with these fields — this is the standard field set for every event scrape as of 2026-09-17, not just a one-off:
- Exists in HubSpot (YES/NO)
- Found in Firmable (YES/NO)
- Company name, website, HubSpot URL, Firmable ID (linked to `https://app.firmable.com/dashboard/company/{id}`)
- Tier, Stand (from the scrape, if the event has sponsor tiers/booth numbers)
- Status (Eligible/Ineligible) + Reason — computed by `hubspot_check.py` itself per the priority order below, not derived separately in chat
- Company Owner, Company Owner (ANZ) — HubSpot `company_owner_nz`, Company Owner (SEA) — HubSpot `company_owner_sea`
- SDR (AU/NZ/SEA)
- Outreach Engagement Status (AU + SEA)
- Customer Status, ICP Match (ANZ), ICP Match (SEA) (HubSpot `icp_match_anz` / `icp_match_sea`, enum values mapped to labels), Open Deal (YES/NO) + Deal Owner (owner of the open deal, may differ from Company Owner)
- Sales Team Size (AU/NZ/SEA/US) — real-time from Firmable, plus a computed ANZ Sales Team Size (AU+NZ summed)
- HQ Country — Firmable `hq_country` (**not** `country` — see Notes)
- Last Contacted (DD Mon YYYY)

**All of the above is fetched or computed by `hubspot_check.py` in ONE pass** (rewritten 2026-09-17) — there is no longer a separate follow-up enrichment step. If a required field is ever missing from `hubspot_check.csv`, extend the script itself; don't re-patch it per event.

---

## Step 1 — Identify the input

The user will give you one of:

**A) An event URL** (e.g. `https://sectechroadshow.com.au/exhibitors-sectech/`)
→ Ask: "What should I call this event folder? (e.g. `SecTech-Roadshow-Australia`)"
→ Scrape the exhibitor page using Playwright or requests+BeautifulSoup (check if JS-rendered first)
→ Save the result as `<region-events-folder>/<EventFolder>/output/exhibitors.csv` with columns `name`, `website` (`<region-events-folder>` = `campaigns/anz/events-outbound` for ANZ, `campaigns/sea-conferences` for SEA, `campaigns/us/events-outbound` for US)
→ Continue to Step 2.

**B) A CSV file path** already containing company names + domains
→ Ask: "What should I call this event folder?" if no folder exists yet
→ Use the CSV directly as the `--input` for `hubspot_check.py` — no pre-processing needed as long as it has a recognisable domain column (`website`, `domain`, `company_website`, or `url`)
→ Continue to Step 2.

**C) A typed/pasted list** of company names and domains
→ Ask: "What should I call this event folder?"
→ Write the list to `<region-events-folder>/<EventFolder>/output/exhibitors.csv` with columns `name`, `website` (`<region-events-folder>` = `campaigns/anz/events-outbound` for ANZ, `campaigns/sea-conferences` for SEA, `campaigns/us/events-outbound` for US)
→ Continue to Step 2.

---

## Step 2 — Create the folder structure

```
<region-events-folder>/<EventFolder>/
├── output/
│   ├── exhibitors.csv       ← input for the check
│   └── hubspot_check.csv    ← enriched output (written by script)
```

Create the folder and `output/` subdirectory if they don't exist yet.

---

## Step 3 — Run the HubSpot + Firmable check

```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/hubspot_check.py \
  --input  <region-events-folder>/<EventFolder>/output/exhibitors.csv \
  --output <region-events-folder>/<EventFolder>/output/hubspot_check.csv
```

The script handles, all in one pass:
- Domain normalisation (strips protocol, path, www.)
- HubSpot lookup: exact domain EQ first, CONTAINS_TOKEN SLD fallback
- Real-time Firmable sales team size (AU/NZ/SEA/US, one `get_sales_team_size` call) + HQ country (from the same `lookup_company` response — no extra call)
- Company Owner, Company Owner (ANZ), Company Owner (SEA), SDR (AU/NZ/SEA) — resolved via the owner map
- Open Deal + Deal Owner — one associated-deals lookup per company
- Next-step-scheduled check — one associated-tasks lookup, but only for companies with an SDR assigned that are otherwise clear of the customer/trial and open-deal rules (recently contacted companies are still checked) (keeps the extra API calls scoped to the companies where it actually matters)
- Status/Reason — computed directly per the priority order in Step 5
- Owner ID → name resolution
- Date formatting (DD Mon YYYY)

Tier/Stand are passed through unchanged from the input CSV's own `tier`/`category` and `stand`/`booth`/`booth_number` columns, if present — nothing to fetch for those.

---

## Step 4 — Show the preview table

After the script finishes, display all rows as a markdown table with these columns:

| In HS | In Firmable | Company Name | Website | Company Owner | Company Owner (ANZ) | Company Owner (SEA) | SDR (AU) | SDR (NZ) | SDR (SEA) | Engagement Status | Engagement Status (SEA) | Sales Team AU | Sales Team NZ | Sales Team SEA | Sales Team US | ANZ Sales Team Size | HQ Country | Last Contacted |

Then report the summary line:
> **HubSpot: X/Y found | Firmable: X/Y found** → `output/hubspot_check.csv`

---

## Step 5 — Categorized summary breakdown

`hubspot_check.py` now computes `status` (Eligible/Ineligible) and `reason` directly — **read these two columns rather than re-deriving the priority logic in chat.** The script's `reason` string already names which rule the row failed (e.g. "Already customer or trialing (Trialing Customer)", "Open deal", "Next step scheduled (due DATE)", "No Firmable match"), in priority order (customer/trial → open deal → next step scheduled → no Firmable match, first match wins — see `campaigns/anz/events-outbound/CLAUDE.md` for the exact rule set). Group rows by their `reason` value to build each bucket below — do not recompute `customer_status`/`open_deal`/`last_contacted` cutoffs by hand; the CSV is the source of truth for status/reason now.

Always present this breakdown in **list format** (not tables — the user wants to copy/paste names straight out), with a horizontal rule (`---` on its own line) between every section and sub-section — the user copies this straight into a Slack channel.

**Structure as two top-level headers, Ineligible then Eligible — not one flat numbered list.** Every `reason` value groups together under Ineligible (in the priority order above); everything with `status == Eligible` appears under Eligible. Because `reason` is now assigned by the script using strict priority order, no company can appear under more than one bucket — no dedup logic needed on the chat side.

### Ineligible — grouped by `reason`

- **Already customer or trialing**: list as `Company (Status — owner: company_owner)`.
- **Open deal**: list as `Company (owner: deal_owner)`.
- **Next step scheduled**: list as `Company (reason text already includes the due date — SDR: whichever of sdr_au/sdr_nz/sdr_sea is non-empty)`.
- **No Firmable match**: plain comma-separated list. Treat as ineligible-until-manually-checked, not a hard permanent exclusion — say so explicitly.

### Eligible — split into two segments

- **Not in HubSpot, matched in Firmable** (`exists_in_hubspot == NO`) — automatically eligible. Plain comma-separated list.
- **In HubSpot, clear of all Ineligible reasons** (`exists_in_hubspot == YES`, `status == Eligible`) — split further into:
  - With an SDR assigned (`sdr_au`/`sdr_nz`/`sdr_sea` non-empty) — list as `Company (SDR name)`.
  - No SDR assigned — plain comma-separated list.
- **Eligible, contacted in last 30 days (note)** — `status == Eligible` and `reason` starts with "Contacted in last 30 days". Since 2026-11-12 recent contact no longer makes a company ineligible; it is a heads-up note only. Pull these out of the two segments above into their own sub-group, listed as `Company (last contact DATE — SDR/owner if any)`, so the reader can check who touched them before reaching out.

### Overall numbers

- Total sponsors scraped
- Ineligible counts per `reason` value + the no-Firmable-match count
- Eligible total, broken into: not-in-HubSpot count + in-HubSpot count (with-SDR / no-SDR split)
- **Always spell out the eligibility definition explicitly** — don't just give the number. State it as a criteria list, e.g.:
  "Eligible = found in Firmable AND not an active customer/trial AND no open deal AND (if an SDR is assigned) no scheduled next step. Companies contacted in the last 30 days are still eligible, flagged with a note."
  Repeat this every run, not just the first time — the reader may not have the full thread of prior turns in front of them.
- Always caveat: this is the tier-1 screen only — it does not run `scripts/hubspot_eligibility.py`'s full contact-level active-task/sequence check, which is required before any actual SmartLead upload

## Step 6 — Export the eligible list to CSV

Always write every row with `status == "Eligible"` to:

```
<region-events-folder>/<EventName>/output/eligible_companies.csv
```

Columns: `company_name, company_website, exists_in_hubspot, found_in_firmable, firmable_id, company_owner, sdr_au, sdr_nz, sdr_sea, customer_status, open_deal, sales_team_au, sales_team_nz, sales_team_sea, sales_team_us, sales_team_anz, hq_country, last_contacted, reason, eligibility_reason` — where `reason` is blank or the recent-contact note, and `eligibility_reason` is `in_hubspot_eligible` (`exists_in_hubspot == YES`) or `net_new_not_in_hubspot` (`exists_in_hubspot == NO`). `firmable_id` lets the reader build a direct link (`https://app.firmable.com/dashboard/company/{id}`) without re-searching.

Do this automatically once the Step 5 breakdown is produced — don't wait to be asked again.

This CSV predates the combined Excel workbook (Step 7) and is now the secondary deliverable — keep producing it (some workflows still consume it directly), but the xlsx is the one to point the user to first.

---

## Step 7 — Build the combined Excel workbook (standard deliverable, do this automatically)

Build this every run, not just when asked — it is the primary deliverable, covering every exhibitor (eligible **and** ineligible) in one file with `status` + `reason` computed, rather than the eligible-only CSV from Step 6.

**Script:** `campaigns/anz/events-outbound/build_workbook.py` (shared, same pattern as `hubspot_check.py`) — reads `hubspot_check.csv`, dedupes, formats, writes the xlsx. Formatting/column logic lives in this script now, not re-implemented ad hoc per event.

```bash
PYTHONPATH=. python3 campaigns/anz/events-outbound/build_workbook.py \
  --input  <region-events-folder>/<EventFolder>/output/hubspot_check.csv \
  --output "<region-events-folder>/<EventFolder>/output/<name>.xlsx"
```

Default filename convention is `<event_slug>_exhibitors.xlsx`, one sheet, one row per deduped exhibitor — but if the user gives an explicit name for the file, use that instead (pass it straight through as `--output`).

**Column order** (as implemented in `build_workbook.py`): Company Name, Domain, Tier, Stand, Status, Reason, In HubSpot, In Firmable, Firmable ID, HubSpot Link, Company Owner, Company Owner (ANZ), Company Owner (SEA), SDR AU, SDR NZ, SDR SEA, Engagement Status (AU), Engagement Status (SEA), Customer Status, ICP Match (ANZ), ICP Match (SEA), Open Deal, Deal Owner, Sales Team AU, Sales Team NZ, Sales Team SEA, Sales Team US, Last Contacted, ANZ Sales Team Size, HQ Country. (Company Owner (ANZ)/(SEA) sit immediately after Company Owner, not at the end — confirmed placement. Note: an earlier draft of this doc listed "SEA Sales Team Size" a second time near the end alongside "US Sales Team Size" — that was a duplicate of the "Sales Team SEA" column already listed earlier and has been corrected here; there is only one SEA sales-team-size field in `hubspot_check.csv`.)

**Formatting (openpyxl), all handled by the script:**
- Bold white header row on a dark fill, frozen (`freeze_panes = "A2"`), autofilter over the full range.
- Row fill: light green for `Status == "Eligible"`, light red/pink otherwise — applied across the whole row, not just the status cell.
- `Firmable ID` is a hyperlink to `https://app.firmable.com/dashboard/company/{id}`.
- `HubSpot Link` cell text is replaced with "Open in HubSpot" and hyperlinked to the stored URL.
- Reasonable column widths per field (name/reason columns wider, flag/status columns narrow) — don't leave default width, it truncates badly at this row count.

**Dedup:** the script drops exact `(company_name, company_website)` duplicates, keeping the first occurrence, before writing any rows — this happens on some event platforms (the same company double-listed under two slugs).

`hubspot_check.csv` alone has every field needed for the workbook (Tier/Stand/Status/Reason included) — no need to separately merge in `exhibitors.csv`. If a rebuild is needed after the first pass (a new column requested, a field corrected), rebuild the whole workbook from `hubspot_check.csv` via the script rather than trying to patch the existing xlsx in place — simpler and less error-prone than editing a saved workbook.

If the user has the file open in Excel when you go to rebuild it, the save may fail or (if they've filtered + edited + saved over it themselves) the file on disk may no longer match what you last wrote — read it back and check row count against what you expect before assuming it's stale versus intentionally edited; ask if unsure rather than silently overwriting their edits.

---

## Notes

- Script: `campaigns/anz/events-outbound/hubspot_check.py`
- The script auto-detects the name column (`name`, `company_name`, `company`) and domain column (`website`, `domain`, `company_website`, `url`) — no fixed column names required in the input CSV.
- Companies not found in HubSpot or Firmable still appear in the output with YES/NO flags and blank enrichment fields.
- If the same event has been run before, re-running will overwrite `hubspot_check.csv` with fresh data.
- For SEA or US events, the same script works — just change the output folder path accordingly.
- Rate: HubSpot alone is close to the old "~0.2s per company" estimate, but once Firmable calls and Step 3b's extra enrichment passes are included, a several-hundred-company event can take 30+ minutes total, sometimes much longer if Firmable's API is slow that day. Don't assume a hang from silence alone — check `ps` CPU time and `lsof` connections (a live/changing connection with near-zero CPU means it's waiting on a slow response, not stuck) before killing and restarting a long-running background enrichment pass, since restarting loses all progress.
- **Firmable field name gotcha:** the company profile's HQ country field is `hq_country`, not `country` (the latter doesn't exist on the response — `knowledge/firmable-api-reference.md` was wrong about this and has been corrected). Double-check field names against a live API response rather than trusting the docs blindly if a new field comes back empty for every row.
- **Timeout:** `FirmableClient._get`/`_post` in `scripts/firmable_api.py` now have a 30s timeout (added 2026-09-15) — previously a hung Firmable connection could block a run indefinitely with no way to recover except killing the process.
- **Re-scraping a previously-run event:** exhibitor lists grow over time (new registrations). If the scraper hardcodes a page count for a paginated listing, check the site's actual pagination widget for the current last page rather than trusting the old constant — sites can add pages between runs.
- When multiple follow-up enrichment scripts read-modify-write the same `hubspot_check.csv`, run them strictly in sequence. Launching them as parallel background tasks causes a write race where the second script's read (missing the first script's not-yet-written columns) clobbers the first script's output on save.
