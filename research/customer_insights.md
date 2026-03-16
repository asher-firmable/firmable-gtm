# Customer Insights

Synthesised from real customer and prospect calls. Updated each time a new transcript is added.

**For each entry, track:** company size (SMB / mid-market / enterprise), industry, use case, and what they were using before. Different sizes have different needs and respond to different messages.

---

## Call: Cotiss — April 17
**Contact:** Madeleine Cooper (GTM/Ops, ~7 months in role)
**Company:** Cotiss — procurement software startup, Auckland NZ. Series B, expanding into AU/NZ market.
**Company size:** 11–50 employees (SMB)
**Context:** Discovery/demo call. Madeleine owns all prospecting and enrichment. SDRs are phone-only.

### Published results (case study)
- Contact accuracy: ~30% (US provider) → **85–90%** with Firmable
- Call connects: **more than doubled within weeks**
- Onboarding: new reps productive within **30 minutes**
- Key quote: *"Our US-based data provider was only giving us a ~30% success rate, which was very low, especially when we were building out a dedicated ANZ team."*

### Why they were looking at Firmable
- Struggling with AU/NZ data quality across all global tools (Apollo, Lusha, etc.)
- Current cost to fully enrich one Australian contact: **~$1.50** — because poor coverage forces 5+ waterfall steps
- Global tools have thin AU/NZ contact data: mobile numbers rarely return, emails bounce
- "Every other database hasn't focused on Australia at all"
- "We've been struggling so much for A&Z data" (AU/NZ)
- "Stabbing in the dark" — can't optimise the waterfall because coverage varies so much by industry/list

### The moment that landed
- "You've just completely opened up my world with the fact that it's one credit for all of the information"
- One Firmable credit (~33 cents) = first name, last name, LinkedIn URL, mobile, email, company data — all in one hit
- vs ~$1.50 and multiple steps with current setup

### What they value most
1. **Local mobile numbers** — their enrichment relies heavily on LinkedIn URL as anchor; mobile is the hardest thing to find
2. **One credit = full profile** — removes the need for a long waterfall just to get one usable contact
3. **Local registry data** — government orgs, aged care providers, state/federal/local classifications. This was a standout feature.
4. **API key integration with Clay** — they use their own API keys for all tools (OpenAI, Anthropic, Apollo) so spend goes directly to the provider, not to Clay credits. Wanted same for Firmable.
5. **Suppression/exclusion** — ability to upload existing contacts and exclude them from searches

### Their workflow (for reference when building Clay/HubSpot integrations)
- LinkedIn Sales Nav → Linro scrape → CSV → Clay → deduplicate → enrichment waterfall → HubSpot
- Use own API keys (not Clay-managed) for OpenAI, Anthropic, Apollo — so credits and spend stay visible per tool
- Scoring done in Clay using Anthropic/Claude (chosen for reasoning performance over GPT)
- "Clay is Excel on steroids that unlocks the ability to integrate with any tool"

### Buying signals they care about
- **Job changes** — new procurement leaders spend majority of budget in first 90 days of role
- News/press is "almost too late" — want to catch prospects before they announce anything
- Event sponsorship as a warm trigger ("by the way, we're sponsoring this event — let's catch up there")

### Friction / objections
- Clay API vs own API key: Firmable charged 30 Clay credits for a person enrichment step (vs 1-3 credits for US tools) — this looked expensive before understanding it's all-in-one
- "Data exchange" label in Firmable UI confused her — expected "import" or "upload" (flagged as product feedback)
- HubSpot source attribution shows as "HubSpot API" not tool name — unclear which tool pushed the record

### ICP they prospect into (useful for building scoring logic)
- Procurement teams of <15 people
- Industries: utilities, renewable energy, consulting, aged care, government (local, state, federal)
- NOT: manufacturing (too tangible, doesn't fit)
- Seniority: CPO, procurement manager, head of, director, VP — not junior
- Strong LinkedIn presence: procurement community is active on LinkedIn, makes LinkedIn URL the most reliable enrichment anchor

### Exact phrases to use in copy
- "Every other tool wasn't built for this market"
- "You're stabbing in the dark" (when describing APAC enrichment with global tools)
- "One credit for everything" (Firmable's key differentiator in the cost conversation)
- "First 90 days" (buying window for new procurement hires)

---

## Calls: Stripe — October 01 & November 19
**Contacts:** Jayne (marketing lead), Ian (data/marketing ops), Sarah, Amy, Trina
**Company:** Stripe — B2B company targeting retail, insurance, travel, and tech verticals across ANZ/APAC (likely payments or SaaS)
**Company size:** Unknown — mid-market indicators (dedicated marketing ops, separate AEs, Salesforce + Marketo stack)
**Context:** Two calls. First is initial demo + must-win list evaluation. Second is follow-up data quality review ~6 weeks later.

### Why they were looking at Firmable
- Marketing had no direct data sourcing tool — data flowed in indirectly via salespeople scraping ZoomInfo
- Marketing wanted to own prospecting rather than wait for sales to bring contacts in
- Evaluating Firmable specifically for marketing-initiated list building against defined must-win accounts

### Match rates from must-win list evaluation (Call 1)
- Platforms vertical: 282/312 companies matched (90%)
- Retail: 77/82 (94%)
- Insurance: 44/44 (100%)
- Travel: ~82/101 (81%)
- People coverage once matched: very high (e.g. 44,000 people across 44 insurance companies)

### Data quality concerns raised (Call 2)
- **Specsavers anomaly:** 158 "Retail Director" contacts — initially suspected stale data
  - Resolution: valid — Specsavers uses "Retail Director" as a standardised title across franchise store managers
  - Fix: exclude "retail" keyword in job title filter; use department + seniority filters instead
- **Mobile number freshness:** concerned about company phones being passed to new employees
  - Firmable: refreshes every 30 days (working toward weekly); data only 15 months old
  - Live DNC register scrub adds a real-time validity signal
  - Coverage example: 14/15 mobile numbers for Specsavers contacts — noted as impressive

### What they value most
1. **Email coverage** — primary requirement for marketing; mobile is secondary
2. **Match rate against named account lists** — came in with specific must-win lists; coverage was the key test
3. **Suppression lists** — upload existing contacts to avoid re-targeting customers or unsubscribes
4. **Buying signals** — leadership changes, new hires in target roles; interested in ongoing signal alerts
5. **APAC expansion** — Ian manages APJ/APAC; flagged interest in broader APAC data when available

### Stack and workflow
- CRM: Salesforce (company-wide)
- Marketing automation: Marketo (larger contact database than Salesforce — some contacts not synced across)
- ZoomInfo data flows in via sales scraping — not a direct marketing tool
- Salesforce native integration requires months of security/compliance review
- Short-term plan: CSV exports, Zapier, or API keys until formal integration is approved

### Friction / objections
- Salesforce integration timeline — IT/security process = months before native integration is live
- Specsavers data initially looked inaccurate — resolved once franchise title logic explained
- Concerned about mobile number staleness (company phones recycled after staff leave)
- 252 retail contacts felt too small for a meaningful overlap test — wanted larger sample

### Privacy / compliance note
- Firmable advised: sales should take no more than 20–30 contacts at a time (Australian privacy law)
- Marketing can take bulk; sales should not auto-dial large lists
- DNC compliance is live API pull — not a static list

### Exact phrases / language used
- "We don't want to wait for things to happen — we want to be directly involved in acquiring"
- "We just wanted to understand if it was accurate" (data quality questions — thorough, not hostile)
- "Once we do a crossover match, it might be 100 and that's not compelling enough" (Ian — needs larger samples for evaluation)

---
