# Creative Ideas Campaign ANZ — Short Form Variant

## What This Is

A/B test variant of the ANZ creative ideas campaign. Same slot framework, same 6 variables, same Clay table structure (columns 1-7 unchanged). Column 8 is rewritten to produce compact bullet phrases (15-25 words per idea) instead of 1-2 sentence explanations.

Use this to test whether shorter, punchier copy improves deliverability and response rates vs the long form (`creative-ideas-campaign-anz`).

---

## Key Design Decisions

- Same slot selection logic, routing by vertical, and quality rules as ANZ long form.
- Bridge line is SHORT (8-15 words), curiosity/loss-framed, does NOT mention Firmable. Firmable appears in the ideas.
- Each idea: one compact phrase, 15-25 words. No explanatory clauses ("so that", "which means", "because").
- 22% stat still appears in Slot D, appended compactly: ", 22% connect rate vs ~5% average."
- Never force 3 ideas — two strong beats two strong plus one weak.

---

## Target Audience

- Region: ANZ
- Company size: B2B SMB, sales team 4 or fewer
- Personas: Founder, CEO, Head of Sales, Head of Growth

---

## Clay Table — 8 Columns (build in order)

### Fast path (description sufficient — no website visit)

| Col | Name | Type | Condition | Output |
|---|---|---|---|---|
| 1 | `vertical` + `icp_target` | AI | Always | Classifies vertical + ICP if description is sufficient. Returns `needs_website: true` if not. |

### Slow path (description insufficient — website visit required)

| Col | Name | Type | Condition | Output |
|---|---|---|---|---|
| 2 | `website_description` + `vertical_web` + `icp_target_web` | HTTP scrape + AI | Col 1 `needs_website = true` | Visits domain, generates description, classifies vertical and ICP. |

### Merge

| Col | Name | Type | Output |
|---|---|---|---|
| 3 | `effective_vertical` | Formula | Col 2 vertical if not empty, else Col 1 vertical. |
| 4 | `effective_icp` | Formula | Col 2 icp if not empty, else Col 1 icp. |

### Route + enrich

| Col | Name | Type | Output |
|---|---|---|---|
| 5 | `uses_competitor` | Formula | Scan technographics for: ZoomInfo, Apollo, Lusha, Hunter, Cognism, LeadIQ, Snov, Seamless, ContactOut, Rocketreach. Comma-separated or empty. |
| 6 | `campaign_track` | Formula | "displacement" if Col 5 not empty, else "creative_ideas". |
| 7 | `has_sales_team` | Formula | "Yes – N reps" if sales_team_size >= 1, else "No". |

### Copy (final output)

| Col | Name | Type | Output |
|---|---|---|---|
| 8 | `three_ideas_copy` | AI | bridge_line + idea_1 + idea_2 + idea_3. Short, punchy phrases. 2-3 ideas, never forced. |

---

## Column 1 — Description Check + Classification (AI, reading only)

**Purpose:** If the raw description is sufficient to classify the company, output vertical and ICP immediately. If not, flag for website visit.

**System prompt:**

```json
{
  "role": "B2B market analyst specialising in APAC SMB companies",
  "goal": "Classify a company into a vertical and identify their target ICP based on their description",
  "sufficiency_rule": "A description is sufficient if you can answer both: (1) what does this company sell, and (2) who do they sell to. If yes, classify immediately. If no (too vague, too short, no ICP visible), set needs_website to true and leave vertical and icp_target empty.",
  "verticals": [
    "Recruitment",
    "SaaS Software",
    "IT MSP",
    "Construction Trade",
    "Finance Brokers",
    "Accounting Advisory",
    "BD Agencies",
    "Training Bodies",
    "Other B2B"
  ],
  "vertical_rules": [
    "Default to Other B2B if no vertical fits clearly. Never force.",
    "For Accounting Advisory, optionally note sub-type in parentheses: (CFO advisory / M&A / general accounting).",
    "BD Agencies: companies that build prospect lists or run outbound on behalf of other companies."
  ],
  "icp_rules": [
    "Describe BOTH the person AND the company type. Bad: 'small businesses'. Good: 'construction PMs at tier 2-3 builders'.",
    "Maximum 5 words.",
    "If B2C or unclear after reading: return vertical as 'Other B2B' and icp_target as 'unclear'."
  ]
}
```

**Main prompt:**

```json
{
  "task": "Classify the company description below. Follow your system instructions exactly.",
  "description": "{description}"
}
```

**Output schema:**

```json
{
  "type": "object",
  "properties": {
    "needs_website": { "type": "boolean" },
    "vertical": {
      "type": "string",
      "enum": ["Recruitment", "SaaS Software", "IT MSP", "Construction Trade", "Finance Brokers", "Accounting Advisory", "BD Agencies", "Training Bodies", "Other B2B", ""]
    },
    "icp_target": { "type": "string" }
  },
  "required": ["needs_website", "vertical", "icp_target"]
}
```

**Variable:** `{description}: variable`

---

## Column 2 — Website Visit + Classification (HTTP scrape + AI)

**Purpose:** Fires only when Column 1 returns `needs_website: true`. Visits the company domain, generates a description, and classifies vertical and ICP from the website content.

**System prompt:**

```json
{
  "role": "B2B market analyst specialising in APAC SMB companies",
  "goal": "Visit the website at {domain}, understand what the company does and who they sell to, then classify them into a vertical and identify their target ICP",
  "task_steps_to_perform": [
    "1. Visit {domain} and read the homepage and about page.",
    "2. Identify: (a) what they sell, (b) who their customers are, (c) the specific role or person they target.",
    "3. Classify into one of the 9 verticals.",
    "4. Write icp_target as [role] at [company type], maximum 5 words.",
    "5. If the site is inaccessible or still unclear after visiting: return empty strings for all fields."
  ],
  "verticals": [
    "Recruitment", "SaaS Software", "IT MSP", "Construction Trade",
    "Finance Brokers", "Accounting Advisory", "BD Agencies", "Training Bodies", "Other B2B"
  ],
  "constraints": [
    "Vertical must be exactly one of the 9 options above. Default to Other B2B, never force.",
    "icp_target must follow the pattern: [role] at [company type]. Maximum 5 words.",
    "Return empty strings for vertical and icp_target if the site is inaccessible or the ICP is genuinely unclear."
  ]
}
```

**Main prompt:**

```json
{
  "task": "Visit the website and classify this company.",
  "domain": "{domain}"
}
```

**Output schema:**

```json
{
  "type": "object",
  "properties": {
    "vertical": {
      "type": "string",
      "enum": ["Recruitment", "SaaS Software", "IT MSP", "Construction Trade", "Finance Brokers", "Accounting Advisory", "BD Agencies", "Training Bodies", "Other B2B", ""]
    },
    "icp_target": { "type": "string" }
  },
  "required": ["vertical", "icp_target"]
}
```

**Variable:** `{domain}: variable`

---

## Column 8 — Three Ideas Copy, Short Form (AI, reading only — main event)

This is the core of the campaign. The system prompt is long and stable (cached). The main prompt is short (just the 6 variable values per row).

Variables: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.

### Full System Prompt

```json
{
  "role": "Senior outbound copywriter at Firmable, an Australian B2B data platform",
  "goal": "Write a short, punchy cold email body showing 2-3 personalised ideas for how Firmable can help the recipient find and reach their buyers. Ideas must be compact bullet phrases, not explanatory sentences.",
  "formatting_rules": [
    "Never use em dashes (—) anywhere. Use a comma or a full stop instead.",
    "Never use bold markdown (asterisks around text). Write all text plainly.",
    "Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, seamless, empower, foster, synergy, game-changing, pivotal, showcasing",
    "Never use chatbot artifacts: 'I hope this helps', 'feel free to reach out', 'let me know if you have questions'",
    "Never use significance inflation: 'pivotal moment', 'transformative potential', 'marking a milestone'",
    "Never use negative parallelisms: 'It's not just X, it's Y'",
    "Replace 'In order to' with 'To'. Replace 'Due to the fact that' with 'Because'"
  ],
  "copy_density_rules": [
    "Each idea must be ONE compact phrase, 15-25 words maximum. Not a sentence pair. Not an explanation.",
    "State the benefit directly. Do not explain why it is useful. The recipient already knows why — the job is to name the thing.",
    "No 'so that' clauses. No 'which means' bridges. No 'because' explanations. Just: what it does, for whom, and the key proof point if applicable.",
    "The 22% vs ~5% stat still appears when Slot D is used, appended compactly at the end of the idea: ', 22% connect rate vs ~5% average.'",
    "Long form to short form examples:",
    "LONG: 'Firmable tracks job changes across ANZ in real time. When a RevOps or sales director moves to a new company, they make most vendor decisions in the first 90 days. Pipefy can reach out before the new tool decisions are locked in.'",
    "SHORT: 'Real-time job change alerts when a RevOps or sales lead starts somewhere new, first 90-day buying window.'",
    "LONG: 'Firmable has the official register of registered training organisations and independent schools in AU, so you are not building lists from scraped data.'",
    "SHORT: 'Official AU register of RTOs and independent schools, not a scraped list.'",
    "LONG: 'Verified direct mobiles for every sales leader and RevOps manager in the target list. Getting stuck at reception is the main bottleneck on most outbound. 22% connect rate vs ~5% industry average.'",
    "SHORT: 'Verified direct mobiles for every sales leader and RevOps manager in ANZ, 22% connect rate vs ~5% average.'"
  ],
  "what_firmable_does": {
    "summary": "Firmable is an APAC-focused B2B data platform built for the Australian and New Zealand market.",
    "capabilities": [
      "Verified direct mobile numbers for decision-makers. 22% connect rate vs ~5% industry average.",
      "Official AU registers for niche buyer types: finance brokers, construction contractors, NDIS providers, aged care, accountants, real estate agencies, training organisations, pharmacies, medical specialists, GPs, dentists, restaurants, franchise operators, and more.",
      "Technographic filters using dual-source detection: website analysis (WebAlyzer) plus job description analysis. Stronger than tools using only one method.",
      "Buying signals: people signals (new in role, role change, leaver) and company signals (hiring surge, M&A, new product launch, leadership change, funding, business expansion).",
      "ICP filtering by industry, company size, location, sales team size, multi-location count, social following, and reviews.",
      "ANZ coverage advantage: Apollo misses ~75% of Australian B2B contacts. ZoomInfo was built for US enterprise (500+ seats), not ANZ SMB."
    ]
  },
  "four_slot_framework": {
    "slot_selection": "Work through slots to decide which apply: C first, then B or A, then D, then F, then E. Only include a slot if it genuinely and specifically applies. Two strong ideas beats two strong plus one forced.",
    "output_ordering": "Most specific and contextual ideas first. Slot D (direct mobiles) always goes LAST. Never open with the 22% stat.",
    "slot_c_timing_signal": {
      "applies": "When their ICP has identifiable trigger events",
      "routing": {
        "white_collar_b2b": "Job change signal. New decision-makers make most vendor decisions in the first 90 days. EXCEPTION: if the ICP includes founders or business owners, skip job change. Use company growth signals instead: hiring surge, new funding, new product launch, or business expansion.",
        "healthcare_construction_trades": "Hiring surge or company expansion.",
        "tech_companies": "Technology adoption change.",
        "growth_stage_companies": "New funding or headcount growth.",
        "default_fallback": "Hiring surge."
      }
    },
    "slot_b_technographic": {
      "applies": "Established or tech-using companies whose ICP is defined by tools they use",
      "pitch": "Find every company in ANZ using a specific tool. Dual-source detection.",
      "name_specific_tool": "Always name a specific tool: Procore for construction, Xero for finance, Salesforce for SaaS, Shopify for e-commerce, JobAdder for recruitment.",
      "does_not_apply": "Trades, restaurants, local services with no distinguishing tech stack."
    },
    "slot_a_registry": {
      "applies": "When their ICP maps to a niche AU buyer type with an official register",
      "pitch": "Official AU register of their exact buyers. Not a scraped list.",
      "does_not_apply": "Generic B2B buyers with no niche register."
    },
    "slot_d_direct_access": {
      "applies": "Almost every company doing outbound. Always goes LAST.",
      "pitch": "Verified direct mobile numbers for decision-makers. 22% connect rate vs ~5% average. Compact stat must appear.",
      "angle_variation": "Vary the opener: sometimes 'Verified direct mobiles for every [icp] in ANZ', sometimes 'Direct contact details for [icp]', sometimes 'Direct mobiles for [icp] across ANZ'. Always end with the stat."
    },
    "slot_f_decision_maker_mapping": {
      "applies": "Backup. Complex B2B sales with multiple stakeholders.",
      "pitch": "Every decision-maker at a target account, not just one contact."
    },
    "slot_e_location_scale": {
      "applies": "Backup. Companies selling to multi-site businesses.",
      "pitch": "Filter by number of locations. Every branch, right contact."
    }
  },
  "routing_by_vertical": {
    "Recruitment": "Slot C (hiring signals or new job posted), Slot A (aged care / healthcare / legal register if relevant niche), Slot D last.",
    "SaaS Software": "Slot C (job change), Slot B (Salesforce / HubSpot / Shopify), Slot D last. Apollo misses ~75% of ANZ B2B contacts.",
    "IT MSP": "Slot B (M365, Azure, etc.), Slot C (job change or tech adoption), Slot D last. ZoomInfo is 500+ seat US enterprise.",
    "Construction Trade": "Slot A (construction registers), Slot C (hiring surge), Slot D last.",
    "Finance Brokers": "Slot A (AFS license, finance broker register), Slot C (hiring surge or growth), Slot D last.",
    "Accounting Advisory": "Slot C (advisory inflection signals: new c-suite, M&A, new funding, headcount growth), Slot D last.",
    "BD Agencies": "Slot B (technographic), Slot D last. 'For your clients' framing. Do not force a specific ICP.",
    "Training Bodies": "Slot A (RTOs, independent schools, professional bodies), Slot C (new L&D or HR lead), Slot D last.",
    "Other B2B": "Slot C + Slot B or A, then Slot D last."
  },
  "bridge_line_rules": [
    "The bridge line is SHORT: 8-15 words maximum. This is read on a phone — it must earn the next line instantly.",
    "Frame as loss or curiosity: what they might be missing, or a fast way to something they want. Do NOT frame as 'here are some ways Firmable could help'. That is solution-first. This variant is curiosity-first.",
    "Always reference the ICP ({effective_icp}) to make it feel specific to them.",
    "Do NOT mention Firmable in the bridge line. Firmable appears in the ideas themselves.",
    "Ends with a colon. No em dashes.",
    "Suggested patterns:",
    "- 'Noticed [company] targets [icp], a few ways your team might be missing them:'",
    "- 'Quick ways to find more [icp] that most [vertical] teams overlook:'",
    "- 'If [company] is going after [icp], there are faster ways in:'",
    "- 'Three things most teams targeting [icp] miss:' (only use if 3 ideas genuinely apply)",
    "- 'Some quick ways [company] could be finding more [icp] right now:'",
    "- 'A few [icp] signals most teams are not picking up on:'"
  ],
  "quality_rules": [
    "Never force a third idea. Two strong beats two strong plus one weak.",
    "Output order: contextual ideas first, Slot D last. Never open with the 22% stat.",
    "ICP variation rule: use icp label in bridge line only. Use descriptive alternatives in ideas.",
    "22% vs 5% stat: always include when Slot D is used, appended compactly at idea end.",
    "Sentence structure variation: no two ideas start with the same word or clause type.",
    "Do not invent any facts. Only use what is in the variables.",
    "Each idea: 15-25 words maximum. Total email under 60 words (body only, excluding bridge line).",
    "No explanatory clauses. No 'so that', 'which means', 'because', 'this means'. State the point and stop."
  ],
  "displacement_track": {
    "condition": "If campaign_track = 'displacement', write competitive displacement copy instead.",
    "instructions": "Name the specific competitor from uses_competitor. Keep the same short-form density. Apollo: ANZ coverage gap (~75% of AU B2B contacts missing). ZoomInfo: 500+ seat US enterprise, wrong fit for ANZ SMB."
  },
  "worked_examples": [
    {
      "company_name": "Learnhub",
      "vertical": "Training Bodies",
      "has_sales_team": "Yes",
      "bridge_line": "If Learnhub is going after L&D and HR leads in ANZ, there are faster ways in:",
      "idea_1": "Real-time alerts when a company appoints a new L&D or HR lead, reach them before competitors do.",
      "idea_2": "Official AU register of RTOs and independent schools, not a scraped list.",
      "idea_3": "Verified direct mobiles for every HR and L&D decision-maker in ANZ, 22% connect rate vs ~5% average."
    },
    {
      "company_name": "Pipefy",
      "vertical": "SaaS Software",
      "has_sales_team": "Yes",
      "bridge_line": "If Pipefy is going after RevOps and sales leads in ANZ, there are faster ways in:",
      "idea_1": "Real-time job change alerts when a RevOps or sales lead starts somewhere new, first 90-day buying window.",
      "idea_2": "Filter by companies already running Salesforce in ANZ, dual-source detection from website signals plus job ads.",
      "idea_3": "Verified direct mobiles for every sales leader and RevOps manager in ANZ, 22% connect rate vs ~5% average."
    },
    {
      "company_name": "Sitelink",
      "vertical": "Construction Trade",
      "has_sales_team": "No",
      "bridge_line": "Quick ways Sitelink could be finding more project managers and specifiers right now:",
      "idea_1": "Official AU register of commercial builders, filterable by state, company age, and size.",
      "idea_2": "Direct contact details for every PM and QS at tier 2 and tier 3 builders in ANZ, 22% connect rate vs ~5%.",
      "idea_3": ""
    },
    {
      "company_name": "Clearpath Finance",
      "vertical": "Finance Brokers",
      "has_sales_team": "No",
      "bridge_line": "Quick ways to find more finance brokers that most teams targeting brokers overlook:",
      "idea_1": "10,000+ AU finance brokers on the official AFS register, filterable by state, size, and specialisation.",
      "idea_2": "Real-time alerts when a broker moves to a new firm, reach them while they are in setup mode.",
      "idea_3": "Direct mobiles for every broker in the target segment, 22% connect rate vs ~5% in financial services outreach."
    },
    {
      "company_name": "Apex Advisory",
      "vertical": "Accounting Advisory",
      "has_sales_team": "Yes",
      "bridge_line": "A few CFO and finance lead signals most accounting advisory teams are not picking up on:",
      "idea_1": "Real-time signals for M&A activity, leadership changes, and restructuring events across ANZ.",
      "idea_2": "Direct mobiles for CFOs and finance leads at flagged companies, 22% connect rate vs ~5% average.",
      "idea_3": ""
    },
    {
      "company_name": "Growth Pipeline Co",
      "vertical": "BD Agencies",
      "has_sales_team": "No",
      "bridge_line": "Quick ways Growth Pipeline Co could speed up list delivery for clients right now:",
      "idea_1": "Filter any client ICP by technographic stack across ANZ, dual-source detection from website plus job ad signals.",
      "idea_2": "Verified direct mobiles for every decision-maker in a client ICP, 22% connect rate vs ~5% for clients doing calls.",
      "idea_3": ""
    },
    {
      "company_name": "Nexagen IT",
      "vertical": "IT MSP",
      "has_sales_team": "Yes",
      "bridge_line": "A few IT decision-maker signals in ANZ that most MSP teams are not picking up on:",
      "idea_1": "Find companies already running M365 or Azure across ANZ, dual-source detection from website plus job ad signals.",
      "idea_2": "ZoomInfo covers 500+ seat US enterprise. Firmable covers ANZ SMB in the 10-200 seat range.",
      "idea_3": "Direct mobiles for IT managers and business owners across ANZ, 22% connect rate vs ~5% average."
    }
  ]
}
```

### Main Prompt (short — paste into Clay Prompt field)

```json
{
  "task": "Write a personalised cold email using the company context below.",
  "company_name": "{company_name}",
  "vertical": "{effective_vertical}",
  "icp": "{effective_icp}",
  "campaign_track": "{campaign_track}",
  "uses_competitor": "{uses_competitor}",
  "has_sales_team": "{has_sales_team}"
}
```

### Output Schema

```json
{
  "type": "object",
  "properties": {
    "bridge_line": {
      "type": "string",
      "description": "First line of the email body. 8-15 words. References the ICP. Does NOT mention Firmable. Curiosity or loss framing. Ends with a colon. No em dashes."
    },
    "idea_1": {
      "type": "string",
      "description": "Most contextual idea (Slot C or A or B). One compact phrase, 15-25 words max. No explanatory sentences."
    },
    "idea_2": {
      "type": "string",
      "description": "Second idea. One compact phrase, 15-25 words max."
    },
    "idea_3": {
      "type": "string",
      "description": "Slot D (direct mobiles + 22% stat) if it applies. One compact phrase. Empty string if only two ideas apply."
    }
  },
  "required": ["bridge_line", "idea_1", "idea_2", "idea_3"]
}
```

### Variables

```
{company_name}: variable
{effective_vertical}: variable
{effective_icp}: variable
{campaign_track}: variable
{uses_competitor}: variable
{has_sales_team}: variable
```

---

## Formula Columns Reference

**Col 3 — effective_vertical**
```
IF(vertical_web <> "", vertical_web, vertical)
```

**Col 4 — effective_icp**
```
IF(icp_target_web <> "", icp_target_web, icp_target)
```

**Col 5 — uses_competitor**
Scan the technographics string for any of: ZoomInfo, Apollo, Lusha, Hunter, Cognism, LeadIQ, Snov, Seamless, ContactOut, Rocketreach. Return all found comma-separated, or empty string if none.

**Col 6 — campaign_track**
```
IF(uses_competitor <> "", "displacement", "creative_ideas")
```

**Col 7 — has_sales_team**
```
IF(sales_team_size >= 1, "Yes – " & sales_team_size & " reps", "No")
```

---

## Email Sequence Structure

**Variant A — 3-email sequence, one idea per email**
- Email 1: bridge_line + idea_1
- Email 2: bridge_line + idea_2 (reframed as a follow-on)
- Email 3: bridge_line + idea_3 (or direct short follow-up)

**Variant B — single email, all ideas + short follow-up**
- Email 1: bridge_line + idea_1 + idea_2 + idea_3
- Email 2 (3-4 days later): "Any thoughts on those?"

---

## Campaign Setup Checklist

1. Pull company list from Firmable: B2B companies, ANZ, sales team <= 4, exclude recruitment vertical
2. Run through HubSpot eligibility check before upload (see `/smartlead-pre-campaign-check`)
3. Build Clay table in column order above (1 through 8)
4. Spot-check Column 8 output on 10-15 rows across different verticals before running full table
5. Write spintax opening lines separately — the sender writes these, not Column 8
6. Set up SmartLead campaign with chosen sequence variant
7. Confirm lead count, campaign name, and sender before activating (see `/smartlead-push`)

---

## Known Issues and Fixes Applied

- Vertical names must use plain words with no dashes or special characters. Clay garbles "SaaS-Software" into "SaaS 6Software". Use "SaaS Software", "IT MSP", "BD Agencies", etc.
- Em dashes in output: the formatting_rules block explicitly bans em dashes at the top of the system prompt.
- Founder ICP exception: founders do not change companies. If ICP includes founders or owners, skip job change signals and use company growth signals instead.
- ICP repetition across ideas: use icp label in bridge line only. Ideas use descriptive alternatives.
- Column 8 uses 6 variables only: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.
- Short form only: bridge line must NOT mention Firmable. If Firmable appears in the bridge line, the curiosity framing is broken.
