import os
import requests
from dotenv import load_dotenv

load_dotenv()


class FirmableClient:
    BASE_URL = "https://api.firmable.com"

    def __init__(self, use_developer_key: bool = False):
        """use_developer_key=True uses FIRMABLE_DATAAPI_KEY (fbl_dev_, spends developer credits)
        instead of FIRMABLE_API_KEY (fbl_, spends subscription credits). Same endpoints either way."""
        key_name = "FIRMABLE_DATAAPI_KEY" if use_developer_key else "FIRMABLE_API_KEY"
        self.api_key = os.getenv(key_name)
        if not self.api_key:
            raise ValueError(f"{key_name} is not set in .env")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, body=None):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.post(url, headers=self.headers, json=body, timeout=30)
        response.raise_for_status()
        return response.json()

    def lookup_company(self, domain: str) -> dict:
        """Look up a company by domain name (fqdn). Strip protocol/path first."""
        import re as _re
        fqdn = _re.sub(r"^www\.", "", domain.replace("https://", "").replace("http://", "").split("/")[0])
        return self._get("/company", params={"fqdn": fqdn})

    def lookup_company_by_id(self, company_id: str) -> dict:
        """Look up a company by its Firmable company ID."""
        return self._get("/company", params={"id": company_id})

    def search_by_linkedin(self, linkedin_url: str) -> dict:
        """Look up a company by its full LinkedIn company URL."""
        return self._get("/company", params={"ln_url": linkedin_url})

    def get_person(self, id: str = None, ln_url: str = None,
                   ln_slug: str = None, work_email: str = None,
                   personal_email: str = None) -> dict:
        """Enrich a person by any one identifier."""
        params = {}
        if id:
            params["id"] = id
        elif ln_url:
            params["ln_url"] = ln_url
        elif ln_slug:
            params["ln_slug"] = ln_slug
        elif work_email:
            params["work_email"] = work_email
        elif personal_email:
            params["personal_email"] = personal_email
        else:
            raise ValueError("Provide at least one identifier: id, ln_url, ln_slug, work_email, or personal_email")
        return self._get("/people", params=params)

    def find_contacts(self, company_id: str, department: int = None,
                      seniority: int = None, country: str = None,
                      position: str = None, from_offset: int = 0,
                      size: int = 25) -> list:
        """Search people at a company. department/seniority use numeric codes — see firmable-api-reference.md."""
        body = {"companyId": company_id, "from": str(from_offset), "size": str(size)}
        if department is not None:
            body["department"] = str(department)
        if seniority is not None:
            body["seniority"] = str(seniority)
        if country:
            body["selectedCountry"] = country
        if position:
            body["position"] = position
        result = self._post("/people/search", body=body)
        if isinstance(result, dict):
            return result.get("records", [])
        return result or []

    def get_tech_intel(self, id: str = None, fqdn: str = None, ln_url: str = None,
                       ln_slug: str = None, website: str = None, abn: str = None,
                       all_pages: bool = True) -> dict:
        """Technologies a company uses. Pass one identifier. Returns {id, total, tech_intelligence: [...]}.

        Pages are 100 technologies; all_pages=True follows next_cursor until done. Costs up to
        5 credits per company once (later pages and repeats free). 403 if not on your plan.
        """
        params = {k: v for k, v in {"id": id, "ln_url": ln_url, "ln_slug": ln_slug,
                                    "fqdn": fqdn, "website": website, "abn": abn}.items() if v}
        if not params:
            raise ValueError("Provide one identifier: id, fqdn, ln_url, ln_slug, website, or abn")
        result = self._get("/tech-intel", params=params)
        while all_pages and result.get("next_cursor"):
            page = self._get("/tech-intel", params={**params, "cursor": result["next_cursor"]})
            result["tech_intelligence"].extend(page.get("tech_intelligence", []))
            result["next_cursor"] = page.get("next_cursor")
        return result

    def get_filter_options(self, identifiers: str = None, search: str = None,
                           offset: int = 0, level_one: str = None) -> dict:
        """Option codes for filters (e.g. identifiers="seniority,department"). Free.

        search/offset only work with exactly one of industry, location, hq_location, people_location.
        level_one (e.g. "l1:J") lists second-level industry codes.
        """
        params = {}
        if identifiers:
            params["identifiers"] = identifiers
        if search:
            params["search"] = search
        if offset:
            params["offset"] = offset
        if level_one:
            params["levelOne"] = level_one
        return self._get("/filter-options", params=params)

    def get_sales_team_size(self, company_id: str) -> dict:
        """Return sales team headcount by region for a Firmable company ID.

        Uses the OS Search API (separate base URL and key from the main API).
        Requires FIRMABLE_OS_API_KEY in .env.
        Returns dict with keys: au_sales_team_size, nz_sales_team_size,
        sea_sales_team_size, us_sales_team_size, total_sales_team_size. Values are int or None.
        """
        os_api_key = os.getenv("FIRMABLE_OS_API_KEY")
        if not os_api_key:
            raise ValueError("FIRMABLE_OS_API_KEY is not set in .env")
        payload = {
            "query": {
                "bool": {
                    "filter": [
                        {"has_parent": {
                            "parent_type": "company",
                            "query": {"ids": {"values": [company_id]}},
                        }},
                        {"term": {"department": 2}},
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
        import time as _time
        for attempt in range(4):
            resp = requests.post(
                "https://staging-search.firmable.com/apikey/os_search",
                headers={"x-api-key": os_api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            if resp.status_code == 429 and attempt < 3:
                _time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            break

        buckets = (
            resp.json()
            .get("aggregations", {})
            .get("by_country", {})
            .get("buckets", [])
        )

        counts = {b["key"]: b["doc_count"] for b in buckets}

        def _get(code):
            v = counts.get(code)
            return v if v is not None else None

        sea_vals = [counts[c] for c in ["ph", "my", "sg", "id", "hk", "jp"] if c in counts]

        return {
            "au_sales_team_size":    _get("au"),
            "nz_sales_team_size":    _get("nz"),
            "sea_sales_team_size":   sum(sea_vals) if sea_vals else None,
            "sg_sales_team_size":    _get("sg"),
            "my_sales_team_size":    _get("my"),
            "hk_sales_team_size":    _get("hk"),
            "ph_sales_team_size":    _get("ph"),
            "us_sales_team_size":    _get("us"),
            "total_sales_team_size": sum(counts.values()) if counts else None,
        }
