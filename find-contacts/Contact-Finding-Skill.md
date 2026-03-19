# Skill: Find Contacts Using Firmable

## What This Skill Does
Given a list of companies (with domains, LinkedIn URLs, or Firmable IDs), finds sales-relevant contacts using the Firmable People Search API.

---

## Logical Steps

1. **Resolve Firmable Company ID** — for each company, get its Firmable ID via:
   - `client.search_by_linkedin(linkedin_url)` — preferred
   - `client.lookup_company(domain)` — fallback

2. **Search for contacts** — use `client.find_contacts()` with filters:
   - `department=2` (Sales) for most outreach use cases
   - `seniority=4` (VP/Director) for senior buyer targeting
   - `country="AU"` to restrict to Australian contacts
   - Adjust filters based on the target persona (see `knowledge/persona-messaging.md`)

3. **Enrich contact details** — use `client.get_person(ln_url=...)` to get full profile (email, mobile, position)

4. **Apply exclusions** — check `knowledge/exclusions.md`:
   - Skip if `on_dnc_register` = Yes
   - Skip existing customers and unsubscribes

5. **Output to CSV** — write to `find-contacts/output/[name]_contacts.csv`

---

## Code Pattern
```python
from applications.firmable import FirmableClient
import csv

client = FirmableClient()

companies = [
    {"domain": "example.com.au", "linkedin_url": "https://www.linkedin.com/company/example"}
]

contacts = []
for co in companies:
    # Step 1: resolve company
    company = client.search_by_linkedin(co["linkedin_url"]) if co.get("linkedin_url") \
              else client.lookup_company(co["domain"])
    if not company:
        continue

    firmable_id = company["id"]

    # Step 2: find contacts
    results = client.find_contacts(
        company_id=firmable_id,
        department=2,   # Sales
        seniority=4,    # VP/Director
        country="AU"
    )

    for r in results:
        # Step 3: enrich (optional, costs a credit)
        person = client.get_person(id=r["person_id"])
        contacts.append(person)

# Step 4: apply exclusions
contacts = [c for c in contacts if not c.get("on_dnc_register")]
```

---

## Seniority & Department Codes
See `knowledge/firmable-api-reference.md` for the full list.

Key codes:
- Seniority: 1=Board, 2=Owner/Founder, 3=C-Suite, 4=VP/Director, 5=Manager
- Department: 1=General Mgmt, 2=Sales, 11=Marketing, 13=Consulting, 14=Finance

---

## Key Files
- Wrapper: `applications/firmable.py`
- API reference: `knowledge/firmable-api-reference.md`
- Exclusion rules: `knowledge/exclusions.md`
- Persona targets: `knowledge/persona-messaging.md`
