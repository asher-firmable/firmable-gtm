# Firmable API Reference

Source: https://docs.firmable.com/api-reference/overview
Last updated: 2026-03-15

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
  "au_employee_count": 120,
  "founding_year": 2010,
  "headquarters": "Sydney, NSW",
  "country": "AU",
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

## Wrapper Notes

`utils/firmable.py` wraps these endpoints. Correct base URL is `https://api.firmable.com` (no `/v1`).

| Wrapper Method          | Endpoint                  | Notes                                     |
|-------------------------|---------------------------|-------------------------------------------|
| `lookup_company(fqdn)`  | `GET /company?fqdn=`      | Pass domain only, no `https://` prefix    |
| `search_by_linkedin(url)` | `GET /company?ln_url=`  | Pass full LinkedIn URL                    |
| `get_person(**kwargs)`  | `GET /people`             | Pass one of: id, ln_url, work_email, etc. |
| `find_contacts(...)`    | `POST /people/search`     | Requires Firmable company ID              |
