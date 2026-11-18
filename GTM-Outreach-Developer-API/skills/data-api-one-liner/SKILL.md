---
name: data-api-one-liner
description: Turn one company domain into outreach copy showing how Firmable's data API (AI adoption index, tech intelligence, decision engine) could help that company's sellers build better prospect lists. Researches the company, finds competitors and integrations, pulls live tech intel counts, then runs the AI adoption index and decision engine on a real sample of the prospect's target accounts so every statement rests on real outputs. Writes one statement per API plus a recommended cold outreach line. Use when a domain is pasted in the context of developer/data API outreach.
---

# Data API One-Liner

Input: one company domain.
Output: a tech stack table, three API statements (one sentence each, addressed to the prospect, each backed by a real test) and one recommended cold outreach line.

---

## Tools: Firmable developer MCP only

Use the developer API MCP (`mcp__firmable__*`), not the app connector (`mcp__claude_ai_Firmable__*`). The pitch is for the developer API, so every number must come from the same API the prospect would buy.

| Step | Tool |
|---|---|
| Resolve technology and industry ids | `get_filter_options` (identifier `tech_intelligence`, `industry`) |
| Counts and sample accounts | `filter_search` (free) |
| AI adoption on the sample | `get_ai_adoption` with `records` (1 unit per company found, 5 units = 1 credit) |
| Decision engine on the sample | `make_decision` with `records` and `withReasoning: true` (2 credits per 25 yes/no answers; unknowns free) |
| Pick a structured decision tool | `list_decision_tools` (free) |

A full run costs roughly 5 to 10 credits.

### Credit costs (from the API, Nov 2026)

| Call | Credits |
|---|---|
| `filter_search`, `ai_search`, `get_filter_options`, `list_decision_tools` | Free. A plain company list (name, domain, industry, size band, HQ country, profile link) costs nothing |
| `get_company` / `bulk_get_companies` | Up to 1 per company, free if the org already paid for that profile |
| `get_person` / `bulk_get_people` | 1 per new profile; reveals on a paid profile are free |
| `get_tech_intel` | 1 per technology, up to 5 per company; repeats and later pages free |
| `get_ai_adoption` | 1 per 5 companies (0.2 each); 3 per company with `withEvidence`; no data = free |
| `make_decision` | 1 per 25 yes/no answers (0.04 each), 2 per 25 with reasons; unknowns free |

Developer credits: 40 free a month, bought credits never expire. There is no published dollar price per developer credit. The closest public proxy is pay.firmable.com: $0.25 per company or people enrichment, $0.05 per people search (USD). Use $0.25 per credit for internal estimates only, and confirm with product before quoting dollars to a prospect.

---

## Step 1: Research the company

Read the website, including any business, partner, pricing and case study pages (also search "<company> case study" and their blog). Work out:
- What they sell
- Which businesses buy it (the real ICP)
- Where those buyers are

Rules:
- Prefer customer logos and case studies over marketing copy. They show the real ICP.
- Identify the home market. A US company is measured against US data, an AU company against AU data.

From the research, also derive:
- The qualifying question: what their reps need answered that no industry or headcount filter captures. See Step 5 for how to phrase it so the decision engine can answer it.
- The AI angle (if any): selling AI products, launching agent features, or depending on buyers who are modernising.

## Step 2: Find competitors and integrations

Competitors. Do not guess from general knowledge. Search in this order:
1. Comparison or "vs" pages on the company's own site
2. Competitors their content keeps naming
3. Only then, review sites such as G2

Integrations. List the platforms the company integrates with. Put first the ones that define their ICP, such as the ecommerce platform or CRM their customers must already run.

## Step 3: Tech intelligence counts

For every competitor and integration:
1. Resolve the technology id with `get_filter_options` (identifier `tech_intelligence`).
2. Count companies in the home market with `filter_search`, using `hq_country`.
3. If the ICP is narrow, add an `industry` filter.

The 200 rule:
- Anything under 200 companies stays out of the pitch.
- Before dropping, try grouping competitors (several ids in one `tech_intelligence` filter = OR) to clear the bar.

Spot-check the top results of every pool. Niche vendors may be missing (Flex and Sika Health aren't tracked), names can match the wrong product (DDI System returned PNC), and raw Shopify detection includes Amazon and Walmart. Add an industry or size filter when the top rows look wrong.

Always record which location filter produced each number. `hq_country` and `country` give different counts (see the IOMETE example), and the copy must quote the one you can reproduce.

## Step 4: Build the test sample

From the strongest pool in Step 3 (usually the grouped competitor list), pull 16 to 20 companies with `filter_search`:
- About half from the top by size (`sorting: {"company": {"company_size": "desc"}}`)
- About half from a smaller size band (e.g. `global_company_size` `range:50-1000`)

A sample of only the largest companies hides whether the engines can tell accounts apart. Keep the company ids; both tests below run on the same sample.

## Step 5: Test the decision engine

The decision engine answers only from what is on the company's Firmable record: its description, industry, size, locations, company type and stock exchange listings. It does not see job ads, tech stack, internal infrastructure or regulation.

How it answers:
- Every answer is yes, no or unknown, with a confidence from 0 to 1, the deciding fact quoted, its source and date, and what would change it. The API has no Choice or Score output; don't pitch either.
- It applies common sense to record facts ("Industry: Banking" → handles regulated data; a "health care network" description beats a wrong Construction tag).
- It does not use outside knowledge of the specific company. Western Alliance is a known regional bank, but the record didn't say so, so it answered unknown.
- It can overreach on loose wording (Pitney Bowes "government clients" → yes to "handles government data").

5a. Phrase the qualifying question so the record can answer it. Ask about what a company would say about itself (what it does, who it serves, where it operates, what kind of organisation it is). Do not ask about:
- Internal infrastructure or tooling ("does it run its own data centers?") → always unknown
- Something already implied by the filter you used ("is this bank regulated?" on a Banking list) → always yes, so it cuts nothing

5b. Run it on the sample: `make_decision` with `ask`, `records` and `withReasoning: true`. If a structured tool fits better (`is_icp_fit`, `offers_service`, `is_b2b`, `is_publicly_listed`, `matches_company_size`), call it with `tool` and `question` instead of `ask`. See "Decision tool notes" below for which tools are reliable.

5c. A question passes only if all three are true:
- At least 60% of the sample gets yes or no (not unknown)
- The answers split: neither yes nor no is above 85%
- The reasons quote the company's description, not just its industry label

If it fails, rephrase once or twice (often by moving from "how they run" to "who they serve" or "what they are"), then re-test. If nothing passes after three tries, leave the decision engine out of the recommended line and say so in the output.

5d. Also run one "what kind of company is this" question on the sample as list hygiene (e.g. "Does this company distribute building, plumbing, electrical, HVAC or industrial supplies to trade customers?"). It won't split a clean list, but it removes false matches that tech intel pulls in (Curri test: it cut Cognizant and PNC from the ERP pool). A hygiene question doesn't need to pass 5c; describe it as cleaning, not as the cut.

Do not trust:
- `has_multiple_sites`. It undercounts locations (Genuine Parts recorded with 2 sites; its description says 10,800).
- `is_multinational`, or reasons citing "has profiles in AU, CA, ID…". Firmable's regional records list many US companies in APAC markets, so this misfires on domestic US companies.
- `matches_campaign_audience` with a long pitch. In testing it answered half the sample, and every "yes" just cited the industry.

## Step 6: Test the AI adoption index

Run `get_ai_adoption` on the same sample with `records` (no `withEvidence` unless you need to quote a specific signal).

Report:
- Coverage: how many of the sample returned data
- Level spread: count of ADVANCED / STRONG / MODERATE / DETECTED
- Momentum: how many are ACCELERATING or EXPANDING
- The dimension that matters for this prospect (e.g. `architecture` for data infrastructure vendors, `footprint` for agent or AI product vendors, `hiring` for anyone selling into AI teams)

The statement must quote the real split from the sample, e.g. "6 of 15 already score Strong or Advanced". Say it's a sample; don't extrapolate to the full pool as if it were measured.

Coverage follows company size (tested Nov 2026: banks 15 of 16, distributors 13 of 18, small DTC brands 9 of 18). If fewer than 60% of the sample has data, or nothing scores above Moderate, leave AI adoption out of the recommended line and say so.

Look at the footprint sub-dimensions, not just the overall level. "10 of 13 already use Claude or ChatGPT at work, none run customer-facing agents" (Curri) is a sharper hook than "3 of 13 score Strong".

## Step 7: Write one statement per API

Each statement is a single sentence addressed to the prospect, and each must rest on a test from Steps 3, 5 and 6.

AI adoption index: which of the prospect's target accounts it surfaces, the real level split from the sample, and why AI readiness changes how the prospect should sell to them.

Tech intelligence: the competitors and integration platforms that passed the 200 rule, with real counts. Competitor installs give a displacement list; integration platforms give the wider addressable pool.

Decision engine: the qualifying question that passed 5c as a yes/no filter, with the real split from the sample and the list it produces. If none passed, write "Decision engine: no record-answerable question found" and the questions tried.

## Step 8: Pick the recommended line

One sentence, 45 words or fewer, for cold outreach. Either:
- The strongest of the three statements, or
- A combination of two, usually tech intelligence for the pool plus AI adoption index or decision engine for the cut.

Only use an engine in the recommended line if it passed its test.

## Output format

1. Tech stack table: Type | Vendor | Evidence | Home-market companies (note the location filter used)
2. Test results: sample size, AI adoption spread, decision engine questions tried with yes/no/unknown counts and pass/fail
3. Three statements
4. Recommended line

---

## Decision tool notes (all 34 tested, 17 Nov 2026)

17 company tools and 18 person tools (`is_located_in` covers both). Full inputs, allowed values and test results per tool are in the Data API Playbook: https://claude.ai/artifact/FQsqg3dyp2SeunHUEsaYvM (section 4). Use `list_decision_tools` with `tool` (free) for any schema.

Company tools:
- Reliable: `evaluate_custom_decision`, `is_icp_fit` (judges each criterion separately, best general fit check), `is_b2b`, `is_publicly_listed`, `claims_rd_tax_incentive` (AU only), `matches_company_size` (returns the exact headcount), `has_local_team` (AU/NZ only, returns the count), `has_company_phone`.
- Use with care:
  - `offers_service` stretches on vague wording (Ferguson said yes to same-day delivery because it mentions "logistics solutions").
  - `matches_company_type` and `is_public_sector_or_nonprofit` can carry wrong types (Canva recorded as a sole trader, Johns Hopkins as private).
  - `is_located_in`: countries and places combine as "any one matches", so pass only the state to check a state. HQ city can be wrong (Micron recorded in San Diego).
  - `is_same_business` and `owns_domain` match exact domains or registry numbers only; no acquisitions or staging sites, and `owns_domain` never says no.
- Avoid: `matches_campaign_audience`, `has_multiple_sites`, `is_multinational`.

Person tools:
- Reliable: `is_email_valid`, `is_mobile_valid`, `is_mobile_on_dnc` (AU only), `is_reachable`, `matches_seniority`, `matches_department`, `is_new_to_role`, `is_new_exec`, `is_long_tenured`, `has_changed_jobs_since`, `works_at_company`, `is_contact_current`, `previously_worked_at`, `has_skill`, `is_located_in`.
- Use with care:
  - `is_decision_maker` guesses which departments own the purchase (a Head of Security came back yes for a sales-data product); pass a specific `buyer`.
  - `is_founder_or_owner` reads the main title only.
  - `has_other_current_roles` counts memberships and second titles at the same employer.

Strongest prospect talking points: the custom question or `is_icp_fit`; for ANZ, `is_reachable` + `is_mobile_on_dnc` for call compliance; `is_new_exec` for timing; `is_contact_current` + `has_changed_jobs_since` for CRM clean-up.

---

## Worked example: curri.com (Nov 2026)

Pool: US HQ companies on Epicor Eclipse, Prophet 21, BisTrack or DDI = 484 (165 in building materials or wholesale). No competitors named on site; Roadie tracked at only 7.
Decision engine: "Distributes building, plumbing, electrical, HVAC or industrial supplies to trade customers?" 16 yes / 3 no / 1 unknown. Doesn't split a clean list but removed Cognizant, PNC and a janitorial supplier. Hygiene, not the cut.
AI adoption: 13 of 18 scored. 10 of 13 use Claude or ChatGPT at work, none run customer-facing agents.
Exclude existing customers shown on curri.com (Johnstone Supply, Hajoca).
Recommended: We can pull the 484 US distributors running Epicor Eclipse, Prophet 21 or BisTrack and show which already use Claude or ChatGPT at work, so your reps can pitch booking deliveries through tools those teams already use.

## Worked example: truemed.com (Nov 2026)

Pool: US Shopify + "wellness"/"supplements" keywords + e-commerce industry, 11 to 1,000 staff = 1,782. Competitors Flex and Sika Health aren't tracked; TrueMed itself shows 24 installs (use to exclude).
Decision engine: "Sells products a clinician could recommend?" 11 yes / 6 no / 1 unknown. Passed: cut candles, snacks, juice, water bottles.
AI adoption: 9 of 18 scored, none above Moderate. Left out.
Recommended: We can pull the 1,700+ US wellness brands selling on Shopify and use our decision engine to keep only those whose products a clinician could recommend, so your reps only pitch brands that can actually offer HSA/FSA checkout.

## Worked example: iomete.com (tested 17 Nov 2026, rerun after ICP fix)

First attempt went wrong: it targeted US regional and community banks because that question passed the engine test. IOMETE's case studies (tier-1 bank, national bank off Oracle, $300M fintech off Snowflake, 200-factory manufacturer, global tech manufacturer at 100,000+ vCPUs) show the buyer is a large regulated enterprise with a big legacy data estate. Lesson: read case studies first, and pick the decision question to match the ICP, not just to pass 5c.

Pool (US HQ, 5,000+ global staff as a proxy for 100TB+):
- Cloudera, Hadoop, Teradata or Oracle Exadata: 1,444
- Same, in banking, insurance, hospitals, government, defense, pharma: 313
- Databricks or Snowflake, regulated industries: 413

Sample: 20 enterprises across industries from the 1,444 pool (so an industry-based question can split).

Decision engine:
| Question | Yes | No | Unknown | Result |
|---|---|---|---|---|
| Handles sensitive regulated data (banking, insurance, patient health, government, defense)? | 14 | 0 | 6 | Use as filter: unknown = not regulated. Caught 5 that industry tags missed (GDIT, R1 RCM, Clario, Cardinal Health, Steward). One false positive (Pitney Bowes, "government clients"). |
| Works for or supplies government, defense or national security? | 4 | 0 | 16 | Flag only. Precise on yes, free on unknown. |
| `is_public_sector_or_nonprofit` | 1 | 19 | 0 | Too narrow (Johns Hopkins recorded as private company). |

AI adoption (20 of 20 had data): ADVANCED 8, STRONG 9, MODERATE 2, DETECTED 1. Of the 14 regulated, 11 score Strong or Advanced and 8 of those 11 have no or basic AI architecture.

Statements:
- Tech intelligence: We can pull the 1,444 US enterprises with 5,000+ staff still running Cloudera, Hadoop, Teradata or Oracle Exadata, 313 of them in banking, insurance, healthcare, government and defense, so your reps start with the legacy estates you replace.
- Decision engine: Our decision engine flags which of those hold regulated data like banking, patient or defense records, including ones industry tags miss, such as a clinical-trials software firm, so your reps only work accounts where the data has to stay in-house.
- AI adoption: In a test of 20 of those enterprises, 11 of the 14 handling regulated data score Strong or Advanced on our AI adoption index, yet 8 of those show little or no AI infrastructure, so your reps can reach teams whose AI plans need data that can't leave their walls.

Recommended: We can pull the 1,444 US enterprises still on Cloudera, Hadoop, Teradata or Exadata, flag those holding regulated data, and show which are scaling AI without the infrastructure for it, so your reps start with teams that need AI-ready data in-house.
