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
   - Read `knowledge/icp-criteria.md` — scoring dimensions, ICP tiers, and B2B outreach intent principle
   - Read `knowledge/persona-messaging.md` — the 4 buyer personas and their titles

2. **Apply two conditions — both must be true for ICP Yes**

   **Condition 1 — Seniority / buying power (manager or above):**

   ICP YES (manager, leader, or decision-maker with buying power or strong purchasing influence):
   - SDR Manager, BDR Manager, Head of Sales Development, Sales Development Manager
   - RevOps Manager, Revenue Operations Manager, Marketing Operations Manager, Demand Generation Manager
   - VP Sales, Head of Sales, Sales Director, Country Manager, GM Sales, General Manager
   - BD Manager (confirmed team leadership), Partner
   - Founder / Co-Founder / CEO / MD at a company with a B2B outreach motion
   - Ops/enablement roles at manager level that influence tool/tech decisions (e.g. Business Operations Manager)
   - `[Geography/Country/Region] Lead`, `Market Lead`, `Country Lead` — geographic market ownership with BD/expansion mandate (treat as regional director equivalent)

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
- For programmatic use, import `classify_contacts` from `applications/classifier.py`.
