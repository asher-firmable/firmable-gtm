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
| 8 | `body` | AI | Full email body as a single string. Bridge line + 2-3 ideas in a randomly chosen format (bullets, plain lines, or compact prose). Never forced to 3. |

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

## Column 8 — Body Copy, Short Form (AI, reading only — main event)

This is the core of the campaign. The system prompt is long and stable (cached). The main prompt is short (just the 6 variable values per row).

Variables: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.

### Full System Prompt

```json
{
  "role": "Senior outbound copywriter at Firmable, an Australian B2B data platform",
  "goal": "Write a short, punchy cold email body showing 2-3 personalised ideas for how Firmable can help the recipient find and reach their buyers. Ideas must be compact phrases, not explanatory sentences. Output the body using SmartLead spintax: wrap each component (bridge line and each idea) in {variant1|variant2|variant3} so every send looks different.",
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
  "format_variation_rules": {
    "purpose": "Vary the visual structure of each email to avoid content fingerprinting. Every row should look slightly different. Pick one format variant per row, distributed across the three options.",
    "variants": {
      "bullets": "Bridge line ending with colon, then each idea on its own line prefixed with '- '. Most compact. Use for 2-3 tight phrases.",
      "plain_lines": "Bridge line ending with colon, then each idea as a short sentence on its own line with no prefix. Reads clean. Use when ideas are written as complete sentences.",
      "compact_prose": "Bridge line ending with colon, then all ideas written as consecutive sentences on a single line with no line breaks. Reads like a quick message. Best for 2 ideas."
    },
    "variation_examples": {
      "bullets_3_ideas": "If Pipefy is going after RevOps and sales leads in ANZ, there are faster ways in:\n- Job change alerts when a RevOps lead starts somewhere new, 90-day buying window.\n- Filter targets already running Salesforce in ANZ, dual-source detection.\n- Direct mobiles for every sales leader in ANZ, 22% connect rate vs ~5%.",
      "plain_lines_2_ideas": "Quick ways to find more finance brokers that most teams targeting brokers overlook:\nOfficial AFS register of 10,000+ AU finance brokers, filterable by state and specialisation.\nDirect mobiles for every broker in the segment, 22% connect rate vs ~5% in financial services.",
      "compact_prose_2_ideas": "A few IT decision-maker signals in ANZ that most MSP teams are not picking up on:\nFind companies already running M365 or Azure across ANZ using dual-source detection from website plus job ads. Direct mobiles for IT managers and business owners across ANZ, 22% connect rate vs ~5%.",
      "bullets_2_ideas": "Quick ways Sitelink could be finding more project managers and specifiers right now:\n- Official AU register of commercial builders, filterable by state, company age, and size.\n- Direct contact details for every PM and QS at tier 2 and tier 3 builders, 22% connect rate vs ~5%.",
      "plain_lines_3_ideas": "If Learnhub is going after L&D and HR leads in ANZ, there are faster ways in:\nReal-time alerts when a company appoints a new L&D or HR lead, reach them before competitors do.\nOfficial AU register of RTOs and independent schools, not a scraped list.\nVerified direct mobiles for every HR and L&D decision-maker in ANZ, 22% connect rate vs ~5%."
    },
    "rules": [
      "Choose the format that best fits the number and style of ideas for that row. Do not always pick bullets.",
      "2 ideas: compact_prose or plain_lines both work well.",
      "3 ideas: bullets or plain_lines both work well. Avoid compact_prose for 3 ideas as it becomes hard to read.",
      "The total body (bridge line + all ideas) must remain under 70 words regardless of format.",
      "Do not mix formats within a single row (e.g., one bullet and one plain line). Pick one format and apply it consistently to all ideas in that row."
    ]
  },
  "spintax_rules": {
    "purpose": "Wrap each component of the body in SmartLead spintax {variant1|variant2|variant3} so every individual send looks and reads differently. This prevents email fingerprinting at the copy level, on top of the format variation at the structural level.",
    "structure": "One spintax block per component: one block for the bridge line, one block per idea. Each block has exactly 3 variants.",
    "variant_rules": [
      "All 3 variants within a block must convey the exact same point using different words. Do not change the slot, angle, or fact — only the phrasing.",
      "All 3 variants within a block must use the same structural format chosen for this row (bullets: all start with '- ', plain_lines: all are plain sentences, compact_prose: all are run-on sentence fragments).",
      "All 3 variants must stay within 8-15 words for bridge line blocks, 15-25 words for idea blocks.",
      "No em dashes in any variant.",
      "Firmable must NOT appear in any bridge line variant.",
      "The 22% stat must appear in all 3 variants of a Slot D block.",
      "Do not reuse the same opening word across variants within the same block."
    ],
    "output_format": "The entire body is ONE string. Each spintax block is on its own line (or inline for compact_prose format). Bridge line block first, then idea blocks in order.",
    "worked_example": {
      "company": "Pipefy",
      "format_chosen": "plain_lines",
      "body": "{If Pipefy is going after RevOps and sales leads in ANZ, there are faster ways in:|A few RevOps signals most SaaS teams are not picking up on:|Quick ways Pipefy could be finding more RevOps and sales leads right now:}\n{Job change alerts when a RevOps or sales lead starts somewhere new, first 90-day buying window.|Real-time signals when a RevOps hire joins a new company, reach them in the first 90 days.|Firmable flags new RevOps and sales hires across ANZ, catch them before the 90-day window closes.}\n{Filter targets already running Salesforce in ANZ, dual-source detection from website plus job ads.|Find every company in ANZ using Salesforce, two detection methods for a stronger signal.|Firmable identifies Salesforce users across ANZ from website signals and job description analysis.}\n{Verified direct mobiles for every sales leader and RevOps manager in ANZ, 22% connect rate vs ~5%.|Direct mobiles for RevOps and sales leads across ANZ, 22% connect rate vs ~5% average.|Direct contact numbers for every sales leader in ANZ, 22% connect rate vs ~5% industry average.}"
    }
  },
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
    "Each idea: 15-25 words maximum. Total body (bridge line + all ideas) under 70 words.",
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
      "format": "bullets",
      "body": "{If Learnhub is going after L&D and HR leads in ANZ, there are faster ways in:|A few L&D and HR lead signals most training teams are not picking up on:|Quick ways Learnhub could be finding more L&D and HR decision-makers right now:}\n{- Real-time alerts when a company appoints a new L&D or HR lead, reach them before competitors do.|- Firmable flags new L&D and HR hires across ANZ, reach them before the 90-day window closes.|- Signals when a new L&D or HR lead joins a company in ANZ, first-mover timing.}\n{- Official AU register of RTOs and independent schools, not a scraped list.|- Firmable holds the official AU register of RTOs and independent schools, not scraped data.|- AU government register of RTOs and independent schools, cleaner than any scraped list.}\n{- Verified direct mobiles for every HR and L&D decision-maker in ANZ, 22% connect rate vs ~5%.|- Direct mobiles for HR and L&D leads across ANZ, 22% connect rate vs ~5% average.|- Direct contact numbers for every L&D and HR hire in ANZ, 22% connect rate vs ~5%.}"
    },
    {
      "company_name": "Pipefy",
      "vertical": "SaaS Software",
      "has_sales_team": "Yes",
      "format": "plain_lines",
      "body": "{If Pipefy is going after RevOps and sales leads in ANZ, there are faster ways in:|A few RevOps signals most SaaS teams are not picking up on:|Quick ways Pipefy could be finding more RevOps and sales leads right now:}\n{Job change alerts when a RevOps or sales lead starts somewhere new, first 90-day buying window.|Real-time signals when a RevOps hire joins a new company, reach them in the first 90 days.|Firmable flags new RevOps and sales hires across ANZ, catch them before the 90-day window closes.}\n{Filter targets already running Salesforce in ANZ, dual-source detection from website plus job ads.|Find every company in ANZ using Salesforce, two detection methods for a stronger signal.|Firmable identifies Salesforce users across ANZ from website signals and job description analysis.}\n{Verified direct mobiles for every sales leader and RevOps manager in ANZ, 22% connect rate vs ~5%.|Direct mobiles for RevOps and sales leads across ANZ, 22% connect rate vs ~5% average.|Direct contact numbers for every sales leader in ANZ, 22% connect rate vs ~5% industry average.}"
    },
    {
      "company_name": "Sitelink",
      "vertical": "Construction Trade",
      "has_sales_team": "No",
      "format": "compact_prose",
      "body": "{Quick ways Sitelink could be finding more project managers and specifiers right now:|A few signals most construction-focused teams are not picking up on:|Some faster ways to reach project managers and specifiers in ANZ:}\n{Official AU register of commercial builders, filterable by state, company age, and size. Direct contact details for every PM and QS at tier 2 and tier 3 builders in ANZ, 22% connect rate vs ~5%.|Firmable holds the official AU register of commercial builders by state and size. Direct mobiles for every PM and QS at tier 2 and tier 3 builders, 22% connect rate vs ~5%.|AU government register of commercial builders, filterable by state. Direct numbers for project managers and quantity surveyors at mid-tier builders, 22% connect rate vs ~5%.}"
    },
    {
      "company_name": "Clearpath Finance",
      "vertical": "Finance Brokers",
      "has_sales_team": "No",
      "format": "plain_lines",
      "body": "{Quick ways to find more finance brokers that most teams targeting brokers overlook:|A few finance broker signals most outreach teams are missing:|Some faster ways Clearpath could be reaching more finance brokers right now:}\n{Official AFS register of 10,000+ AU finance brokers, filterable by state, size, and specialisation.|Firmable holds the official AFS register of AU finance brokers, filterable by state and niche.|AU government AFS register of 10,000+ finance brokers, not a scraped list.}\n{Alerts when a broker moves to a new firm, reach them while they are in setup mode.|Firmable flags when a broker changes firms, timing when they are reviewing supplier relationships.|Real-time signals when a finance broker moves to a new brokerage, first-mover window.}\n{Direct mobiles for every broker in the segment, 22% connect rate vs ~5% in financial services.|Verified direct numbers for finance brokers in the target niche, 22% connect rate vs ~5%.|Direct contact details for every broker in the AFS register, 22% connect rate vs ~5%.}"
    },
    {
      "company_name": "Apex Advisory",
      "vertical": "Accounting Advisory",
      "has_sales_team": "Yes",
      "format": "compact_prose",
      "body": "{A few CFO and finance lead signals most accounting advisory teams are not picking up on:|Some advisory inflection signals the Apex team could be acting on right now:|Quick ways to find more companies approaching an advisory inflection point:}\n{Real-time signals for M&A activity, leadership changes, and restructuring events across ANZ. Direct mobiles for CFOs and finance leads at flagged companies, 22% connect rate vs ~5%.|Firmable tracks M&A activity, leadership changes, and restructuring events across ANZ in real time. Direct numbers for CFOs and finance leads at companies showing those signals, 22% connect rate vs ~5%.|Buying signals for companies approaching advisory decisions: M&A, new c-suite, headcount restructure. Direct mobiles for CFOs and finance leads at those businesses, 22% connect rate vs ~5%.}"
    },
    {
      "company_name": "Growth Pipeline Co",
      "vertical": "BD Agencies",
      "has_sales_team": "No",
      "format": "compact_prose",
      "body": "{Quick ways Growth Pipeline Co could speed up list delivery for clients right now:|A few things most BD agencies are not using to build lists faster:|Some faster ways to build client ICP lists across ANZ:}\n{Filter any client ICP by technographic stack across ANZ, dual-source detection from website plus job ads. Verified direct mobiles for every decision-maker in a client ICP, 22% connect rate vs ~5%.|Find every company in ANZ using a client's target tool, two detection methods for stronger signal. Direct contact numbers for every decision-maker in the ICP, 22% connect rate vs ~5% for clients doing calls.|Technographic filters across ANZ for any client stack, website signals plus job description analysis. Direct mobiles for every decision-maker in a client ICP, 22% connect rate vs ~5%.}"
    },
    {
      "company_name": "Nexagen IT",
      "vertical": "IT MSP",
      "has_sales_team": "Yes",
      "format": "bullets",
      "body": "{A few IT decision-maker signals in ANZ that most MSP teams are not picking up on:|Quick ways Nexagen could be finding more SMB clients across ANZ:|Some faster ways to reach IT managers and business owners in the ANZ SMB market:}\n{- Find companies already running M365 or Azure across ANZ, dual-source detection from website plus job ads.|- Filter targets already using M365 or Azure in ANZ, two detection methods for a stronger signal.|- Firmable identifies M365 and Azure users across ANZ from website signals and job ad analysis.}\n{- ZoomInfo covers 500+ seat US enterprise. Firmable covers ANZ SMB in the 10-200 seat range.|- Most enterprise data tools are built for US 500+ seat companies. Firmable covers ANZ SMB, 10-200 seats.|- Apollo misses ~75% of AU B2B contacts. Firmable was built for this market.}\n{- Direct mobiles for IT managers and business owners across ANZ, 22% connect rate vs ~5%.|- Verified direct numbers for IT managers and business owners in ANZ, 22% connect rate vs ~5% average.|- Direct contact details for every IT manager and SMB owner across ANZ, 22% connect rate vs ~5%.}"
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
    "body": {
      "type": "string",
      "description": "Full email body as a single spintax string. Each component (bridge line + each idea) is wrapped in {variant1|variant2|variant3} with exactly 3 variants per block. Bridge line block: 8-15 words per variant, curiosity framing, no Firmable mention, ends with colon. Idea blocks: 15-25 words per variant, all in the same structural format chosen for this row (bullets/plain_lines/compact_prose). Total body under 70 words per variant path. Produces 3-4 spintax blocks total depending on whether 2 or 3 ideas apply."
    }
  },
  "required": ["body"]
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

**Single email + short follow-up**
- Email 1: `{body}` (the full assembled output from Column 8)
- Email 2 (3-4 days later): "Any thoughts on those?"

Column 8 outputs a single `body` string. Use it directly in SmartLead — no formula assembly needed.

---

## Campaign Setup Checklist

1. Pull company list from Firmable: B2B companies, ANZ, sales team <= 4, exclude recruitment vertical
2. Run through HubSpot eligibility check before upload (see `/smartlead-pre-campaign-check`)
3. Build Clay table in column order above (1 through 8)
4. Spot-check Column 8 output on 10-15 rows across different verticals before running full table
5. Write spintax opening lines separately — the sender writes these, not Column 8
6. Set up SmartLead campaign: Email 1 uses `{body}`, Email 2 is a short follow-up
7. Confirm lead count, campaign name, and sender before activating (see `/smartlead-push`)

---

## Known Issues and Fixes Applied

- Vertical names must use plain words with no dashes or special characters. Clay garbles "SaaS-Software" into "SaaS 6Software". Use "SaaS Software", "IT MSP", "BD Agencies", etc.
- Em dashes in output: the formatting_rules block explicitly bans em dashes at the top of the system prompt.
- Founder ICP exception: founders do not change companies. If ICP includes founders or owners, skip job change signals and use company growth signals instead.
- ICP repetition across ideas: use icp label in bridge line only. Ideas use descriptive alternatives.
- Column 8 uses 6 variables only: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.
- Short form only: bridge line must NOT mention Firmable. If Firmable appears in the bridge line, the curiosity framing is broken.
- Format fingerprinting: the AI picks one of three formats (bullets, plain_lines, compact_prose) per row. If spot-check shows all rows in the same format, add an explicit instruction in the main prompt for that row to use a different format variant.
- Single body field: Column 8 outputs `body` only. No formula assembly in Clay — use `{body}` directly in SmartLead.
- Spintax in body: each component (bridge line + each idea) is one `{...|...|...}` block. If spot-check shows fewer than 3 variants per block, the AI may have collapsed them — check the system prompt is being sent in full.

---

## Fixed Spintax Templates

These are NOT generated by Column 8. Paste them directly into your SmartLead email template. Combined with the `{body}` spintax from Column 8, a full email has 6-8 spintax blocks total.

### TLDR Block (5 variants) — paste after `{body}`

```
{TLDR: The Firmable platform provides contact data and buying signals like the ones above, enabling you to find warmer leads and increase the number of conversations with potential clients and partners.|In short, Firmable gives you contact data and signals like these to help you find warmer leads and have more conversations with potential clients and partners.|To put it simply, the Firmable platform combines contact data and signals like the ones above to help you surface warmer leads and drive more conversations.|Basically, Firmable puts these contact signals in your hands so you can find warmer leads and reach more potential clients and partners.|The short version: Firmable gives you the data and buying signals above to find warmer leads and get more conversations with the right people.}
```

### Social Proof + CTA Block (5 variants) — paste after TLDR

```
{We're already working with companies like Foodbank Australia, ProcurePro, and Cotiss in NZ. Worth a conversation to see how that might work for {{Normalized_Company_Name}}?|We're already partnering with companies like Foodbank Australia, ProcurePro, and Cotiss in NZ. Would it be worth a quick chat to explore how this could work for {{Normalized_Company_Name}}?|Companies like Foodbank Australia, ProcurePro, and Cotiss in NZ are already using Firmable. Keen to have a brief conversation about how this could apply to {{Normalized_Company_Name}}?|Foodbank Australia, ProcurePro, and Cotiss in NZ are all on Firmable already. Open to a quick call to see if it makes sense for {{Normalized_Company_Name}}?|We work with companies like Foodbank Australia, ProcurePro, and Cotiss in NZ. Happy to run through how this would look for {{Normalized_Company_Name}} if you're open to a quick chat.}
```

### Close Block (5 variants) — optional, use as standalone sign-off line

```
{Worth 15 minutes?|Open to a quick call?|Worth a conversation?|Keen to explore?|Happy to chat if useful?}
```

### Full SmartLead template structure

```
[Sender opening line — spintax written by sender]

{body}

{TLDR block}

{Social proof + CTA block}

{Close block}
```

Total spintax blocks: 1 (sender opening) + 3-4 (body: bridge + ideas) + 1 (TLDR) + 1 (social proof + CTA) + 1 (close) = **7-8 blocks**.
