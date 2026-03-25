---
name: firmable-api
description: Use this skill when interacting with the Firmable platform API. Triggers include searching for companies or contacts, enriching data, bulk operations, or any task requiring Firmable's data endpoints.
---

# Firmable API

## Setup
- API key in `.env` as `FIRMABLE_API_KEY`
- Main client: `scripts/firmable_api.py` → `FirmableClient`
- Always import the client class — never write raw API calls

```python
from scripts.firmable_api import FirmableClient
client = FirmableClient()
```

## Common operations

### Company lookup
```python
# By domain
company = client.lookup_company("example.com.au")

# By Firmable ID
company = client.lookup_company_by_id("f000000117274")

# By LinkedIn URL
company = client.search_by_linkedin("https://linkedin.com/company/example")
```

### Contact search
```python
# Find contacts at a company
contacts = client.find_contacts(
    company_id="f000000117274",
    department=2,   # 2 = Sales (see knowledge/firmable-api-reference.md for all codes)
    seniority=4,    # 4 = VP/Director
    country="AU"
)

# Enrich a person by email
person = client.get_person(work_email="name@company.com")
person = client.get_person(ln_url="https://linkedin.com/in/username")
```

### Sales team sizing
```python
# Requires FIRMABLE_OS_API_KEY in .env
sizes = client.get_sales_team_size(company_id="f000000117274")
# Returns: au_sales_team_size, nz_sales_team_size, sea_sales_team_size, total_sales_team_size
```

## Best practices
- Respect rate limits — add `time.sleep(0.5)` between calls in bulk loops
- Cache results where possible — avoid repeat lookups for the same company
- Handle errors gracefully — log failures with the company name, don't crash the whole run
- For bulk operations, use try/except per record and continue on error

## Integration with other skills
- `account-qualification` calls this for enrichment when data is incomplete
- `contact-validation` calls this to find contacts at qualified accounts
- `signal-research` calls this for technographic data

## Full endpoint reference
See `knowledge/firmable-api-reference.md` for all endpoints, seniority codes, and department codes.
