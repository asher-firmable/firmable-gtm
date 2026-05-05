# ANZ SMB Closed-Won Analysis: Why They Chose Firmable
**Period:** Jan 2026 – May 2026 (300 deals processed out of 399 total)  
**Matched to Fathom recordings:** ~102 companies (~34% match rate)  
**ANZ-headquartered:** ~96 companies | **Non-ANZ HQ (global MNC):** 6 companies — see Section 2.5  
**Data source:** Fathom call summaries via `find_person` — no full transcript review unless otherwise noted

---

## 1. Executive Summary

- **The single biggest reason customers buy Firmable is ANZ data that global tools can't match.** Apollo, ZoomInfo, and Lusha are named in ~25% of matched calls. The common thread: these tools treat Australia and New Zealand as an afterthought, either scraping LinkedIn (producing lists customers already have) or applying US-enterprise data models that don't fit the ANZ SMB market.

- **The second-largest buyer cohort isn't switching tools — they're building their first outbound motion.** ~15–18 companies had no prior prospecting tool at all. Firmable is their entry point into outbound, not a replacement.

- **Recruitment is the dominant vertical**, accounting for ~11 of the ~102 matched companies. The JobAdder integration is a consistent decision factor for this group and should be treated as a first-class acquisition lever.

- **Discovery is almost impossible to measure from this dataset** — ~90% of Fathom summaries don't record how the prospect found Firmable. Of the ~12 where we know, 7 were outbound (Firmable SDR) and 5 were referrals. Zero confirmed organic/inbound in this sample.

- **Direct mobile numbers are a primary value prop for a specific buyer type** — field sales, cold callers, and executive search teams who are blocked by gatekeepers and LinkedIn lag. This is a distinct use case from the "data quality vs. Apollo" buyer and should be messaged separately.

- **~94% of matched companies are ANZ-native businesses.** 6 of 102 are subsidiaries of non-ANZ multinationals (Hitachi, SoftBank, BRITA, Nilfisk, INFUSE, Enboarder). All core findings below apply to the ANZ-native cohort unless otherwise noted.

---

## 2. Methodology & Scope

- HubSpot filter: `dealstage=closedwon`, `icp_match__new_=true`, `market IN [AU, NZ, ANZ]`, `dealname CONTAINS "New Deal"`, `closedate >= 2026-01-01`
- 300 deals processed (Jan 2026 – May 2026); Nov/Dec 2025 skipped
- For each deal: retrieved associated HubSpot contact → ran `find_person` in Fathom → extracted signal from meeting summary
- **Match rate:** ~102 of 300 (~34%) had an accessible Fathom recording
- **No-recording cases** are primarily self-serve trials with no booked call
- All signals extracted from AI summaries; full transcripts pulled for pilot companies only (5)

---

## 2.5 HQ Location Breakdown

HubSpot deal records all carry AU or NZ country codes (subsidiary/office location). The split below reflects actual global headquarters, determined by company name recognition and Firmable lookup for borderline cases.

| HQ Location | Count | % of matched companies |
|---|---|---|
| ANZ (AU or NZ native) | ~96 | ~94% |
| Non-ANZ (global MNC with ANZ office) | 6 | ~6% |

**Non-ANZ HQ companies (†):**

| Company | Global Parent / HQ | Notes |
|---|---|---|
| Hitachi Vantara | Hitachi Ltd (Japan) | ANZ subsidiary of Japanese conglomerate |
| SoftBank Robotics | SoftBank Group (Japan) | ANZ office for commercial robotics rollout |
| BRITA Water | BRITA GmbH (Germany) | ANZ subsidiary of German water filtration group |
| Nilfisk | Nilfisk A/S (Denmark) | ANZ subsidiary of Danish industrial cleaning company |
| INFUSE | INFUSE LLC (USA) | US B2B demand gen company with ANZ operations |
| Enboarder | Enboarder Inc. (Austin, TX) | AU-founded but relocated HQ to USA ~2022 |

**Why this matters for ICP targeting:** The 6 non-ANZ HQ companies operate under different buying dynamics. Their tool procurement is often influenced by global IT mandates or regional autonomy policies — not purely a data quality decision. The ANZ-native cohort (~96 companies) is the core ICP target where Firmable's positioning as an ANZ-native platform drives the sale.

---

## 3. Discovery Channel Breakdown

**Caveat:** Discovery channel was captured in ~12% of matched calls. The other ~90% of Fathom summaries don't record how the prospect found Firmable. Treat these numbers as a directional floor, not a full picture.

| Channel | Count (confirmed) | Notes |
|---|---|---|
| Outbound (Firmable SDR) | 7 | Ignatius, Ashton, Oscar, Tom, James, Darcy named |
| Referral | 5 | Joe, Steph, Lonnie, LeadList, Ex Recruiter |
| Inbound / organic | 0 | Not confirmed in any summary |
| Unknown | ~90 | Not recorded in Fathom summary |

**Named SDR closures:** Blackbird IT (Ignatius), CUB Club (Ashton), Employers Comp (Oscar), VRC St Leger (Oscar), Workfacta (Oscar), Yindili (Tom + James), Cyberlinx (Darcy).

---

## 4. Pain Points & Triggers

Grouped by theme, with frequency count across matched companies.

### 4.1 Global tool doesn't work for ANZ (~20 companies)

The most cited pain. Apollo and ZoomInfo are named most often — but the underlying issue is consistent: tools built for US enterprise produce thin, inaccurate, or already-familiar data for the ANZ market.

> **Note on non-ANZ HQ companies in this group:** Hitachi Vantara†, BRITA Water†, Nilfisk†, and Enboarder† all appear in this cohort. For these subsidiaries, the "global tool doesn't work" pain is real — but the buying dynamic is different. Their ANZ team may be evaluating Firmable independently because their global tool mandate (ZoomInfo, etc.) doesn't deliver for the local market. This is a distinct use case: **global tool mandate + local data gap**, rather than an SMB choosing Firmable as their primary tool.

**Apollo failures:**
- CUB Club: *"I imagine what they did for ANZ, because it's sort of an afterthought market, they would have just scraped LinkedIn and that would have been their Australian data set."* — Apollo data overlapped completely with their existing 30k LinkedIn network.
- MYMAX: Apollo returned only 43 valid leads out of 800 (5% hit rate) for an AU campaign.
- Asset Vision: Apollo export was 3 years old — high bounce rates damaged their HubSpot sender reputation.
- WorkingMouse: Apollo had a 75% coverage gap compared to Firmable's AU database.
- Roger Roger Marketing: Apollo NZ database = 765k records vs Firmable's 1.26M.
- Hoselink: Expanding from D2C into B2B — Apollo couldn't support ANZ B2B targeting.
- Broad Reform, Hitachi Vantara: Replaced Apollo for ANZ lead gen.

**ZoomInfo failures:**
- Blackbird IT: *"ZoomInfo seems to have a focus on the US and not massively usable for the Australian market... they're targeted more towards your 500, 1,000 seat plus."*
- Effective Freight Solutions: ZoomInfo expensive, clunky, ~80% ANZ accuracy — needed Lucia to supplement.
- Enboarder: Firmable data quality superior; ZoomInfo import also blocked by internal policy.
- BRITA Water: Launching new ANZ outbound function — ZoomInfo lacks deep local data.
- Konnexus, YellowfinBI: ZoomInfo comparison → Firmable won on ANZ coverage.

**Other tools:**
- BCI, INFUSE, Vision Property: Lusha/Cognism poor ANZ data quality.
- Yindili: Lucia 35% email bounce rate (70 of 200 emails bounced) — wasting credits.
- Service Quality: Lusher missing numbers, stale contacts — blocked cold-call-heavy outbound.
- HIVE Creative: RocketReach + LinkedIn Sales Nav — poor data quality + no contact info.
- Simplifi: Scrap + Hunter poor AU/NZ quality, forced manual verification, blocked phone-first strategy.

---

### 4.2 First-ever outbound motion (~15–18 companies)

A large cohort had no prior tool — Firmable is their first entry into structured outbound. Triggers include: new hire (sales/BDM role), strategic shift from inbound-only, business acquisition, or new product launch.

Representative examples:
- **Workfacta:** 4–5 years of organic growth, now launching first SDR motion targeting AU wineries.
- **Kreate Australia:** Shifting from reactive project work to proactive outbound targeting larger corporate clients (60/40 ongoing/project).
- **Governance Institute of Australia:** B2C training org building their first B2B outbound motion — new AE hired specifically for this.
- **DyCom Group:** 30-year IT company pivoting from "farmer" (large clients) to "hunter" model.
- **Sutton IT:** SEO too difficult → outbound as alternative.
- **TitanWater:** Business acquired 7 months prior — previous owner had no outbound, Conrad rebuilding.
- **MedRisk:** Launching new digital pre-employment medical service; needed automated outbound.
- **dsdassist:** Launching 2026 direct-to-customer sales motion; building 4× pipeline.
- **Perth Support:** Technical services firm, historically word-of-mouth; no prior lead sourcing.
- **InLogic, ValAuth, Fractional Growth Engine, Folio.Insure, Pelorus Capital:** All first-time outbound or new product launch scenarios.

---

### 4.3 Need direct mobile/email — gatekeepers and LinkedIn lag (~10 companies)

A distinct buyer type: field sales, cold callers, and executive search firms who need direct numbers, not LinkedIn profiles.

- **TOT Transport:** Limited to slow LinkedIn messages — no direct mobile/email for prospects.
- **HUBB SYDNEY:** Recruiting ASX small-cap directors — static list failed, needed 04 mobile numbers to bypass gatekeepers.
- **Blue Bike Solutions:** Signal Hire fails to provide mobile numbers → stuck at gatekeepers.
- **A.I.R Recruitment:** Replaced LinkedIn Recruiter Lite — white-glove messaging avoidable with direct contact info.
- **BCI:** Lusha poor ANZ mobile/email coverage.
- **Raizor Insurance:** Manual process for finding contacts in shell companies.
- **Chris Kelly/Fleetwood:** National modular housing BDM — bypass gatekeepers with direct contact.
- **JLSG:** Manual LinkedIn → Firmable's 10.3M+ AU contact database.
- **Zank & Co.:** Wealth management seeking direct mobiles + emails for mortgage broker outreach.
- **OMPL:** Needed direct contact info for credit managers list.

---

### 4.4 Vertical or niche coverage gap (~12 companies)

Companies that need contacts in a specific industry that generic tools don't cover adequately.

- ACM Healthcare: Apollo has no AU healthcare vertical (radiologists, nurses).
- KBI Group: Needed 678 Practice Manager contacts — found in Firmable demo.
- Nilfisk: Urgent campaign — flour mills / food production ANZ contacts.
- Handle: Needed Shopify-install technographic filter to isolate ideal e-commerce customers.
- Koatas: AU construction firms, 11–250 employees.
- ONTRAC Group: Pivoting from quarrying to mining — new sector contact data.
- FormsExpress: Local councils and utilities targeting.
- Karabiner: Tier 2/3 builder specifiers for construction products.
- SoftBank Robotics: Facilities Managers / Ops / COO for commercial cleaning robots.
- GraceWell Group: Allied health professionals (hard-to-fill recruitment).
- Folio.Insure: General insurance brokers for SaaS platform.
- DataSentinel: People who previously used DataSentinel-like products at prior companies.

---

### 4.5 Scale / automate a manual or fragmented process (~7 companies)

- **Interite:** 3 data tools + sales assistant building lists in Excel, manual entry into Salesforce → one platform.
- **Working Capital Partners:** Needed to enrich a 13,000-company list.
- **Lumi:** Enriching 10k brokers + 6k brokerages.
- **The People Plugin:** AU e-commerce decision-maker data for recruitment BD.
- **JLSG:** Manual LinkedIn prospecting → automated list-building.
- **Tri-Star Logistics:** Too much workload (prospecting + quoting + account management) — needed automation.
- **DataSentinel:** Building targeted lists of people who used competitor products at prior companies.

---

### 4.6 Price / model mismatch with incumbent (~3 companies)

- **AuditCo:** 50% savings switching to annual plan ($960/yr vs monthly equivalent).
- **The Evolved Group:** Legacy list provider raised prices → triggered competitive review.
- **Business Benchmark Group:** Spirian static list — evaluating for efficiency, cost, data quality.

---

## 5. Competitive Displacement

Tools named in Fathom recordings, ranked by frequency.

| Tool | Times Named | Primary Failure Mode |
|---|---|---|
| Apollo | 8–9 | AU/NZ data scraped from LinkedIn; no net-new contacts; low hit rates |
| ZoomInfo | 6 | US-enterprise focus; wrong data model for AU SMB; expensive |
| Lusha | 3–4 | Poor ANZ data quality; missing mobiles |
| Static list brokers | 3–4 | Expensive, not self-serve, one-time snapshots |
| Manual / LinkedIn | 4 | LinkedIn Recruiter (no direct contact), manual Excel workflows |
| Lucia / Lusher | 3 | High bounce rates, stale/missing AU contacts |
| Signal Hire | 1 | No mobile number coverage |
| RocketReach | 1 | Poor data quality |
| LinkedIn Sales Nav | 1 | No contact info (profiles only) |
| Scrap + Hunter | 1 | Poor AU/NZ quality |
| Spirian | 1 | Static, not self-serve |
| Prospector | 1 | Limited partner/contact data |
| Cognism | 1 | ANZ data quality (alongside Lusha) |

**No prior tool (first outbound motion):** ~15–18 companies — larger than any single tool displacement cohort.

---

## 6. Decision Factors

What specifically tipped the deal, extracted from call summaries.

| Factor | Frequency | Notes |
|---|---|---|
| ANZ-native data accuracy / depth | ~40+ | Implicit in almost every deal; explicit comparison in ~40 |
| Direct mobile + email contact data | ~10 | Named explicitly by field sales / cold calling buyers |
| HubSpot native integration | ~8 | One-click push; key for teams already on HubSpot |
| Signals feature | ~8 | New-in-role, AI signals, hiring activity — mainly recruitment + SDR teams |
| JobAdder integration | 4 | Decisive for recruitment firms using JobAdder as ATS |
| Price vs. incumbent | 4 | Annual plan savings; vs. static list broker cost |
| Technographics | 3 | Shopify installs (Handle), fintech stack (Blinkpay), product users (qbox) |
| NZ data depth | 3 | 1.26M NZ records vs Apollo's 765k; Simplifi NZ healthcare |
| Pipedrive integration | 1 | Zank & Co., M&S Transport |
| Australian founders / credibility | 1 | Blackbird IT explicitly — "built by Aconex, Message Media people" |

---

## 7. Buyer Profiles / ICP Patterns

### 7.1 By vertical

| Vertical | Count | Key signals |
|---|---|---|
| Recruitment | ~11 | JobAdder integration, Signals for hiring activity, ANZ talent database |
| SaaS / software | ~8 | New outbound motion, tool replacement (ZoomInfo/Apollo), HubSpot integration |
| Finance / fintech / brokers | ~8 | Direct contact data, niche verticals (insurance, FX, lending) |
| IT / MSPs | ~7 | Tool replacement or first outbound; SMB/mid-market targeting |
| Professional services | ~7 | BD efficiency, partner outreach, project-based work transitioning to retainer |
| Construction / trade | ~6 | Niche targeting (Tier 2/3 specifiers, mining, young companies) |
| Marketing agencies / BDaaS | ~5 | List-building for clients; AU B2B data for campaigns |
| Logistics / transport | ~4 | Direct mobiles for field sales; niche vertical contacts |
| Healthcare | ~4–5 | Niche vertical coverage; JobAdder for health recruitment |

### 7.2 By outbound maturity at time of purchase

| Stage | Count | Description |
|---|---|---|
| Building first outbound motion | ~15–18 | No prior tool; Firmable is their entry point |
| Replacing a failing tool | ~20 | Apollo or ZoomInfo not working for ANZ |
| Adding / scaling existing outbound | ~10 | Had something working; needed more volume or accuracy |
| Re-engaging after bad trial | ~3 | Cyder Solutions, Symetrix, 1Breadcrumb |

### 7.3 By company size / stage

Most deals involve companies with small sales teams (1–5 people doing outreach). Several are:
- Solo operators or micro businesses (1–2 person sales function)
- Founder-led businesses launching outbound for the first time
- Established companies (10–50yr old) launching their first structured BD function
- Early-stage startups (CirculaTech at 5 weeks old; Nodal Talent at 3 weeks old)

---

## 8. Notable Quotes

All sourced from Fathom transcript summaries (pilot companies have full transcripts).

> *"We did look at ZoomInfo but that seems to have a focus on the US and not massively usable for the Australian market... they're targeted more towards your 500, 1,000 seat plus."*  
> — Chris Wagner, Blackbird IT (CGO)

> *"We found most people were people that we've already spoken to through LinkedIn... I imagine what they did for ANZ, because it's sort of an afterthought market, they would have just scraped LinkedIn and that would have been their Australian data set."*  
> — Anthony Mullane, CUB Club (Co-founder / Head of Growth)

> *"Our legacy provider came in with prices quite a bit more than they used to. So we're broadening our view."*  
> *"A lot of this today has been different from who we've spoken to, and in a good way. So I'm enthused."*  
> — Ben Griffiths, The Evolved Group

> Apollo returned only 43 valid leads out of 800 for an AU campaign — ~5% hit rate.  
> — Tanya Stainton, MYMAX

> Apollo's NZ database: 765k records. Firmable's: 1.26M.  
> — Cory Gordon, Roger Roger Marketing

> Lucia email tool: 35% bounce rate (70 of 200 emails bounced) — wasting credits and time.  
> — Daniel Johnson, Yindili

> Apollo export was 3 years old — high bounce rates had damaged their HubSpot sender reputation.  
> — Gareth Thomas, Asset Vision

> Scrap + Hunter: poor AU/NZ data quality forced manual verification and blocked their phone-first strategy.  
> — Jeremiah Chow, Simplifi

---

## 9. Implications for Positioning & Messaging

### What's landing

1. **"ANZ-native" is the core claim** — it's not just a feature, it's the reason they're in the room. Lead with it.
2. **The Apollo comparison is ready-made** — customers bring it up unprompted. Apollo's ANZ data = scraped LinkedIn = no net-new contacts. This is a clean, provable displacement angle.
3. **The "first outbound motion" buyer is under-served by current messaging** — they're not comparing tools, they're deciding whether to invest in outbound at all. Firmable's message needs a version that speaks to this context.
4. **JobAdder integration is a recruitment-vertical acquisition moat** — 4 named deals where it was decisive. Worth a standalone recruitment landing page / sequence.
5. **Direct mobile numbers are the primary value for cold callers and field sales** — this is a distinct persona from the "data quality" buyer and responds to different copy.

### Gaps / questions to investigate

- Discovery channel is unknown for ~90% of deals — better tagging in Fathom notes or HubSpot deal source field needed.
- "How did you hear about us?" should be a standard call-opening question and captured in Fathom structured summary.
- The self-serve / no-recording cohort (~66% of deals) is invisible — understanding their path to purchase requires a different method (in-product survey, post-signup email).

---

## Appendix: Companies Matched

102 companies with confirmed Fathom recordings across Jan–May 2026 deals. Full detail in memory file `project_anz_smb_analysis_bulk_findings.md`.

† = Non-ANZ global headquarters (see Section 2.5)

**Pilot (5):** Blackbird IT, CUB Club, ACM Healthcare, IT Live, The Evolved Group

**Bulk run sample (selected):** CirculaTech, Working Capital Partners, The People Plugin, Nilfisk†, AuditCo, Asset Vision, Employers Comp, Tri-Star Logistics, VRC St Leger, BCI, Roger Roger Marketing, SoftBank Robotics†, HIVE Creative, Effective Freight Solutions, Workfacta, Enboarder†, Chain Reaction, 1Breadcrumb, Koatas, ONTRAC Group, Handle, TOT Transport, Raizor Insurance, Yindili, Vectura Recruitment, Business Benchmark Group, Service Quality, HUBB SYDNEY, Yorkshire Bridge, Blue Bike Solutions, MedRisk, Scoutr, WorkingMouse, Dfnce, YellowfinBI, BRITA Water†, Tasman FX, OMPL, Lumi, Insights Exchange, Nodal Talent, Bentleys, MYMAX, KBI Group, JLSG, Cyder Solutions, Pelorus Capital, Spier Services, Sutton IT Management, A.I.R Recruitment, InLogic, Impactlab, Broad Reform, DataSentinel, Blinkpay, Kreate Australia, KPA Search Partners, Symetrix, EndVision, TGA Cables, Simplifi, TitanWater, RubyOnyx, INFUSE†, Hitachi Vantara†, Interite, Cyberlinx, Konnexus, Veitch Lister Consulting, Elias Recruitment, Jobwire, DyCom Group, Sunshine Finance Brokers, Governance Institute of Australia, Custom365, Profcoll, Charles Elena, Hoselink, dsdassist, Zank & Co., Vision Property, Valiant, Intermodal Terminal, Fractional Growth Engine, GraceWell Group, Folio.Insure, Infrastructure Sustainability Council, Perth Support, qbox

---

*Generated from Fathom call recordings via Claude Code | May 2026*
