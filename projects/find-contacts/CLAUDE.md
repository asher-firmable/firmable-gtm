# Find Contacts — Sub-Agent

## Role
I handle ad-hoc and batch contact lookups using the Firmable API. Given a company name, domain, LinkedIn URL, or Firmable company ID, I find the right sales contacts and return structured results.

---

## What Lives Here
- `bot.py` — Interactive CLI and Slack bot for real-time contact lookups
- `output/` — Results from contact searches (gitignored)

---

## How to Use

### Interactive CLI
```bash
PYTHONPATH=. python3 projects/find-contacts/scripts/bot.py
```

### Batch lookup from a CSV
If given a list of companies, use the Firmable People Search to find contacts at each:
```python
from scripts.firmable_api import FirmableClient

client = FirmableClient()

# Find contacts at a company by Firmable ID
contacts = client.find_contacts(
    company_id="f000000117274",
    department=2,   # Sales (see knowledge/firmable-api-reference.md for codes)
    seniority=4,    # VP/Director
    country="AU"
)

# Enrich a person by email
person = client.get_person(work_email="name@company.com")

# Look up company first (to get Firmable ID), then find contacts
company = client.lookup_company("example.com.au")
firmable_id = company.get("id")
contacts = client.find_contacts(company_id=firmable_id)
```

---

## Skill
See `Contact-Finding-Skill.md` for full instructions on running searches.

---

## Key References
- `scripts/firmable_api.py` — `FirmableClient` wrapper
- `knowledge/firmable-api-reference.md` — API endpoints, seniority/department codes
- `knowledge/exclusions.md` — DNC rules (apply before returning contacts for outreach)

---

## Output
Write results to `projects/find-contacts/output/` (gitignored). Naming convention:
`[search_name]_contacts.csv`
