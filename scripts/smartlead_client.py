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

    def create_campaign(self, name: str) -> dict:
        """Create a new SmartLead campaign. Returns the created campaign dict (includes 'id')."""
        payload = {"name": name}
        return self._post("/campaigns", payload)

    def add_email_sequence(self, campaign_id: str, steps: list) -> dict:
        """Add email sequence steps to a campaign.

        Each step: {"subject": str, "email_body": str, "seq_number": int, "seq_delay_details": {"delay_in_days": int}}
        """
        payload = {"sequences": steps}
        return self._post(f"/campaigns/{campaign_id}/sequences", payload)

    def get_campaign_leads(self, campaign_id: str, status: str = None, limit: int = 100, offset: int = 0) -> dict:
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return self._get(f"/campaigns/{campaign_id}/leads", params=params)

    def get_lead_message_history(self, campaign_id: str, lead_id: int) -> dict:
        return self._get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")

    def get_untracked_replies(self, limit: int = 100, offset: int = 0) -> dict:
        return self._get("/master-inbox/untracked-replies", params={"limit": limit, "offset": offset})

    def get_campaign_sequences(self, campaign_id: str) -> list:
        return self._get(f"/campaigns/{campaign_id}/sequences")

    def get_campaign_analytics(self, campaign_id: str) -> dict:
        return self._get(f"/campaigns/{campaign_id}/analytics")

    def get_email_accounts(self, limit: int = 100, offset: int = 0) -> list:
        result = self._get("/email-accounts", params={"limit": limit, "offset": offset})
        return result if isinstance(result, list) else result.get("data", [])

    def get_inbox_replies(self, offset: int = 0, limit: int = 20,
                          start_date: str = None, end_date: str = None) -> dict:
        """Fetch from the main master inbox (POST /master-inbox/inbox-replies).

        Response: {"ok": true, "data": [...], "offset": N, "limit": N}
        Each record has email_account_id, email_campaign_name, last_reply_time, lead_*.
        start_date / end_date: ISO 8601 strings for replyTimeBetween filter.
        """
        filters = {}
        if start_date and end_date:
            filters["replyTimeBetween"] = [start_date, end_date]
        payload = {"offset": offset, "limit": limit, "sortBy": "REPLY_TIME_DESC", "filters": filters}
        url = f"{self.BASE_URL}/master-inbox/inbox-replies"
        resp = requests.post(url, params={"api_key": self.api_key, "fetch_message_history": "false"}, json=payload)
        resp.raise_for_status()
        return resp.json()
