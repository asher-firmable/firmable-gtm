# Firmable API Reference

Source: https://docs.firmable.com/api-reference/overview
Last updated: 2026-11-10

---

## Overview

Firmable API provides access to Australia and NZ's B2B sales intelligence platform — 10M+ contacts at 1.5M+ companies, with buying signals and enrichment data.

---

## Base URL

```
https://api.firmable.com
```

> Note: No `/v1` version prefix. Endpoints are directly off the root.

---

## Authentication

All requests require a bearer token in the `Authorization` header:

```
Authorization: Bearer fbl_xxx
```

Retrieve your API key from:
https://app.firmable.com/dashboard/profile?selected=integrations&connection=api

### Two keys, same endpoints

| `.env` variable | Prefix | Credits spent | Where to get it |
|---|---|---|---|
| `FIRMABLE_API_KEY` | `fbl_` | Subscription credits, then add-on credits | App dashboard (link above) |
| `FIRMABLE_DATAAPI_KEY` | `fbl_dev_` | Developer credits (separate pool: 40 free/month, bought credits never expire) | https://app.firmable.com/developer |

Both keys hit the same base URL and endpoints with the same responses. Pick the key with `FirmableClient(use_developer_key=True)`; the default is `FIRMABLE_API_KEY`. Developer credits: 1 credit per new company or person profile, paid once per org; reveals of an already-paid profile and all searches are free. Developer balance is under Usage at https://app.firmable.com/developer.

---

## Rate Limits

**50 requests per second per API key.**

---

## HTTP Methods

- `GET` — Read data. Filtering/sorting/pagination via query parameters.
- `POST` — Used for search endpoints. Body is JSON.

---

## Endpoints

### 1. GET /company — Company Enrichment

Retrieve full company profile by any one identifier.

**Query Parameters** (pass exactly one):

| Parameter | Type   | Description                          | Example                                      |
|-----------|--------|--------------------------------------|----------------------------------------------|
| `id`      | string | Firmable company ID                  | `f000000117274`                              |
| `ln_slug` | string | LinkedIn company slug                | `smec`                                       |
| `ln_url`  | string | Full LinkedIn company URL            | `https://www.linkedin.com/company/smec`      |
| `fqdn`    | string | Domain name (fully qualified)        | `smec.com`                                   |
| `abn`     | string | Australian Business Number           | `47065475149`                                |
| `website` | string | Company website URL                  | `https://smec.com`                           |

**Response (200):** Company object

```json
{
  "id": "f000000117274",
  "name": "Company Name",
  "website": "https://example.com",
  "fqdn": "example.com",
  "description": "...",
  "tagline": "...",
  "linkedin": "https://www.linkedin.com/company/example",
  "employee_count": 120,
  "year_founded": 2010,
  "hq_location": "Sydney, NSW, AU",
  "hq_country": "AU",
  "company_size": "51-200",
  "company_type": "Private",
  "abn": "...",
  "abn_status": "Active",
  "industries": ["Software", "SaaS"],
  "revenue": "...",
  "phones": [...],
  "emails": [...],
  "social_media": {...},
  "nextGen": {
    "technographics": [...],
    "web_traffic": {...},
    "employee_reviews": {...}
  }
}
```

**Error (400):**
```json
{ "error": { "code": "...", "message": "..." } }
```

---

### 2. GET /people — Person Enrichment

Retrieve full contact profile by any one identifier.

**Query Parameters** (pass exactly one):

| Parameter        | Type   | Description                    | Example                                          |
|------------------|--------|--------------------------------|--------------------------------------------------|
| `id`             | string | Firmable person ID             | `fp000000067890`                                 |
| `ln_slug`        | string | LinkedIn person slug           | `chathchw`                                       |
| `ln_url`         | string | Full LinkedIn profile URL      | `https://www.linkedin.com/in/chathchw`           |
| `work_email`     | string | Work email address             | `name@company.com`                               |
| `personal_email` | string | Personal email address         | `name@gmail.com`                                 |

**Response (200):** People object

```json
{
  "id": "fp000000067890",
  "name": "Jane Smith",
  "first_name": "Jane",
  "last_name": "Smith",
  "headline": "Head of Sales at Acme",
  "position": "Head of Sales",
  "department": "Sales",
  "seniority": "VP/Director",
  "gender": "Female",
  "current_company": {
    "id": "f000000117274",
    "name": "Acme",
    "website": "https://acme.com",
    "industry": "Software"
  },
  "time_in_current_role": "2 years",
  "year_joined": 2022,
  "emails": [
    { "type": "work", "email": "jane@acme.com", "deliverability": "valid" }
  ],
  "phones": [
    { "number": "+61...", "dnd": false }
  ],
  "linkedin": "https://www.linkedin.com/in/...",
  "skills": [...],
  "education": [...],
  "secondary_position": [...],
  "social_media": { "linkedin": {...}, "github": {...}, "twitter": {...} }
}
```

---

### 3. POST /people/search — Search People by Company

Search contacts at a known company, with optional filters.

**Request Body (JSON):**

| Field             | Type   | Required | Description                          |
|-------------------|--------|----------|--------------------------------------|
| `companyId`       | string | Yes      | Firmable company ID                  |
| `selectedCountry` | string | No       | Country code e.g. `"AU"`             |
| `position`        | string | No       | Job title keyword                    |
| `seniority`       | string | No       | See seniority codes below            |
| `department`      | string | No       | See department codes below           |
| `from`            | string | No       | Pagination offset (default: 0)       |
| `size`            | string | No       | Results per page (default varies)    |

**Seniority Codes:**

| Code | Label                    |
|------|--------------------------|
| 1    | Board Member / Director  |
| 2    | Owner / Founder          |
| 3    | C-Suite                  |
| 4    | VP / Director            |
| 5    | Manager                  |
| 6    | Other                    |
| 7    | No Data Available        |

**Department Codes:**

| Code | Label                      |
|------|----------------------------|
| 1    | General Management         |
| 2    | Sales                      |
| 3    | Trades                     |
| 4    | Operations                 |
| 5    | Engineering & Technical    |
| 6    | HR                         |
| 7    | Customer Service           |
| 8    | Medicine & Healthcare      |
| 9    | Research & Analysis        |
| 10   | Legal                      |
| 11   | Marketing                  |
| 12   | Education & Training       |
| 13   | Consulting                 |
| 14   | Finance                    |
| 15   | Product                    |
| 16   | Other                      |
| 17   | No Data Available          |

**Response (200):** Object wrapping an array of person summaries

```json
{
  "success": true,
  "total": 1,
  "records": [
  {
    "person_id": "fp000000067890",
    "position": "Head of Sales",
    "company_name": "Acme",
    "linkedin": "chathchw",
    "has_email": true,
    "has_personal_email": false,
    "has_phone": true,
    "has_mobile": true,
    "has_dnd_phone": false
  }
  ]
}
```
> Note: `find_contacts()` in `utils/firmable.py` automatically unwraps `records` and returns the array directly.

### 5. GET /tech-intel — Technologies a Company Uses

Docs: https://docs.firmable.com/api-reference/tech-intelligence

Pass exactly one of `id`, `ln_url`, `ln_slug`, `fqdn`, `website`, `abn` (first wins in that order if several are sent). Returns no company profile. Tech Intelligence must be on the plan, otherwise `403`. Costs up to 5 credits per company, once; later pages and repeats are free. A known company with no tech data returns `200`, `total: 0`, free.

Response:
```json
{
  "id": "f000000740279",
  "total": 558,
  "tech_intelligence": [
    {"product": "Claude (Anthropic)", "product_slug": "anthropic", "vendor": "Anthropic",
     "filter": "LLM APIs & apps", "category": "AI & Machine Learning", "pillar_slug": "ai-machine-learning",
     "confidence": "high", "recency": "30d", "last_observed": "2026-10-28", "nature": "direct"}
  ],
  "next_cursor": "..."
}
```
- Up to 100 technologies per page; pass `next_cursor` back as `cursor` with the same identifier. No `next_cursor` = last page.
- `confidence`: high / medium / low. `recency`: 30d / 90d / older. `nature`: direct / derived.

### 6. GET /filter-options — Filter Option Codes

Free. Query params: `identifiers` (comma-separated, e.g. `seniority,department`; all filters if omitted), `search` and `offset` (only with exactly one of industry, location, hq_location, people_location; pages of 20), `levelOne` (e.g. `l1:J`, lists second-level industry codes). Response: `{markets: [...], filters: {...}}`.

---

## Usage Patterns

### Look up a company by LinkedIn URL
```python
from utils.firmable import FirmableClient
client = FirmableClient()
company = client.search_by_linkedin("https://www.linkedin.com/company/smec")
firmable_id = company.get("id")
```

### Look up a company by domain
```python
company = client.lookup_company("smec.com")
```

### Enrich a person by email
```python
person = client.get_person(work_email="name@company.com")
```

### Search contacts at a company (e.g. Sales VPs)
```python
contacts = client.find_contacts(
    company_id="f000000117274",
    department=2,   # Sales
    seniority=4,    # VP/Director
    country="AU"
)
```

---

---

### 4. OS Search API — Sales Team Size by Region

Separate API for regional sales headcount. Requires `FIRMABLE_OS_API_KEY` (different key from main API).

**Endpoint:** `POST https://staging-search.firmable.com/apikey/os_search`  
**Auth:** `x-api-key` header (not Bearer token)

**Correct query pattern** — use `has_parent` + `terms` on `countries` field:

```python
payload = {
    "query": {
        "bool": {
            "filter": [
                {"has_parent": {
                    "parent_type": "company",
                    "query": {"ids": {"values": [company_id]}},
                }},
                {"term": {"department": 2}},   # 2 = Sales
            ]
        }
    },
    "aggs": {
        "by_country": {
            "terms": {"field": "countries", "size": 20}
        }
    },
    "size": 0,
}
```

**Important:** Country codes in the `countries` field are **lowercase** (`au`, `nz`, `sg`, `ph`, `my`, `id`, `hk`, `jp`, `us`).

**Do NOT use** the `children` aggregation or Painless scripts to derive country — these fail silently for non-ANZ-headquartered companies (e.g. global SaaS companies with AU sales teams return 0 when they have real data). The `countries` field + `has_parent` approach works correctly across all company types.

**SEA countries:** `ph`, `my`, `sg`, `id`, `hk`, `jp`

Always call via `FirmableClient.get_sales_team_size(company_id)` — never write raw OS Search calls.

---

## Wrapper Notes

`scripts/firmable_api.py` wraps these endpoints. Correct base URL is `https://api.firmable.com` (no `/v1`).

| Wrapper Method                    | Endpoint                  | Notes                                              |
|-----------------------------------|---------------------------|----------------------------------------------------|
| `lookup_company(fqdn)`            | `GET /company?fqdn=`      | Pass domain only, no `https://` prefix             |
| `lookup_company_by_id(id)`        | `GET /company?id=`        | Pass Firmable company ID                           |
| `search_by_linkedin(url)`         | `GET /company?ln_url=`    | Pass full LinkedIn URL                             |
| `get_person(**kwargs)`            | `GET /people`             | Pass one of: id, ln_url, work_email, etc.          |
| `find_contacts(...)`              | `POST /people/search`     | Requires Firmable company ID                       |
| `get_sales_team_size(company_id)` | OS Search API             | Requires `FIRMABLE_OS_API_KEY`; returns regional headcount |
| `get_tech_intel(**kwargs)`        | `GET /tech-intel`         | One identifier; follows all pages by default; up to 5 credits once |
| `get_filter_options(...)`         | `GET /filter-options`     | Free; option codes for seniority, department, industry, etc. |

`FirmableClient(use_developer_key=True)` switches every method above (except `get_sales_team_size`) to `FIRMABLE_DATAAPI_KEY`.
