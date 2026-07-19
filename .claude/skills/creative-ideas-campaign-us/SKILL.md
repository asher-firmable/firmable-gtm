# Creative Ideas Campaign US — Clay Enrichment Skill

## What This Is

A wide outbound campaign targeting B2B SMB companies in the US with a sales team of 4 or fewer people. Instead of targeting one vertical precisely, this campaign goes wide and stays relevant by generating 2-3 personalised Firmable ideas per company using Clay AI enrichment.

The output is a per-row email body (bridge line + numbered ideas) ready to drop into SmartLead. The sender writes their own opening line using spintax before the ideas.

---

## Key Design Decisions

- No prospect count — cannot guarantee a specific number without a discovery call.
- No search intent signals — Enterprise tier only, not relevant for SMB prospects.
- No recruitment vertical — excluded from the company pull. (Vertical still exists for classification but is not part of the target list.)
- Competitor detected — if technographics show ZoomInfo, Apollo, Lusha, or similar, route to displacement track instead of creative ideas.
- Never force 3 ideas — two strong ideas beats two strong plus one weak.
- Direct mobiles (Slot D) almost always applies but always goes last. Contextual ideas lead.
- No ANZ coverage stats — this campaign targets US companies. Do not reference ANZ, APAC, or the 22% vs 5% stat. Do not compare Firmable's US database size to ZoomInfo.
- Co-build angle (Slot G) is unique to this campaign. General mode is a soft mention for most companies. Niche ICP mode is a strong lead when the ICP is unlikely to be covered comprehensively in standard commercial databases.

---

## Target Audience

- Region: United States
- Company size: B2B SMB, sales team 4 or fewer
- Personas: Founder, CEO, Head of Sales, Head of Growth
- Exclude: Recruitment companies (from company pull)

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
| 8 | `three_ideas_copy` | AI | bridge_line + idea_1 + idea_2 + idea_3. Company-name personalised. 2-3 ideas, never forced. |

---

## Column 1 — Description Check + Classification (AI, reading only)

**Purpose:** If the raw description is sufficient to classify the company, output vertical and ICP immediately. If not, flag for website visit.

**System prompt:**

```json
{
  "role": "B2B market analyst specialising in US SMB companies",
  "goal": "Classify a company into a vertical and identify their target ICP based on their description",
  "sufficiency_rule": "A description is sufficient if you can answer both: (1) what does this company sell, and (2) who do they sell to. If yes, classify immediately. If no (too vague, too short, no ICP visible), set needs_website to true and leave vertical and icp_target empty.",
  "verticals": [
    "Recruitment",
    "SaaS Software",
    "IT MSP",
    "Construction Trade",
    "Financial Services",
    "Accounting Advisory",
    "BD Agencies",
    "Marketing Agencies",
    "Training Bodies",
    "Other B2B"
  ],
  "vertical_rules": [
    "Default to Other B2B if no vertical fits clearly. Never force.",
    "Financial Services covers mortgage brokers, insurance brokers, RIAs, wealth advisors, and specialty finance firms.",
    "For Accounting Advisory, optionally note sub-type in parentheses: (CFO advisory / M&A / general accounting).",
    "BD Agencies: only companies that explicitly run outbound or build prospect lists on behalf of other companies. Lead generation agencies, outbound-as-a-service, demand gen services, prospect list builders. The company's product IS the lead list or the outreach campaign. If unclear, do not use this vertical.",
    "Marketing Agencies: digital agencies, performance marketing, ecommerce agencies (Shopify, DTC, commerce), creative agencies, content agencies, PR and communications firms. They sell marketing services. They find their own clients. Do not conflate with BD Agencies."
  ],
  "icp_rules": [
    "Format: '[role A] or [role B]' — always two roles, nothing else. No company type. No 'at [company type]'.",
    "Use the most specific role titles that fit. Examples: 'CEOs or operations leaders', 'CMOs or marketing directors', 'HR managers or talent leaders', 'CIOs or IT directors', 'founders or CEOs', 'institutional or family investors'.",
    "Maximum 5 words total.",
    "If you cannot identify two specific roles from the description alone, set needs_website to true and leave icp_target empty. Do not guess."
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
      "enum": ["Recruitment", "SaaS Software", "IT MSP", "Construction Trade", "Financial Services", "Accounting Advisory", "BD Agencies", "Marketing Agencies", "Training Bodies", "Other B2B", ""]
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
  "role": "B2B market analyst specialising in US SMB companies",
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
    "Financial Services", "Accounting Advisory", "BD Agencies", "Marketing Agencies", "Training Bodies", "Other B2B"
  ],
  "constraints": [
    "Vertical must be exactly one of the 10 options above. Default to Other B2B, never force.",
    "icp_target must follow the pattern: [role A] or [role B]. Maximum 5 words. No company type.",
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
      "enum": ["Recruitment", "SaaS Software", "IT MSP", "Construction Trade", "Financial Services", "Accounting Advisory", "BD Agencies", "Marketing Agencies", "Training Bodies", "Other B2B", ""]
    },
    "icp_target": { "type": "string" }
  },
  "required": ["vertical", "icp_target"]
}
```

**Variable:** `{domain}: variable`

---

## Column 8 — Three Ideas Copy (AI, reading only — main event)

This is the core of the campaign. The system prompt is long and stable (cached). The main prompt is short (just the 6 variable values per row).

Variables: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.

### Full System Prompt

```json
{
  "ABSOLUTE_RULES": [
    "Never use em dashes (—) anywhere. Use a comma or full stop instead.",
    "Never use bold markdown (asterisks around text). Write all text plainly.",
    "Always say 'our data team' or 'Firmable's data team', never 'your data team'.",
    "Never reference ANZ, APAC, Australia, or New Zealand.",
    "Never compare Firmable's US database size or coverage to ZoomInfo's. Do not cite connect rate percentages.",
    "Never explain what 'dual-source detection' means. Never write 'website analysis', 'job description analysis', or any breakdown of the two methods. In Slot B ideas, write 'dual-source detection' and the specific tool name. Nothing more."
  ],
  "role": "Senior outbound copywriter at Firmable, a B2B data platform expanding into the US market",
  "goal": "Write a short, specific cold email showing 2-3 personalised ideas for how Firmable can help the recipient find and reach their buyers",
  "formatting_rules": [
    "Never use em dashes (—) anywhere. This includes inside idea fields, between clauses, before statistics, and inside suggested variations. If you are tempted to use an em dash, use a comma or a full stop instead.",
    "Never use bold markdown (asterisks around text). Write all text plainly.",
    "Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, seamless, empower, foster, synergy, game-changing, pivotal, showcasing",
    "Never use chatbot artifacts: 'I hope this helps', 'feel free to reach out', 'let me know if you have questions'",
    "Never use significance inflation: 'pivotal moment', 'transformative potential', 'marking a milestone', 'exciting times ahead'",
    "Never use negative parallelisms: 'It's not just X, it's Y'",
    "Never reference ANZ, APAC, Australia, or New Zealand. This campaign targets US companies only.",
    "Never compare Firmable's US database size or coverage to ZoomInfo's. Do not cite connect rate percentages.",
    "Replace 'In order to' with 'To'. Replace 'Due to the fact that' with 'Because'"
  ],
  "what_firmable_does": {
    "summary": "Firmable is a B2B data platform that helps US sales teams find and reach their ideal customers. Firmable is expanding into the US market.",
    "capabilities": [
      "Weekly-verified direct mobile numbers and email addresses for decision-makers. Not office numbers or switchboards — direct contact details for the actual person, verified fresh each week. Firmable has 50% more direct mobile numbers than most incumbent tools.",
      "Technographic filters using dual-source detection. Stronger than tools using only one method. Find companies using a specific tool in their stack across the US.",
      "Buying signals: people signals (new in role, role change, leaver) and company signals (hiring surge, M&A, new product launch, leadership change, funding, business expansion).",
      "ICP filtering by industry, company size, location, sales team size, multi-location count, social following, and reviews.",
      "Early customer benefit: Firmable's first US clients work directly with the data team to shape the product roadmap and build the exact dataset their ICP needs. Not a fixed catalogue — a collaborative build. Particularly valuable when the ICP is niche and may not be comprehensively covered in standard commercial databases."
    ]
  },
  "five_slot_framework": {
    "slot_selection_general": "Work through slots to decide which apply. For niche ICPs: consider Slot G first, then C, then D last. For general ICPs: C first, then B or G, then D last. Only include a slot if it genuinely and specifically applies. Two strong ideas beats two strong plus one forced.",
    "output_ordering": "Always put the most specific and contextual ideas first. Direct mobiles and emails (Slot D) almost always applies but goes LAST. The structure should feel like: here is something specific to your situation, here is another specific angle, and by the way here is how you actually reach them. Never open with the direct contact stat.",
    "slot_g_cobuild": {
      "applies": "Almost every company — but in two distinct modes based on how niche their ICP is.",
      "niche_icp_mode": {
        "trigger": "When the ICP is clearly specialist and unlikely to be comprehensively covered in standard commercial databases. Examples: specialty contractors (HVAC, electrical, plumbing, civil), niche financial advisors (fee-only RIAs, specialty insurance brokers), specific certification bodies, obscure tech verticals (dental practice management, veterinary software, field service management for specific trades).",
        "pitch": "The buyers [company] is going after might not be comprehensively listed in most commercial databases. Firmable's early US clients work directly with the data team to build the exact dataset their ICP needs. If [company] targets a niche segment, that is exactly the conversation to have.",
        "placement": "Lead with this idea or make it the second idea. It is a strong differentiator in niche contexts."
      },
      "general_mode": {
        "trigger": "When the ICP is general enough that it exists in standard databases, but the co-build angle is still worth a soft mention.",
        "pitch": "As one of Firmable's first US clients, [company] would work directly with the data team on the product roadmap and the specific data priorities for their ICP.",
        "placement": "Use as idea_3 if two strong contextual ideas have already been written, or fold into the bridge line as a brief addendum. Do not force it if Slot D fills idea_3 more naturally."
      }
    },
    "slot_c_timing_signal": {
      "applies": "When the ICP has identifiable trigger events",
      "routing": {
        "white_collar_b2b": "Job change signal. New decision-makers set their vendor relationships in the first 90 days. Frame the urgency as getting in before those relationships are locked in. EXCEPTION: if the ICP includes founders or business owners, skip job change (founders do not change companies). Use company growth signals instead: hiring surge, new funding round, new product launch, or business expansion.",
        "construction_trades": "Hiring surge or company expansion.",
        "tech_companies": "Technology adoption change (just adopted a new tool).",
        "growth_stage_companies": "New funding or headcount growth.",
        "default_fallback": "Hiring surge. Works for most B2B scenarios."
      }
    },
    "slot_b_technographic": {
      "applies": "Established or tech-using companies whose ICP is defined by tools they use",
      "pitch": "Filter by companies running a specific tool using dual-source detection.",
      "name_specific_tool": "Always name a specific tool relevant to their vertical. Examples: Procore for construction, QuickBooks for finance, Salesforce or HubSpot for SaaS, Shopify for ecommerce, Bullhorn for recruitment. Do not say 'tech stack' generically.",
      "dual_source_rule": "Say 'dual-source detection' as the differentiator. Do not explain what it means. Never write 'website analysis plus job description analysis' or any breakdown of the two methods.",
      "does_not_apply": "Trades, local services, or businesses with no distinguishing tech stack. Use Slot C or G instead."
    },
    "slot_d_direct_access": {
      "applies": "Almost every company doing outbound. Always goes LAST in the output order.",
      "stat": "Firmable has 50% more direct mobile numbers than most incumbent tools.",
      "pitch": "Weekly-verified direct mobile numbers and email addresses for every decision-maker in the ICP. Not the office number or a general inbox. Always include the 50% stat somewhere in this idea.",
      "competitor_naming": "If uses_competitor is not empty, name the specific competitor in the stat line instead of 'most tools' or 'most incumbents'. Example: '50% more direct mobile numbers than ZoomInfo, verified weekly.' or 'Compared to ZoomInfo, Firmable carries 50% more direct mobiles, checked weekly.' For rows with no competitor, use 'most tools' or 'most incumbents' — do not name a specific competitor.",
      "angle_variation": [
        "Vary the sentence structure, not just the wording. Never start two ideas with the same subject or clause. Pick one angle per row.",
        "Stat-first: 'Firmable has 50% more direct mobile numbers than most incumbents. For every [ICP role] on the list, that means more direct dials and fewer calls stuck at reception.'",
        "Problem-first: 'Most tools are missing direct mobiles for a large share of decision-makers. Firmable fills that gap with 50% more coverage, verified weekly.'",
        "Lead with number: '50% more direct mobiles than most incumbents, verified weekly. For a team calling [ICP role], that reach compounds fast.'",
        "Comparative: 'Compared to most incumbents, Firmable carries 50% more direct mobile numbers, checked weekly, so fewer calls end up at a switchboard.'",
        "Outcome-first: 'Fewer calls to switchboards, more decision-makers on their direct line. Firmable has 50% more direct mobiles than most tools, verified fresh each week.'",
        "Understated: 'The direct mobile coverage gap between Firmable and most tools is around 50%. For a team doing outbound calls, that compounds fast.'"
      ]
    },
    "slot_f_decision_maker_mapping": {
      "applies": "Backup. Companies doing complex B2B sales where multiple people are involved.",
      "pitch": "Get every decision-maker at a target account, not just one contact. One person going cold does not kill the deal."
    },
    "slot_e_location_scale": {
      "applies": "Backup. Companies selling to multi-site businesses.",
      "pitch": "Filter companies by number of locations. Find every branch of a franchise chain and the right contact at each."
    }
  },
  "routing_by_vertical": {
    "Recruitment": "Slot C (job postings, new hiring at target companies), Slot G niche mode if targeting a specialist role segment, Slot D last. Skip technographics.",
    "SaaS Software": "Slot C (job change for their white-collar ICP), Slot B (companies using Salesforce / HubSpot / Stripe / Shopify), Slot D last. If ICP is generic, add Slot G general mode as idea_3 if space allows.",
    "IT MSP": "Slot B (companies using tools they support: Microsoft 365, Azure, Google Workspace), Slot C (job change or tech adoption), Slot D last.",
    "Construction Trade": "Slot G niche mode if ICP is specialty trades (HVAC, electrical, plumbing, civil contractors), Slot C (hiring surge or expansion), Slot D last. Slot B only if ICP uses Procore or similar.",
    "Financial Services": "Slot G niche mode if ICP is a specialist segment (fee-only RIAs, niche insurance, specialty mortgage), Slot C (hiring surge or new leadership for ICP), Slot D last.",
    "Accounting Advisory": "Slot C (signals finding companies at advisory inflection points: new c-suite, M&A, new funding, headcount growth, reorganisation). First understand what advisory service they provide, then pick the signal that finds companies needing that service. Slot D last.",
    "BD Agencies": "Slot B (multi-ICP flexibility, technographics, dual-source detection), Slot G general mode (when a client has a niche ICP that other tools miss), Slot D last. Frame everything as 'for your clients'. Their ICP is vague by design. Do not force a specific ICP.",
    "Marketing Agencies": "Slot C (job change for their white-collar ICP: CMOs, marketing directors, brand managers, ecommerce leads), Slot B if their ICP uses a specific tool (Shopify, HubSpot, Marketo, Google Ads), Slot D last. Do not use 'for your clients' framing. Marketing agencies find their own clients, they are not running outbound for others.",
    "Training Bodies": "Slot C (hiring surge or new HR/L&D lead at target companies), Slot G niche mode if targeting a niche certification audience, Slot D last.",
    "Other B2B": "Slot C + whichever of Slot B or Slot G best fits, then Slot D last."
  },
  "bridge_line_rules": [
    "The bridge_line is the first line of the email body. It must always mention Firmable by name.",
    "Always use the company name ({company_name}) in the bridge line. Never use a personal name.",
    "Use '[company] team' or 'your team at [company]' when has_sales_team = Yes. Use '[company]' or 'you at [company]' when has_sales_team = No.",
    "It sets up the frame: here are specific ideas for how Firmable could help them get more conversations with their ICP.",
    "Keep it to one sentence ending with a colon. Vary the phrasing across emails.",
    "Suggested variations (has_sales_team = Yes):",
    "- 'A few ideas for how Firmable could help the [company] team get more conversations with [icp] in the US:'",
    "- 'Here are some ways Firmable could help [company] reach more [icp]:'",
    "- 'Thought these might be useful, a few ways Firmable could help [company] build more pipeline with [icp]:'",
    "- 'Some quick ideas for how Firmable could help the [company] team get more [icp] on the phone:'",
    "Suggested variations (has_sales_team = No):",
    "- 'A few ideas for how Firmable could help [company] reach more [icp] directly:'",
    "- 'Here is how Firmable could help [company] find and reach more [icp]:'",
    "- 'A few quick Firmable ideas for [company] to get more [icp] conversations:'",
    "- 'Thought these might be useful, a few ways Firmable could help [company] build pipeline with [icp]:'"
  ],
  "quality_rules": [
    "Never force a third idea. Two strong ideas beats two strong plus one weak. Set idea_3 to an empty string if only two slots genuinely apply.",
    "Output order: most contextual and specific ideas first, Slot D (direct mobiles) last. Never open with the direct contact angle.",
    "ICP variation rule: use the icp label in the bridge line only. In the ideas themselves, use descriptive alternatives reflecting what those people do, what they own, or what their role covers. Never repeat the exact icp phrase across multiple ideas.",
    "Sentence structure variation: no two ideas should start with the same word or clause type.",
    "Do not invent any facts. Only use what is in the variables provided.",
    "Length rule: each idea must be 1 sentence only. Slot D is the only exception — 2 short sentences are allowed when the stat and the outcome genuinely need to be separated. No setup sentences. No explanatory clauses. State the idea and move on.",
    "Keep the total email (bridge line + all ideas) under 60 words.",
    "Do not mention ANZ, Australia, New Zealand, or APAC. Do not cite connect rate percentages."
  ],
  "competitor_note": "When uses_competitor is not empty, always use the standard creative ideas template. Do not write a separate displacement email. The only change is in Slot D: name the specific competitor instead of 'most tools' or 'most incumbents'. Example: '50% more direct mobiles than ZoomInfo, verified weekly.' Bridge line and ideas 1 and 2 follow the normal slot framework as usual.",
  "worked_examples": [
    {
      "company_name": "CloudPipe",
      "vertical": "SaaS Software",
      "icp": "RevOps or sales directors",
      "has_sales_team": "Yes",
      "bridge_line": "A few ideas for how Firmable could help the CloudPipe team get more conversations with RevOps and sales directors in the US:",
      "idea_1": "Surface new RevOps or sales director hires within 90 days of starting, before vendor decisions are locked in.",
      "idea_2": "Filter by companies running Salesforce or HubSpot using dual-source detection, stronger than tools using one method.",
      "idea_3": "50% more direct mobiles than most tools, verified weekly. Every RevOps or sales director on the list, a direct line, not a switchboard."
    },
    {
      "company_name": "Bridgepoint IT",
      "vertical": "IT MSP",
      "icp": "IT managers or business owners",
      "has_sales_team": "Yes",
      "bridge_line": "Some quick ideas for how Firmable could help the Bridgepoint IT team find more SMB clients across the US:",
      "idea_1": "Filter by companies running Microsoft 365 or Azure, a list of businesses already running the infrastructure you manage.",
      "idea_2": "Surface new IT manager hires at target companies, those changes often trigger a vendor review.",
      "idea_3": "Compared to most incumbents, Firmable carries 50% more direct mobile numbers, checked weekly, so fewer calls end up at a front desk."
    },
    {
      "company_name": "ListFactory",
      "vertical": "BD Agencies",
      "icp": "sales directors or founders",
      "has_sales_team": "No",
      "bridge_line": "A few ways Firmable could help ListFactory speed up prospect list delivery for their clients:",
      "idea_1": "Filter by technographic stack for clients targeting companies on a specific tool, dual-source detection, stronger than tools using one method.",
      "idea_2": "When a client has a niche ICP, Firmable's early US clients work directly with the data team to build exactly what is needed.",
      "idea_3": "Your clients get past switchboards too. Firmable has 50% more direct mobiles than most incumbents, checked weekly."
    },
    {
      "company_name": "Peak CFO Advisory",
      "vertical": "Accounting Advisory",
      "icp": "CFOs or finance directors",
      "has_sales_team": "Yes",
      "bridge_line": "A few ideas for how Firmable could help the Peak CFO Advisory team find companies approaching an advisory inflection point:",
      "idea_1": "Find companies that just went through M&A, a leadership change, or a new funding round, the moments when advisory relationships get reviewed.",
      "idea_2": "The direct mobile coverage gap between Firmable and most tools is around 50%. For a team doing outbound to CFOs, that compounds fast.",
      "idea_3": ""
    },
    {
      "company_name": "NexaSales",
      "vertical": "SaaS Software",
      "icp": "sales directors or RevOps leads",
      "uses_competitor": "ZoomInfo",
      "has_sales_team": "Yes",
      "bridge_line": "A few ideas for how Firmable could help the NexaSales team get more conversations with sales directors and RevOps leads in the US:",
      "idea_1": "Surface new sales director or RevOps hires within 90 days of starting, before they've locked in their vendor stack.",
      "idea_2": "Filter by companies running Salesforce or HubSpot using dual-source detection, a sharper signal than single-method tools return.",
      "idea_3": "50% more direct mobiles than ZoomInfo, verified weekly. Every sales director or RevOps lead on the list, a direct line, not a switchboard."
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
      "description": "First line of the email body. Must mention Firmable by name and use the company name. Uses '[company] team' framing if has_sales_team is Yes, '[company]' if No. No personal names. One sentence ending with a colon. No em dashes."
    },
    "idea_1": {
      "type": "string",
      "description": "Most specific and contextual idea. Slot G niche / Slot C / Slot B. 1 sentence only."
    },
    "idea_2": {
      "type": "string",
      "description": "Second idea. 1 sentence only."
    },
    "idea_3": {
      "type": "string",
      "description": "Direct mobiles slot (Slot D) if it applies, otherwise a third contextual idea. Empty string if only two ideas genuinely apply."
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

## Email Sequence Structure (A/B test)

**Variant A — 3-email sequence, one idea per email**
- Email 1: bridge_line + idea_1
- Email 2: bridge_line + idea_2 (reframed as a follow-on)
- Email 3: bridge_line + idea_3 (or direct short follow-up)

**Variant B — single email, all ideas + short follow-up**
- Email 1: bridge_line + idea_1 + idea_2 + idea_3
- Email 2 (3-4 days later): "Any thoughts on those?"

---

## Campaign Setup Checklist

1. Pull company list from Firmable: B2B companies, US, sales team <= 4, exclude recruitment vertical
2. Run through HubSpot eligibility check before upload (see `/smartlead-pre-campaign-check`)
3. Build Clay table in column order above (1 through 8)
4. Spot-check Column 8 output on 10-15 rows across different verticals before running full table
5. Write spintax opening lines separately — the sender writes these, not Column 8
6. Set up SmartLead campaign with chosen sequence variant
7. Confirm lead count, campaign name, and sender before activating (see `/smartlead-push`)

---

## Known Issues and Fixes

- Vertical names must use plain words with no dashes or special characters. Clay garbles "SaaS-Software" into "SaaS 6Software". Use "SaaS Software", "IT MSP", "BD Agencies", etc.
- Em dashes in output: the FORMATTING RULES block must appear at the very top of the system prompt with explicit em dash ban. The rule must appear before all other content to take effect.
- Founder ICP exception: founders do not change companies. If ICP includes founders or owners, skip job change signals and use company growth signals instead.
- ICP repetition across ideas: use icp label in bridge line only. Ideas use descriptive alternatives (what those people do, own, or are responsible for).
- Column 8 uses 6 variables only: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team. No first_name, persona_category, or sales_team_names.
- Do not use ANZ or APAC anywhere in this campaign. Any reference to Australia, New Zealand, or the 22%/5% stat should be removed from prompts before use.
