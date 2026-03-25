# ICP Definition

> This file is the single source of truth for account qualification. Skills reference it. Update it whenever we learn something new about what makes a good or bad fit.

Used by lead scoring scripts to assign a numeric score and tier to each company or contact.
Total score determines routing: which outreach track, which SmartLead campaign, or whether to flag for manual review.

---

## Core Principles

### 1. Seniority / Buying Power
Firmable targets **managers, leaders, and decision-makers** — people with budget authority or strong purchasing influence for their team. Individual contributors (AEs, SDRs, Recruitment Consultants, Sales Reps) do not qualify even if they personally do B2B outreach, because they are *users* not *buyers*.

**ICP YES seniority** (manager, leader, or decision-maker with buying power or strong influence):
- Manager, Head of, Director, VP, C-suite, GM, Partner
- Founder / Co-Founder / CEO / MD / Managing Director
- Ops and enablement roles at manager level that influence tool/tech decisions (e.g. Business Operations Manager, Revenue Operations Manager, Marketing Operations Manager, Demand Generation Manager)
- SDR Manager, BDR Manager, Sales Development Manager
- `[Geography/Country/Region] Lead`, `Market Lead`, `Country Lead` — titles indicating ownership of a geographic market with business development or expansion mandate (equivalent to a regional director)
- "Lead" titles where context confirms team leadership responsibility

**ICP NO seniority** (individual contributors — excluded regardless of industry or company type):
- Account Executive, Senior AE, Mid-Market AE, Enterprise AE
- Sales Representative, Sales Rep
- Sales Development Representative, BDR, SDR (without "Manager")
- Recruitment Consultant, Senior/Principal Consultant (IC billing roles without team management)
- Account Manager, Customer Success Manager (individual book of business)
- Brand Ambassador, Sales Ambassador
- Specialist, Coordinator, Associate, Analyst

> **Title-prefix note:** Seniority-sounding prefixes like "Director" or "Senior" do not automatically qualify. Always check whether the underlying role is a team leader or an individual contributor (e.g. "Director, Enterprise Account Executive" = IC AE, not a director).

> **Default when uncertain:** If the title is manager/above AND the company has any plausible B2B dimension, classify as Yes. Do NOT use company size as a filter — sales team size data will come from the Firmable API separately and is used for scoring, not qualification.

### 2. B2B Outreach Intent
The **company** must proactively contact other businesses as part of its commercial or operational activity — whether to sell products or services, sell sponsorships or event packages, raise corporate donations, fill roles (recruitment), or develop strategic partnerships.

**The outreach motion matters, not the industry label. Interpret this loosely.**

Examples of qualifying outreach motions that may not look like "traditional sales":
- A charity that solicits donations from corporate sponsors → same outbound BD motion as a SaaS company
- An events company selling sponsorship packages to businesses → same prospecting need as a B2B sales team
- A recruitment firm placing candidates with corporate clients → BD-heavy outbound motion

When classifying a contact, ask two questions: **(1) Is this person a manager or above?** **(2) Does their company reach out to other businesses?** Both must be true for ICP Yes. For ambiguous company types, check the company website for B2B signals before deciding.

---

## Scoring Dimensions

### 1. Sales Team Size
*Sourced from Firmable API (`sales_team_size` field). Higher is always better.*

| Sales Team Size | Points |
|-----------------|--------|
| 20+             | 25     |
| 10–19           | 20     |
| 5–9             | 15     |
| 2–4             | 8      |
| 1               | 3      |
| 0 / unknown     | 0      |

---

### 2. Company Type / Industry
*Based on industry classification returned by Firmable or Clay enrichment.*

| Company Type                                  | Points | Notes                                                      |
|-----------------------------------------------|--------|------------------------------------------------------------|
| SaaS / Software                               | 25     | Highest fit — outbound-driven, budget exists, APAC-focused |
| Recruitment / Staffing                        | 20     | High BD activity, large contact databases, APAC-focused    |
| Consulting / Professional Services            | 15     | B2B sales motion, often ANZ-focused                        |
| Financial Services                            | 15     | B2B sales, compliance-conscious (DNC fit is a plus)        |
| Events / Sponsorship Sales                    | 15     | Sells sponsorship packages or event spaces to businesses — active B2B outreach motion |
| Real Estate / PropTech                        | 12     | B2B sales teams, APAC footprint                            |
| Non-profit with corporate fundraising         | 12     | Solicits donations or partnerships from corporate sponsors — same outbound motion as B2B sales |
| Other B2B (logistics, construction, etc.)     | 8      | Moderate fit — evaluate on other signals                   |
| B2C / Consumer (no B2B revenue line)          | 0      | Poor fit — no outbound B2B motion. Note: B2C companies with a sponsorship or corporate sales arm still qualify. |
| Unknown / Unclear                             | 0      |                                                            |

---

### 3. Sales Function Signals
*Detected from job postings, LinkedIn headcount by department, or contact titles in the company.*

| Signal                                                                 | Points | Notes                                                     |
|------------------------------------------------------------------------|--------|-----------------------------------------------------------|
| SDR / BDR roles exist (job postings or headcount detected)             | 20     | Mature outbound motion — highest signal                   |
| Sales team with AE / Account Manager roles                             | 12     | Established sales function                                |
| Recruitment consultants (BD-style role in a recruitment firm)          | 20     | Direct analogue to SDR in this vertical                   |
| Founder-led sales (no sales titles, small team)                        | 5      | Potential fit but lower priority                          |
| No sales function signals                                              | 0      |                                                           |

---

### 4. Competitive Tech Stack
*Detected via Firmable technographics or Clay enrichment. These companies are problem-aware and open to switching.*

| Tech Detected                         | Points | Track                    |
|---------------------------------------|--------|--------------------------|
| ZoomInfo                              | 20     | Problem-aware (APAC gap) |
| Apollo.io                             | 20     | Problem-aware (APAC gap) |
| Lusha                                 | 20     | Problem-aware (APAC gap) |
| Cognism                               | 20     | Problem-aware (APAC gap) |
| LinkedIn Sales Navigator only         | 10     | Semi-aware               |
| No outbound data tool detected        | 0      | Not problem-aware        |

> **Note:** If competitive tech is detected, route to the competitor displacement email track regardless of total score.

---

## Score Tiers

| Total Score | Tier   | Routing                                                                 |
|-------------|--------|-------------------------------------------------------------------------|
| 70+         | Tier 1 | Priority. Flag for call-first outreach if competitive tech detected. Else top email sequence. |
| 40–69       | Tier 2 | Standard email sequence.                                                |
| 20–39       | Tier 3 | Lower priority. Nurture sequence or hold for future campaign.           |
| <20         | DQ     | Do not contact. Remove from active lists.                               |

---

## Maximum Possible Score

| Dimension             | Max Points |
|-----------------------|------------|
| Sales team size       | 25         |
| Company type          | 25         |
| Sales function signal | 20         |
| Competitive tech      | 20         |
| **Total**             | **90**     |

---

## Notes
- Scores are additive. Award points from each dimension independently.
- Sales team size data comes from the Firmable API — if unavailable, score 0 for that dimension and note as `sales_team_size_unknown`.
- Competitive tech detection is a routing override: regardless of tier, detected ZoomInfo/Apollo/Lusha/Cognism users go to the competitor displacement track.
- DNC exclusion is applied before scoring — see `knowledge/exclusions.md`.
- Update this rubric as new signals are validated against conversion data.

---

## Qualification Checklist

Use this when manually qualifying an account (A/B/C/D tier):

**A — Strong fit (all boxes checked)**
- [ ] Manager-level or above contact available
- [ ] Company has clear B2B outreach motion
- [ ] Sales team signals present (SDR/BDR roles, AE team, or BD headcount)
- [ ] Score 70+ OR competitor tech detected

**B — Good fit**
- [ ] Manager-level contact available
- [ ] B2B outreach motion confirmed
- [ ] Score 40–69 with at least one sales signal

**C — Marginal**
- [ ] Manager-level contact available
- [ ] B2B outreach plausible but unclear
- [ ] Score 20–39

**D — No fit (disqualify)**
- [ ] No manager-level contacts
- [ ] OR no B2B outreach motion
- [ ] OR score <20

*Last updated: March 2026. Update this file whenever qualification criteria change.*
