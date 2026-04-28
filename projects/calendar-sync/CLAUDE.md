# calendar-sync — Sub-Agent

## Purpose
Twice-daily sync of Outlook (Microsoft 365) calendar events to a dedicated Google Calendar. Runs at 12 PM and 6 PM SGT via GitHub Actions. Mirrors creates, updates, and deletes for events in the next 14 days.

## What goes in
- Microsoft Outlook calendar (authenticated via Azure app + OAuth refresh token)
- Credentials loaded from environment variables (locally via `.env`, in CI via GitHub Actions secrets)

## What goes out
- Events created / updated / deleted on the target Google Calendar (`GOOGLE_CALENDAR_ID`)
- Console log summary: `X created, Y updated, Z deleted`

## Scripts / tools

| Script | Role |
|---|---|
| `scripts/sync_calendar.py` | Main sync: fetch MS events → diff → upsert/delete in Google |

## Credentials required

| Variable | Description |
|---|---|
| `MS_CLIENT_ID` | Azure app client ID |
| `MS_CLIENT_SECRET` | Azure app client secret |
| `MS_TENANT_ID` | Azure tenant ID (`common` for personal accounts) |
| `MS_REFRESH_TOKEN` | OAuth refresh token (obtained via one-time auth flow) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON string of Google service account key |
| `GOOGLE_CALENDAR_ID` | Target Google Calendar ID (e.g. `abc@group.calendar.google.com`) |

## One-time setup

### Microsoft
1. [portal.azure.com](https://portal.azure.com) → App registrations → New registration
2. Delegated permission: `Calendars.Read` (Microsoft Graph)
3. Redirect URI: `http://localhost`
4. Note `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`
5. Run the auth flow to get `MS_REFRESH_TOKEN` (see script header comment)

### Google
1. [console.cloud.google.com](https://console.cloud.google.com) → Enable Google Calendar API
2. IAM → Service Accounts → Create → download JSON key
3. Create a Google Calendar named "Microsoft Sync"
4. Share it with the service account email (Make changes to events)
5. Copy calendar ID → `GOOGLE_CALENDAR_ID`

## Conventions
- Deduplication key: Microsoft `iCalUID` stored in Google event `extendedProperties.private.ms_uid`
- All-day events use `start.date` / `end.date` format in Google
- Never write to the main sync script from other workflows
- Run with `PYTHONPATH=.` from repo root
