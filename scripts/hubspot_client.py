from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()


class HubSpotClient:
    BASE_URL = "https://api.hubapi.com"

    def __init__(self):
        self.token = os.getenv("HUBSPOT_ACCESS_TOKEN")
        if not self.token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN is not set in .env")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # ── Base HTTP methods ──────────────────────────────────────────────────

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, payload):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _patch(self, endpoint, payload):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint, payload):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.put(url, headers=self.headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    # ── Contacts ───────────────────────────────────────────────────────────

    def search_contacts(self, property_name: str, value: str) -> list:
        """Search contacts by any property value. Returns list of matching contact objects."""
        payload = {
            "filterGroups": [{"filters": [{"propertyName": property_name, "operator": "EQ", "value": value}]}],
            "properties": ["hs_object_id", "email", "phone", "firstname", "lastname"],
            "limit": 5,
        }
        result = self._post("/crm/v3/objects/contacts/search", payload)
        return result.get("results", [])

    def create_contact(self, properties: dict) -> dict:
        """Create a new contact. Returns created contact object."""
        return self._post("/crm/v3/objects/contacts", {"properties": properties})

    def update_contact(self, contact_id: str, properties: dict) -> dict:
        """Update an existing contact by ID."""
        return self._patch(f"/crm/v3/objects/contacts/{contact_id}", {"properties": properties})

    def create_or_update_contact(self, email: str, properties: dict) -> dict:
        """Legacy upsert by email using 409 conflict. Prefer search_contacts + create/update."""
        payload = {"properties": {"email": email, **properties}}
        try:
            return self._post("/crm/v3/objects/contacts", payload)
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                contact_id = e.response.json()["message"].split(":")[-1].strip()
                return self._patch(f"/crm/v3/objects/contacts/{contact_id}", {"properties": properties})
            raise

    # ── Companies ──────────────────────────────────────────────────────────

    def search_companies(self, domain: str) -> list:
        """Search for companies by domain (EQ then CONTAINS_TOKEN fallback)."""
        for operator in ("EQ", "CONTAINS_TOKEN"):
            payload = {
                "filterGroups": [{"filters": [{"propertyName": "domain", "operator": operator, "value": domain}]}],
                "properties": ["hs_object_id", "name", "domain"],
                "limit": 5,
            }
            result = self._post("/crm/v3/objects/companies/search", payload)
            matches = result.get("results", [])
            if matches:
                return matches
        return []

    def search_companies_by_name(self, name: str) -> list:
        """Search for companies by name (exact match). Used as fallback when domain search fails."""
        payload = {
            "filterGroups": [{"filters": [{"propertyName": "name", "operator": "EQ", "value": name}]}],
            "properties": ["hs_object_id", "name", "domain"],
            "limit": 5,
        }
        result = self._post("/crm/v3/objects/companies/search", payload)
        return result.get("results", [])

    def create_company(self, properties: dict) -> dict:
        """Create a new company. Returns created company object."""
        return self._post("/crm/v3/objects/companies", {"properties": properties})

    def update_company(self, company_id: str, properties: dict) -> dict:
        """Update an existing company by ID."""
        return self._patch(f"/crm/v3/objects/companies/{company_id}", {"properties": properties})

    def create_or_update_company(self, domain: str, properties: dict) -> dict:
        """Legacy upsert by domain."""
        payload = {"properties": {"domain": domain, **properties}}
        return self._post("/crm/v3/objects/companies", payload)

    # ── Associations ───────────────────────────────────────────────────────

    def associate_contact_to_company(self, contact_id: str, company_id: str) -> None:
        """Associate a contact to a company using the default association type."""
        # Note: "from" is a Python reserved word so we build the dict with string key
        self._post(
            "/crm/v4/associations/contacts/companies/batch/associate/default",
            {"inputs": [{"from": {"id": contact_id}, "to": {"id": company_id}}]},
        )

    # ── Lists ──────────────────────────────────────────────────────────────

    def create_static_list(self, name: str) -> dict:
        """Create a static (manual) contact list. Returns list object including listId."""
        return self._post("/crm/v3/lists", {
            "name": name,
            "objectTypeId": "0-1",
            "processingType": "MANUAL",
        })

    def add_contacts_to_list(self, list_id: str, contact_ids: list) -> None:
        """Add contact IDs to a static list. Body is a plain array. Batches 100 at a time."""
        for i in range(0, len(contact_ids), 100):
            batch = contact_ids[i:i + 100]
            self._put(f"/crm/v3/lists/{list_id}/memberships/add", batch)

    # ── Portal ─────────────────────────────────────────────────────────────

    def get_portal_id(self) -> str:
        """Return the HubSpot portal (account) ID."""
        result = self._get("/integrations/v1/me")
        return str(result.get("portalId", ""))

    # ── Eligibility / read-only engagement queries ─────────────────────────

    def get_contact_by_email(self, email: str) -> dict | None:
        """Look up a single contact by email. Returns contact dict with lifecyclestage,
        associatedcompanyid, and hs_last_contacted, or None if not found."""
        payload = {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
            "properties": ["hs_object_id", "email", "firstname", "lastname", "lifecyclestage", "associatedcompanyid", "hs_last_contacted"],
            "limit": 1,
        }
        result = self._post("/crm/v3/objects/contacts/search", payload)
        results = result.get("results", [])
        return results[0] if results else None

    def get_company_properties(self, company_id: str, properties: list) -> dict:
        """Fetch specific properties from a company record. Returns the properties dict."""
        prop_str = ",".join(properties)
        result = self._get(f"/crm/v3/objects/companies/{company_id}", params={"properties": prop_str})
        return result.get("properties", {})

    def get_associated_ids(self, from_object_type: str, from_id: str, to_object_type: str) -> list:
        """Return a list of string IDs associated with the given object via the v4 associations API."""
        result = self._get(f"/crm/v4/objects/{from_object_type}/{from_id}/associations/{to_object_type}")
        return [str(r["toObjectId"]) for r in result.get("results", [])]

    def get_deal_stage_label_map(self) -> dict:
        """Return a dict mapping deal stage ID → human-readable label across all pipelines."""
        result = self._get("/crm/v3/pipelines/deals")
        label_map = {}
        for pipeline in result.get("results", []):
            for stage in pipeline.get("stages", []):
                label_map[stage["id"]] = stage["label"]
        return label_map

    def get_company_deal_stages(self, company_id: str) -> list:
        """Return a list of dealstage values for all deals associated with a company."""
        deal_ids = self.get_associated_ids("companies", company_id, "deals")
        if not deal_ids:
            return []
        deals = self.batch_get_objects("deals", deal_ids, ["dealstage"])
        return [d.get("properties", {}).get("dealstage", "") for d in deals]

    def get_owners(self) -> list:
        """Return list of HubSpot owners (users). Each item has id, email, firstName, lastName."""
        result = self._get("/crm/v3/owners", params={"limit": 100})
        return result.get("results", [])

    def get_property_options(self, object_type: str, property_name: str) -> list:
        """Return enum options for a CRM property. Each item has 'label' and 'value'."""
        result = self._get(f"/crm/v3/properties/{object_type}/{property_name}")
        return result.get("options", [])

    def batch_get_objects(self, object_type: str, ids: list, properties: list) -> list:
        """Batch read CRM objects by ID. Handles chunks of 100. Returns flat list of result dicts."""
        if not ids:
            return []
        all_results = []
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            payload = {
                "inputs": [{"id": obj_id} for obj_id in chunk],
                "properties": properties,
            }
            result = self._post(f"/crm/v3/objects/{object_type}/batch/read", payload)
            all_results.extend(result.get("results", []))
        return all_results
