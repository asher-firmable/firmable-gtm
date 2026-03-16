import os
import requests
from dotenv import load_dotenv

load_dotenv()


class SmartLeadClient:
    BASE_URL = "https://server.smartlead.ai/api/v1"

    def __init__(self):
        self.api_key = os.getenv("SMARTLEAD_API_KEY")
        if not self.api_key:
            raise ValueError("SMARTLEAD_API_KEY is not set in .env")

    def _post(self, endpoint, payload):
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.post(url, params={"api_key": self.api_key}, json=payload)
        response.raise_for_status()
        return response.json()

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def list_campaigns(self) -> list:
        return self._get("/campaigns")

    def add_leads_to_campaign(self, campaign_id: str, leads: list) -> dict:
        payload = {"lead_list": leads}
        return self._post(f"/campaigns/{campaign_id}/leads", payload)
