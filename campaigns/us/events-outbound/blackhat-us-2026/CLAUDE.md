## Purpose
Scrape the Black Hat US 2026 sponsor list into a CSV of company name, domain, sponsor tier, and Firmable company ID for US outbound targeting.

## What goes in
- Sponsor list page: https://blackhat.com/us-26/event-sponsors.html

## What goes out
- `output/exhibitors.csv` — `company_name`, `domain`, `sponsor_type`, `firmable_id` columns; one row per sponsor

## Scripts / tools
| Script | Purpose |
|---|---|
| `scrape_exhibitors.py` | Playwright scraper — loads page (bypasses Cloudflare), parses sponsor tiers + links, normalises domains, enriches with Firmable IDs |
| `scripts/1_classify_use_case.py` | Classifies each company against the 10 use-case categories in `reference/use_case_signals.json` (description first, Firecrawl homepage fallback if description is too thin). Pulls `example_detections` verbatim from the matched row — never invents tech names. |
| `scripts/2_generate_copy.py` | Generates the 2-email sequence per contact via `ask_claude`, using the 3 source angles below as style reference (not templates) |
| `scripts/3_contact_overview.py` | Read-only: prints per-company contact counts from the curated CSV in `input/`, sorted descending, flagging companies over the 15-contact cap |
| `scripts/4_trim_contacts.py` | Trims companies over 15 contacts down to 15, prioritizing US West Coast location first, then title tier (SDR/BDR/BD/Inside Sales practitioners > C-suite > Head of Sales > Director/VP > Manager > everyone else). Writes both a trimmed file and a dropped file — never silently discards rows. See script docstring for the full tier logic. |

## Run command
```bash
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py
```

Inspect rendered HTML without running Firmable lookups:
```bash
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scrape_exhibitors.py --debug
```

Outreach pipeline (run after dropping the curated contact CSV into `input/`):
```bash
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/3_contact_overview.py       # see per-company counts first
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/4_trim_contacts.py           # trim companies over 15 contacts
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/1_classify_use_case.py --limit 10   # sample batch first
PYTHONPATH=. python3 campaigns/us/events-outbound/blackhat-us-2026/scripts/2_generate_copy.py --limit 10
# review output/2_copy_<timestamp>.csv, then re-run both without --limit for the full list
```

## Conventions
- Output writes to `output/` (gitignored)
- `sponsor_type` is the raw tier heading text from the page (e.g. "Titanium Sponsors", "Platinum Plus")
- Domains are bare (no `www.`, no `https://`)
- Rows with no domain are still included — no data is silently dropped
- Firmable IDs are blank if no match found for the domain

## Outreach campaign (input/, reference/, scripts/)

**What goes in** — `input/`: the user's curated CSV of targeted companies + contacts (head of sales + ICs), with company description and domain/website. This is a manually filtered subset of `output/exhibitors.csv`, not the full 451 sponsors — dropped in by the user, not scraped.

**Reference data** — `reference/use_case_signals.json`: the 10 use-case categories from the Notion "For Asher" doc (blackhat-specific technographic use cases: AI adopters, AppSec/supply chain, legacy identity, firewall/network-gear displacement, cloud security, data security, endpoint, email/domain security, OT/industrial, machine identity/certs), each with a buyer persona and a pre-approved `example_detections` list. Classification must pick from these rows, not invent new categories or tech names.

**Campaign-specific exceptions to standing house rules** (explicit user direction for this campaign only — do not apply elsewhere without asking):
- No automated HubSpot eligibility / DNC check before send — the user has already vetted this contact list.
- Copy does not use `knowledge/messaging-frameworks.md` or `knowledge/persona-definitions.md`. It's built directly from 3 angles the user supplied (below), adapted per company using `example_detections`.

**The 3 source angles** (style reference only — `2_generate_copy.py` adapts, does not copy verbatim):
1. **Cut through the noise** — Black Hat visibility ends, the daily prospecting grind doesn't; Firmable's OSINT data means outreach starts from something real about the target's environment.
2. **David vs Goliath** — smaller sponsors can't out-budget Cisco/AWS/Microsoft at the show, but OSINT signal + phone coverage is an edge those budgets don't buy.
3. **What happens after** — any platform can enrich the attendee list with email/phone after the show; Firmable adds OSINT signal on the companies themselves.

**Copy rules specific to this campaign:**
- Email 1: hook personalized with the company's `example_detections`; explicitly frame the signal as backend/infrastructure-level — not visible on the target's website, not something a job posting would reveal. Phrase any tech-name-dropping as an offer/suggestion ("we could show you...") not a flat assertion.
- Email 2: "how we actually get this" — OSINT/publicly-observable-signal explanation, one legitimacy line (nothing behind a login), booth ask reinforced. P.S. line only: "50% more phone/mobile coverage than major B2B databases" — this stat is US-specific, valid here because Black Hat US is a US audience; do not reuse it for non-US campaigns without re-checking. Do **not** use the 22% connect-rate-vs-5% stat for this campaign.
- Both scripts support `--limit N` — always run a 5-10 contact sample batch first and get sign-off before running the full list.

**What goes out** — `output/1_classified_<timestamp>.csv`, `output/2_copy_<timestamp>.csv`. SmartLead upload requires explicit confirmation of lead count, campaign name, sender identity, and send timing per email (CLAUDE.md rule 2) — not automated by these scripts.
