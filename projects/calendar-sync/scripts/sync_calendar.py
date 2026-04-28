"""
Microsoft Outlook → Google Calendar sync.

One-time refresh token setup (run once locally):
  1. Open this URL in a browser (replace CLIENT_ID and TENANT_ID):
     https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize
       ?client_id={CLIENT_ID}
       &response_type=code
       &redirect_uri=http://localhost
       &scope=Calendars.Read+offline_access
  2. After login, copy the `code` param from the redirect URL.
  3. POST to https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token
     with: client_id, client_secret, grant_type=authorization_code, code, redirect_uri=http://localhost
  4. Save the `refresh_token` from the response as MS_REFRESH_TOKEN in .env / GitHub secret.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import msal
import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_TENANT_ID = os.getenv("MS_TENANT_ID")
MS_REFRESH_TOKEN = os.getenv("MS_REFRESH_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

GRAPH_SCOPES = ["https://graph.microsoft.com/Calendars.Read", "offline_access"]
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar"]
SYNC_DAYS = 14
MS_UID_KEY = "ms_uid"
MS_MODIFIED_KEY = "ms_last_modified"


def get_ms_access_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=MS_CLIENT_ID,
        client_credential=MS_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{MS_TENANT_ID}",
    )
    result = app.acquire_token_by_refresh_token(MS_REFRESH_TOKEN, scopes=GRAPH_SCOPES)
    if "access_token" not in result:
        raise RuntimeError(f"MS token error: {result.get('error_description', result)}")
    return result["access_token"]


def fetch_ms_events(access_token: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=SYNC_DAYS)
    url = "https://graph.microsoft.com/v1.0/me/calendarView"
    params = {
        "startDateTime": now.isoformat(),
        "endDateTime": end.isoformat(),
        "$select": "id,iCalUId,subject,bodyPreview,start,end,location,isAllDay,lastModifiedDateTime",
        "$top": 200,
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    events = []
    while url:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        events.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        params = {}  # nextLink already has params baked in
    return events


def build_google_service():
    sa_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=GOOGLE_SCOPES)
    return build("calendar", "v3", credentials=creds)


def fetch_google_events(service) -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=SYNC_DAYS)
    result = {}
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            privateExtendedProperty=f"{MS_UID_KEY}=*",
            singleEvents=True,
            maxResults=500,
            pageToken=page_token,
        ).execute()
        for event in resp.get("items", []):
            ms_uid = event.get("extendedProperties", {}).get("private", {}).get(MS_UID_KEY)
            if ms_uid:
                result[ms_uid] = event
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return result


def ms_event_to_google(ms: dict) -> dict:
    body: dict = {
        "summary": ms.get("subject", "(No title)"),
        "description": ms.get("bodyPreview", ""),
        "extendedProperties": {
            "private": {
                MS_UID_KEY: ms["iCalUId"],
                MS_MODIFIED_KEY: ms.get("lastModifiedDateTime", ""),
            }
        },
    }

    location = ms.get("location", {}).get("displayName", "")
    if location:
        body["location"] = location

    if ms.get("isAllDay"):
        body["start"] = {"date": ms["start"]["dateTime"][:10]}
        body["end"] = {"date": ms["end"]["dateTime"][:10]}
    else:
        body["start"] = {"dateTime": ms["start"]["dateTime"], "timeZone": ms["start"].get("timeZone", "UTC")}
        body["end"] = {"dateTime": ms["end"]["dateTime"], "timeZone": ms["end"].get("timeZone", "UTC")}

    return body


def sync():
    missing = [v for v in ["MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_TENANT_ID", "MS_REFRESH_TOKEN",
                            "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_CALENDAR_ID"] if not os.getenv(v)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print("Fetching Microsoft calendar events...")
    ms_token = get_ms_access_token()
    ms_events = fetch_ms_events(ms_token)
    ms_map = {e["iCalUId"]: e for e in ms_events}
    print(f"  Found {len(ms_map)} Microsoft events")

    print("Fetching Google calendar events...")
    google_svc = build_google_service()
    google_map = fetch_google_events(google_svc)
    print(f"  Found {len(google_map)} synced Google events")

    created = updated = deleted = 0

    # Create or update
    for ical_uid, ms_event in ms_map.items():
        google_body = ms_event_to_google(ms_event)
        if ical_uid not in google_map:
            google_svc.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=google_body).execute()
            created += 1
        else:
            g_event = google_map[ical_uid]
            stored_modified = g_event.get("extendedProperties", {}).get("private", {}).get(MS_MODIFIED_KEY, "")
            ms_modified = ms_event.get("lastModifiedDateTime", "")
            if ms_modified != stored_modified:
                google_svc.events().update(
                    calendarId=GOOGLE_CALENDAR_ID,
                    eventId=g_event["id"],
                    body=google_body,
                ).execute()
                updated += 1

    # Delete events removed from Microsoft
    for ms_uid, g_event in google_map.items():
        if ms_uid not in ms_map:
            google_svc.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=g_event["id"]).execute()
            deleted += 1

    print(f"Sync complete: {created} created, {updated} updated, {deleted} deleted")


if __name__ == "__main__":
    sync()
