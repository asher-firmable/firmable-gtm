# GTM Communities Sub-Agent

## Purpose
Market map of GTM engineering communities and their closest GTM-type neighbours (sales development, RevOps, growth), with the person who runs each one. Covers the seed set, the US (plus global online communities that serve US GTM teams) and ANZ; add regions as new rows, not new files.

## What goes in
- No input file. Built from web research: WebSearch for discovery, Firecrawl (`https://api.firecrawl.dev/v1/scrape`, `FIRECRAWL_API_KEY` in `.env`) to read community sites and pull founder names and LinkedIn links
- Seed list (provided Oct 2026): GTM Cafe, Bootprint, RevTech Academy, The GTM Engineer Lab, GTM Engineer School, Unlock GTME

## What goes out
- `output/gtm_communities.csv`: one row per community with community_name, website, description, type, region, relevance_tier, list_source, contact_name, contact_title, contact_linkedin, notes
- `output/` is gitignored

## Scripts / tools
- None. Research is manual; record the source of any field that is not on the community's own site in `notes`

## Conventions
- `relevance_tier`: `Core` = GTM engineering, Clay or AI-GTM education or community; `Adjacent` = sales development, RevOps, growth or cross-functional GTM operator communities
- `list_source`: `Seed` for the provided list, `<Region> research` for anything found (`US research` includes global online communities found in the US pass)
- Exclude communities owned or run by a software vendor, including local chapters (Clay Club, HubSpot User Groups, Salesforce, n8n, Workato and similar). Vendor sponsorship is fine. Independent global communities with an active local chapter are fine
- When no person can be found, set `contact_name` to `Not found` and say where you looked in `notes`; never guess
- Out of scope unless asked: general sales (AE/closing) communities, marketing-only communities, founder and startup networks, SaaS industry bodies, one-off conferences
- Contact = founder, or whoever runs the community or local chapter. Prefer LinkedIn URLs linked from the community's own site or a sponsor post; flag anything weaker in `notes`
- GTM ANZ is powered by Firmable (with Pointer). Keep that flagged in `notes`

## US findings (Oct 2026)
- 13 rows added: 7 Core (The Go-Tos, The GTM Club, The GTM University, GTM Engineer Foundations, StackOptimise course, AI Growth Systems Bootcamp, GTM AI Academy) and 6 Adjacent (RevGenius, RevOps Co-op, Wizards of Ops, MarketingOps.com, SDR Leaders of USA, NextGen Sales Systems)
- Left out as vendor-run: Clay's Slack, cohorts and AlphaForge bootcamp, GTM Society (Expandi), Outbounders (Woodpecker), Instantly's Slack, Sales Pulse (Reply), SyncGTM's Slack and course, RevOps Chat (Weflow), Scaile's GTM Engineers Community (page now redirects)
- Left out as out of scope: Pavilion, GTM Leader Society (exec networks), Exit Five, CMO Coffee Talk and the Maven GTM bootcamp for non-technical marketers (marketing-only), PreSales Collective, Enablement Squad, Women in Revenue, AI Automation Society, Maker School and AI Automation Agency Hub (general AI automation, not GTM)
- Could not confirm: RevOps Village, Revenue Operations Alliance

## ANZ findings (Oct 2026)
- No independent GTM engineering community exists in ANZ. Clay Club Sydney and Melbourne are the only GTM-engineering-specific groups, and they are excluded as vendor-run
- Considered and left out: Generate (B2B in-house marketers only), SalesHaus / LiveHaus (general sales events), kiwiSaaS (NZ SaaS industry body), RevOps Co-op (no ANZ chapter; two Sydney happy hours in 2025), MO Pros (Sydney chapter only planned), SDRs of APAC (Singapore/Europe-led, 69 members), AI Tinkerers (general AI builders), Sales Enablement Collective (global summit series), Aussie Founders Club (founders)
