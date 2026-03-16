import os
import requests
from dotenv import load_dotenv

load_dotenv()


class FirmableClient:
    BASE_URL = "https://api.firmable.com"

    def __init__(self):
        self.api_key = os.getenv("FIRMABLE_API_KEY")
        if not self.api_key:
            raise ValueError("FIRMABLE_API_KEY is not set in .env")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, body=None):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.post(url, headers=self.headers, json=body)
        response.raise_for_status()
        return response.json()

    def lookup_company(self, domain: str) -> dict:
        """Look up a company by domain name (fqdn). Strip protocol/path first."""
        fqdn = domain.replace("https://", "").replace("http://", "").split("/")[0].lstrip("www.")
        return self._get("/company", params={"fqdn": fqdn})

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
        """Search people at a company. department/seniority use numeric codes — see firmable_api_reference.md."""
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
