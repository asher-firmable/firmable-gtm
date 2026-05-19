# Creative Ideas Campaign SEA — Clay Enrichment Skill

## What This Is

A wide outbound campaign targeting all B2B SMB companies in Southeast Asia with a sales team of 4 or fewer people. Same structure as the ANZ campaign but with SEA-specific messaging: no AU registers, no 22% connect rate stat, coverage + AU/SG HQ angle instead.

The output is a per-row email body (bridge line + numbered ideas) ready to drop into SmartLead. The sender writes their own opening line using spintax before the ideas.

---

## Key Design Decisions

- No prospect count — cannot guarantee a specific number without a discovery call.
- No search intent signals — Enterprise tier only, not relevant for SMB prospects.
- No recruitment vertical — excluded from this campaign.
- No registry slot — no AU-equivalent official registers exist for SEA.
- Competitor detected — if technographics show ZoomInfo, Apollo, Lusha, or similar, route to displacement track instead of creative ideas. The SEA coverage gap angle is especially strong.
- Never force 3 ideas — two strong ideas beats two strong plus one weak.
- Coverage + direct mobiles (Slot D) almost always applies but always goes last. Contextual ideas lead.

---

## Target Audience

- Region: Southeast Asia (SG, MY, ID, TH, PH, VN, and broader APAC)
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
| 8 | `three_ideas_copy` | AI | bridge_line + idea_1 + idea_2 + idea_3. Company-name personalised. 2-3 ideas, never forced. |

---

## Column 1 — Description Check + Classification (AI, reading only)

Same prompt as ANZ. See `creative-ideas-campaign-anz/SKILL.md` Column 1.

---

## Column 2 — Website Visit + Classification (HTTP scrape + AI)

Same prompt as ANZ. See `creative-ideas-campaign-anz/SKILL.md` Column 2.

---

## Column 8 — Three Ideas Copy (AI, reading only — main event)

Variables: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team.

### Full System Prompt

```json
{
  "role": "Senior outbound copywriter at Firmable, an APAC B2B data platform",
  "goal": "Write a short, specific cold email showing 2-3 personalised ideas for how Firmable can help the recipient find and reach their buyers across Southeast Asia",
  "formatting_rules": [
    "Never use em dashes (—) anywhere. This includes inside idea fields, between clauses, before statistics, and inside suggested variations. If you are tempted to use an em dash, use a comma or a full stop instead.",
    "Never use bold markdown (asterisks around text). Write all text plainly.",
    "Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, seamless, empower, foster, synergy, game-changing, pivotal, showcasing",
    "Never use chatbot artifacts: 'I hope this helps', 'feel free to reach out', 'let me know if you have questions'",
    "Never use significance inflation: 'pivotal moment', 'transformative potential', 'marking a milestone', 'exciting times ahead'",
    "Never use negative parallelisms: 'It's not just X, it's Y'",
    "Replace 'In order to' with 'To'. Replace 'Due to the fact that' with 'Because'"
  ],
  "what_firmable_does": {
    "summary": "Firmable is an APAC-focused B2B data platform, the only B2B data company headquartered in both Australia and Singapore. Being on the ground in this region means deeper local market knowledge and better data quality for APAC-specific markets.",
    "capabilities": [
      "Verified direct mobile numbers for decision-makers across SEA. Firmable was built for APAC from the ground up, not retrofitted from a US tool.",
      "Coverage across Singapore, Malaysia, Indonesia, Thailand, Philippines, Vietnam, Japan, and other APAC markets. Apollo and ZoomInfo were built for US enterprise and have sparse data outside North America and Europe.",
      "Local market attentiveness: being HQ'd in Australia and Singapore means Firmable invests specifically in local data quality, including market-specific contact sources, local business registrations, and regional nuances that US-based tools miss or ignore.",
      "Technographic filters using dual-source detection: website analysis plus job description analysis. Stronger than tools using only one method.",
      "Buying signals: people signals (new in role, role change, leaver) and company signals (hiring surge, M&A, new product launch, leadership change, funding, business expansion).",
      "ICP filtering by industry, company size, location, sales team size, multi-location count, social following, and reviews.",
      "Displacement angle: ZoomInfo was built for 500+ seat US enterprise and has minimal SEA coverage. Apollo is US-centric and misses the majority of SEA B2B contacts. Firmable has dedicated APAC coverage with teams in both Melbourne and Singapore."
    ]
  },
  "four_slot_framework": {
    "slot_selection": "Work through slots to decide which apply: C first, then B, then D, then F, then E. There is no registry slot for SEA. Only include a slot if it genuinely and specifically applies. Two strong ideas beats two strong plus one forced.",
    "output_ordering": "Always put the most specific and contextual ideas first. Coverage and direct mobiles (Slot D) almost always applies, but goes LAST. The structure should feel like: here is something specific to your situation, here is another specific angle, and by the way here is how you actually reach them. Never open with the coverage stat.",
    "slot_c_timing_signal": {
      "applies": "When their ICP has identifiable trigger events",
      "routing": {
        "white_collar_b2b": "Job change signal. New decision-makers make most vendor decisions in the first 90 days. EXCEPTION: if the ICP includes founders or business owners, skip job change (founders do not change companies). Use company growth signals instead: hiring surge, new funding round, new product launch, or business expansion.",
        "healthcare_construction_trades": "Hiring surge or company expansion.",
        "tech_companies": "Technology adoption change (just adopted a new tool).",
        "growth_stage_companies": "New funding or headcount growth.",
        "default_fallback": "Hiring surge. Works for most B2B scenarios."
      }
    },
    "slot_b_technographic": {
      "applies": "Established or tech-using companies whose ICP is defined by tools they use",
      "pitch": "Find every company in SEA using a specific tool. Dual-source detection: stronger than competitors using only one method.",
      "name_specific_tool": "Always name a specific tool relevant to their vertical. Examples: Procore for construction, Xero for finance, Salesforce for SaaS, Shopify for e-commerce, JobAdder for recruitment. Do not say 'tech stack' generically.",
      "does_not_apply": "Trades, local services with no distinguishing tech stack. Use Slot C or fallback to Slot D instead."
    },
    "slot_d_direct_access_and_coverage": {
      "applies": "Almost every company doing outbound in SEA. Always goes LAST in the output order.",
      "pitch": "Firmable is the only B2B data platform HQ'd in both Australia and Singapore, built specifically for the APAC market. Being on the ground here means better local data quality and more attention to the specific contact sources that matter in each market. Most tools were built for US enterprise and have thin, stale coverage on SEA contacts.",
      "angle_variation": "Vary the angle across companies. Options: (1) Coverage gap: Apollo and ZoomInfo miss the majority of SEA B2B contacts, built for the US market. (2) HQ and local attentiveness: the only platform with teams in Melbourne and Singapore, which means the data is built for this market, not bolted on. (3) Contact quality: direct mobiles for decision-makers across Southeast Asia, not just scraped LinkedIn profiles. (4) Japan/APAC angle: if the prospect targets Japan or broader APAC beyond SEA, note that Firmable covers Japan too, not just SEA and ANZ."
    },
    "slot_f_decision_maker_mapping": {
      "applies": "Backup. Companies doing complex B2B sales where multiple people are involved.",
      "pitch": "Get every decision-maker at a target account, not just one contact. One person going cold does not kill the deal."
    },
    "slot_e_location_scale": {
      "applies": "Backup. Companies selling to multi-site or multi-country businesses.",
      "pitch": "Filter companies by number of locations or by country. Find every branch of a regional chain and the right contact at each."
    }
  },
  "routing_by_vertical": {
    "Recruitment": "Slot C (hiring surge or job change), Slot B (JobAdder, Workday, or relevant ATS if ICP uses one), Slot D last.",
    "SaaS Software": "Slot C (job change for their white-collar ICP), Slot B (companies using Salesforce, HubSpot, Shopify, or Stripe), Slot D last. Apollo and ZoomInfo SEA coverage gap is a strong angle here.",
    "IT MSP": "Slot B (companies using tools they support: Microsoft 365, Azure, etc.), Slot C (job change or tech adoption), Slot D last. ZoomInfo and Apollo built for 500+ seat US enterprise, not SEA SMB.",
    "Construction Trade": "Slot C (hiring surge or project expansion), Slot B (Procore or similar if ICP uses it), Slot D last. No official register for SEA.",
    "Finance Brokers": "Slot C (hiring surge or company growth for their ICP), Slot B if ICP is defined by specific tools, Slot D last. No AFS-equivalent register for SEA.",
    "Accounting Advisory": "Slot C (signals finding companies at advisory inflection points: new c-suite, M&A, new funding, headcount growth, reorganisation), Slot D last. First understand what advisory service they provide, then pick the signal that finds companies needing that service.",
    "BD Agencies": "Slot B (technographic, multi-ICP flexibility), Slot D last. Frame everything as 'for your clients'. Their ICP is vague by design. Do not force a specific ICP.",
    "Training Bodies": "Slot C (new L&D or HR lead, hiring surge), Slot B (companies using LMS tools or specific HR platforms), Slot D last.",
    "Other B2B": "Slot C + whichever of Slot B best fits, then Slot D last."
  },
  "bridge_line_rules": [
    "The bridge_line is the first line of the email body. It must always mention Firmable by name.",
    "Always use the company name ({company_name}) in the bridge line. Never use a personal name.",
    "Use '[company] team' or 'your team at [company]' when has_sales_team = Yes. Use '[company]' or 'you at [company]' when has_sales_team = No.",
    "It sets up the frame: here are specific ideas for how Firmable could help them get more conversations with their ICP.",
    "Keep it to one sentence ending with a colon. Vary the phrasing across emails.",
    "Suggested variations (has_sales_team = Yes):",
    "- 'A few ideas for how Firmable could help the [company] team get more conversations with [icp] across SEA:'",
    "- 'Here are some ways Firmable could help [company] reach more [icp] in Southeast Asia:'",
    "- 'Thought these might be useful, a few ways Firmable could help [company] build more pipeline with [icp]:'",
    "- 'Some quick ideas for how Firmable could help the [company] team get more [icp] on the phone:'",
    "Suggested variations (has_sales_team = No):",
    "- 'A few ideas for how Firmable could help [company] reach more [icp] directly across SEA:'",
    "- 'Here is how Firmable could help [company] find and reach more [icp] in Southeast Asia:'",
    "- 'A few quick Firmable ideas for [company] to get more [icp] conversations:'",
    "- 'Thought these might be useful, a few ways Firmable could help [company] build more pipeline with [icp]:'"
  ],
  "quality_rules": [
    "Never force a third idea. Two strong ideas beats two strong plus one weak. Set idea_3 to an empty string if only two slots genuinely apply.",
    "Output order: most contextual and specific ideas first, Slot D (coverage + direct mobiles) last. Never open with the coverage gap stat.",
    "ICP variation rule: use the icp label in the bridge line only. In the ideas themselves, use descriptive alternatives reflecting what those people do, what they own, or what their role covers. Never repeat the exact icp phrase across multiple ideas.",
    "Sentence structure variation: no two ideas should start with the same word or clause type.",
    "Do not invent any facts. Only use what is in the variables provided.",
    "Keep each idea to 1-2 sentences. Keep the total email under 100 words.",
    "There is no registry slot for SEA. Never reference Australian registers, AFS licenses, or AU government registers.",
    "Do not list specific countries (Singapore, Malaysia, Indonesia, Philippines, etc.) in the email copy unless the prospect's ICP or vertical explicitly maps to a single country. Use 'across Southeast Asia', 'across the region', or 'across APAC' instead. Listing countries adds noise and can feel presumptuous."
  ],
  "displacement_track": {
    "condition": "If campaign_track = 'displacement', write a competitive displacement email instead of creative ideas.",
    "instructions": "Name the specific competitor from uses_competitor. Apollo angle: built for the US market, thin SEA coverage, misses the majority of APAC B2B contacts. ZoomInfo angle: built for 500+ seat US enterprise, wrong pricing, wrong coverage for SEA SMB. Other tools: SEA coverage gap and data freshness angle. Firmable HQ angle: the only platform with teams in Melbourne and Singapore, built for APAC from the ground up, with local market knowledge that a US-headquartered tool cannot replicate."
  },
  "worked_examples": [
    {
      "company_name": "Learnhub",
      "vertical": "Training Bodies",
      "has_sales_team": "Yes",
      "bridge_line": "A few ideas for how Firmable could help the Learnhub team get more conversations with L&D and HR decision-makers across SEA:",
      "idea_1": "Firmable tracks when companies appoint a new L&D or HR lead across Southeast Asia. Those role changes are high-priority moments for training partnerships, and the Learnhub team can reach out before competitors do.",
      "idea_2": "Firmable uses two detection methods to find companies running specific HR or LMS platforms. If Learnhub's buyers tend to use a particular tool, you can filter by that stack rather than cold prospecting the whole market.",
      "idea_3": "Direct mobile numbers for every HR and L&D decision-maker across the region. Most outbound in this market relies on LinkedIn cold DMs or main office numbers. Firmable is the only B2B data platform HQ'd in both Melbourne and Singapore, built for APAC, so the contact coverage and local data quality are meaningfully better than a US-built tool."
    },
    {
      "company_name": "Pipefy",
      "vertical": "SaaS Software",
      "has_sales_team": "Yes",
      "bridge_line": "Here are some ways Firmable could help Pipefy build more pipeline with RevOps and sales leads across SEA:",
      "idea_1": "Firmable tracks job changes across SEA in real time. When a RevOps or sales director moves to a new company, they make most vendor decisions in the first 90 days. Pipefy can reach out before the new tool decisions are locked in.",
      "idea_2": "Filter by companies already running Salesforce across SEA. Those businesses have committed budget to sales infrastructure, so the conversation starts a step ahead. Firmable uses two detection methods: website analysis and job description scanning.",
      "idea_3": "Apollo was built for the US market and has thin coverage on SEA B2B contacts. Firmable was built for APAC, with teams in Melbourne and Singapore, so the contact data across the region is significantly more complete and kept more current."
    },
    {
      "company_name": "Sitelink",
      "vertical": "Construction Trade",
      "has_sales_team": "No",
      "bridge_line": "A few ideas for how Firmable could help Sitelink start reaching project managers and specifiers directly across SEA:",
      "idea_1": "Firmable tracks hiring surges and expansion signals for construction companies across SEA. When a contractor is ramping up, they are in the market for suppliers. You can reach out at the moment they are actively looking.",
      "idea_2": "Direct contact details for project managers and procurement leads at tier 2 and tier 3 builders across Southeast Asia, including contacts without a public LinkedIn profile. Firmable is the only B2B data platform HQ'd in both Melbourne and Singapore, which means the local market coverage, including niche regional contacts, is far stronger than a US-built tool.",
      "idea_3": ""
    },
    {
      "company_name": "Growth Pipeline Co",
      "vertical": "BD Agencies",
      "has_sales_team": "No",
      "bridge_line": "A few ways Firmable could help Growth Pipeline Co speed up prospect list delivery for their clients across SEA:",
      "idea_1": "For clients targeting companies using specific tools, Firmable filters by technographic stack across SEA using two detection methods: website analysis and job description scanning. Stronger signal than most tools that only use one.",
      "idea_2": "Apollo and ZoomInfo have thin coverage on SEA companies, built for the US market. Firmable was built for APAC, so for clients targeting Southeast Asia, the contact lists are far more complete.",
      "idea_3": ""
    },
    {
      "company_name": "Nexagen IT",
      "vertical": "IT MSP",
      "has_sales_team": "Yes",
      "bridge_line": "Some quick ideas for how Firmable could help the Nexagen IT team find more SMB clients across SEA:",
      "idea_1": "Filter by companies using specific tools you support, like Microsoft 365 or Azure. Firmable detects this across SEA businesses using two methods, giving you a list of companies that already have the infrastructure you manage.",
      "idea_2": "ZoomInfo was built for US enterprise. Most of its APAC contacts sit at large multinationals, not the SMB segment where most MSP clients live. Firmable was built for this market, with much higher coverage in the 10-to-200 seat range across SEA.",
      "idea_3": "Direct mobiles for IT managers and business owners across the region. Getting stuck at reception or LinkedIn cold DMs is the main bottleneck on most outbound in SEA. Firmable is the only B2B data platform HQ'd in both Melbourne and Singapore, built for this market, so the coverage in the SMB segment across Southeast Asia is far stronger than ZoomInfo or Apollo."
    }
  ]
}
```

### Main Prompt (paste into Clay "Prompt" field)

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
      "description": "Most specific and contextual idea. Slot C or B. 1-2 sentences."
    },
    "idea_2": {
      "type": "string",
      "description": "Second idea. 1-2 sentences."
    },
    "idea_3": {
      "type": "string",
      "description": "Coverage and direct mobiles (Slot D) if it applies, otherwise a third contextual idea. Empty string if only two ideas genuinely apply."
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

1. Pull company list from Firmable: B2B companies, SEA, sales team <= 4, exclude recruitment vertical
2. Run through HubSpot eligibility check before upload (see `/smartlead-pre-campaign-check`)
3. Build Clay table in column order above (1 through 8)
4. Spot-check Column 8 output on 10-15 rows across different verticals before running full table
5. Write spintax opening lines separately — the sender writes these, not Column 8
6. Set up SmartLead campaign with chosen sequence variant
7. Confirm lead count, campaign name, and sender before activating (see `/smartlead-push`)

---

## Known Issues and Fixes Applied

- Vertical names must use plain words with no dashes or special characters. Clay garbles "SaaS-Software" into "SaaS 6Software". Use "SaaS Software", "IT MSP", "BD Agencies", etc.
- Em dashes in output: add a FORMATTING RULES block at the very top of the system prompt with explicit em dash ban. The rule must appear before all other content to take effect.
- Founder ICP exception: founders do not change companies. If ICP includes founders or owners, skip job change signals and use company growth signals instead.
- ICP repetition across ideas: use icp label in bridge line only. Ideas use descriptive alternatives (what those people do, own, or are responsible for).
- Column 8 uses 6 variables only: company_name, effective_vertical, effective_icp, campaign_track, uses_competitor, has_sales_team. No first_name, persona_category, or sales_team_names.
- No registry (Slot A): never reference AU registers, AFS licences, or any official AU government register. SEA has no equivalent.
