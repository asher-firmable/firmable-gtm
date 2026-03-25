---
name: hubspot-sync
description: Use this skill when pushing data to or pulling data from HubSpot CRM. Triggers include syncing leads, creating or updating contacts/companies, pulling deal data, pushing signals, or any HubSpot interaction.
---

# HubSpot Sync

## Setup
- Access token in `.env` as `HUBSPOT_ACCESS_TOKEN`
- Client: `scripts/hubspot_client.py` → `HubSpotClient`

```python
from scripts.hubspot_client import HubSpotClient
hs = HubSpotClient()
```

## Common operations

### Contacts
```python
# Search first to avoid duplicates
existing = hs.search_contacts("email", "name@company.com")

# Create new
hs.create_contact({"email": "name@company.com", "firstname": "Jane", "lastname": "Smith"})

# Update existing
hs.update_contact(contact_id, {"phone": "+61412345678"})

# Legacy upsert (create or update by email)
hs.create_or_update_contact("name@company.com", {"phone": "..."})
```

### Companies
```python
# Search by domain
companies = hs.search_companies("example.com.au")

# Create
hs.create_company({"name": "Example Co", "domain": "example.com.au"})

# Associate contact to company
hs.associate_contact_to_company(contact_id, company_id)
```

### Static lists
```python
lst = hs.create_static_list("Campaign: ANZ Series B - March 2026")
hs.add_contacts_to_list(lst["listId"], [contact_id_1, contact_id_2])
```

## Deduplication rules
- **Always search before creating** — check contacts by email, companies by domain
- If a match exists: update the record, don't create a duplicate
- If domain search fails, try name search as fallback: `search_companies_by_name()`
- Associate contacts to companies after creating both

## Rate limits
- 100 API calls per 10 seconds
- For bulk operations, add `time.sleep(0.1)` between records or use batch endpoints

## Important safety rules
- **Always ask before bulk-updating existing records** — tell the user how many records will be affected
- Log all sync operations: which contact/company, what changed, success/failure
- Never delete records without explicit confirmation

## References
- Event scraper HubSpot sync: `projects/event-scraper/scripts/2_sync_to_hubspot.py`
