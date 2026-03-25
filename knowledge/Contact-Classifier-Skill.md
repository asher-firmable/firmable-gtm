# Contact ICP Classifier Skill

## Purpose
Classify a list of contacts as Firmable ICP matches (Yes/No) based on their job title, company, and any available context. Output includes a reason for each decision.

---

## Inputs
A contact list in any of these formats:
- **CSV or Excel file** — provide the file path
- **Inline list** — paste directly into the prompt
- **Webhook/JSON payload** — pass the contacts array

Minimum required field per contact: `title`
Optional fields (improve accuracy): `first_name`, `last_name`, `company`, `summary`

---

## Steps

1. **Load knowledge context**
   - Read `knowledge/icp-definition.md` — scoring dimensions, ICP tiers, and B2B outreach intent principle
   - Read `knowledge/persona-definitions.md` — the 4 buyer personas and their titles

2. **Apply two conditions — both must be true for ICP Yes**

   **Condition 1 — Seniority / buying power (manager or above):**

   ICP YES (manager, leader, or decision-maker with buying power or strong purchasing influence):
   - SDR Manager, BDR Manager, Head of Sales Development, Sales Development Manager
   - RevOps Manager, Revenue Operations Manager, Marketing Operations Manager, Demand Generation Manager
   - VP Sales, Head of Sales, Sales Director, Country Manager, GM Sales, General Manager
   - Partner, C-suite, MD, Managing Director
   - Founder / Co-Founder / CEO / MD at a company with a B2B outreach motion
   - Ops/enablement roles at manager level that influence tool/tech decisions (e.g. Business Operations Manager)
   - `[Geography/Country/Region] Lead`, `Market Lead`, `Country Lead` — geographic market ownership with BD/expansion mandate (treat as regional director equivalent)

   **"Business Development Manager" ambiguity rule (applies to: Business Development Manager, Senior BDM, Business Development Executive):**
   In ANZ, "Business Development Manager" is frequently an individual contributor (senior AE equivalent), not a people manager. To qualify as ICP Yes, the headline or summary must contain an explicit signal of team leadership — e.g., "leading a team", "managing a team of X", "player-coach", "managing SDRs/BDRs", "sales leader managing". If no such signal is present, classify as No.
   - "Head of Business Development", "BD Director", "VP Business Development" → Yes without needing headline evidence (these are unambiguously senior)
   - "Business Development Manager" / "Senior BDM" / "Business Development Executive" → requires team leadership evidence in headline → otherwise No

   **Multiple-roles rule (applies to: Co-Founder, Founder, Owner):**
   People sometimes hold more than one active professional role. When the title is Co-Founder, Founder, or Owner, check the headline/summary for a secondary current role at a different company or context (e.g., a headline reading "Business Development Lead | ..."). If the headline reveals a current role that carries B2B buying authority and is manager-level or above, use that secondary role as the primary seniority signal. If the co-founder/founder role itself is at a non-B2B company but the secondary headline role qualifies, the contact may still be ICP Yes.

   ICP NO (individual contributors — excluded regardless of company or industry):
   - Account Executive, Senior AE, Mid-Market AE, Enterprise AE
   - Sales Development Representative, BDR, SDR (without "Manager")
   - Recruitment Consultant, Senior/Principal Consultant (IC billing roles without team management)
   - Sales Representative, Sales Rep
   - Account Manager, Customer Success Manager (individual book of business)
   - Brand Ambassador, Sales Ambassador
   - Specialist, Coordinator, Associate, Analyst

   > **Title-prefix note:** Seniority-sounding prefixes ("Director", "Senior") do not automatically qualify. Check whether the underlying role is a team leader or an individual contributor. Example: "Director, Enterprise Account Executive" = IC AE → No.

   **Condition 2 — Company has a B2B outreach motion (interpret loosely):**
   - Sells products/services to other businesses
   - Sells sponsorships or event packages to businesses
   - Raises corporate donations or partnerships (charities/non-profits)
   - Recruits for corporate clients (recruitment firms)
   - Any company that proactively contacts businesses as customers, sponsors, or donors
   - Do NOT use company size as a filter — sales team size comes from the Firmable API and is used for scoring, not qualification

   **Default when uncertain:** If the title is manager/above AND B2B outreach is plausible (even if not immediately obvious), return Yes. Only return No when you are confident the person is an IC or the company has no B2B dimension at all.

   **Grey area — use company website as tiebreaker:**
   - Founder at an unknown/obscure company → check website: does it sell to, sponsor, or fundraise from businesses?
   - Charity / non-profit → check website: do they pursue corporate donors or sponsors?
   - Events company → check website: do they sell sponsorship or exhibition packages to businesses?

3. **Website check (for uncertain cases)**
   - If the company type is ambiguous from name/headline alone, fetch the company homepage
   - Scan for: "sponsors", "corporate partners", "exhibitors", "B2B", "enterprise", "clients", pricing pages
   - If clear B2B outreach intent is found → ICP Yes; if clearly B2C/consumer only → ICP No

4. **Write the output**
   Add columns/fields to each contact:
   - `ICP_Match`: `Yes` or `No`
   - `ICP_Reason`: one sentence explaining the decision
   - `Confidence`: `high` or `low` (low = website fetch was needed or data was insufficient)

5. **Return in the same format as input**
   - CSV in → CSV out (same file or new file with `_classified` suffix)
   - Inline list in → table or list out
   - JSON in → JSON out

---

## Example Output

| First | Last | Title | Company | ICP_Match | ICP_Reason |
|---|---|---|---|---|---|
| James | Wu | SDR Manager | SaaSCo | Yes | SDR Manager is a primary Firmable buyer persona responsible for outbound pipeline. |
| Sarah | Chen | Software Engineer | FinTech | No | Engineer roles have no sales mandate and are not Firmable buyers. |
| Mike | Lee | Head of Sales | Consulting Co | Yes | Head of Sales is a senior buyer persona focused on pipeline outcomes. |

---

## Notes
- **Title is the primary signal.** Company and summary are supporting context only.
- **When in doubt, lean Yes** — if the title is manager/above and the company has any plausible B2B dimension, classify as Yes. Don't over-filter at this stage.
- **BDM titles need evidence** — "Business Development Manager" and similar are IC by default in ANZ. Headline must confirm team leadership.
- **Check headlines for secondary roles** — Co-Founder/Owner at a non-B2B company may have a current BD/leadership role visible in their headline; use that as the seniority basis.
- For programmatic use, import `classify_contacts` from `scripts/classifier.py`.
- `scripts/classifier.py` reads this file at runtime via `_build_system_prompt()` — update this file to change classifier behaviour.
