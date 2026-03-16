"""
Slack bot: /find-contacts

Flow:
  1. User runs /find-contacts in a Slack channel
  2. Bot asks them to upload a companies XLSX (columns: company_name, domain, firmable_company_id)
  3. Bot asks which country to search contacts for
  4. Bot finds contacts via Firmable (VP/Director Sales top 5, C-Suite top 2)
  5. Bot posts a summary with a "Name this list" button
  6. User fills in a modal with the HubSpot list name
  7. Bot shows a HubSpot preview (existing vs new) with Confirm / Cancel buttons
  8. On Confirm: upserts companies + contacts, creates HubSpot list, posts the URL

Usage:
    PYTHONPATH=. python3 workflows/contact_finder/bot.py

Required .env keys:
    SLACK_BOT_TOKEN   xoxb-...
    SLACK_APP_TOKEN   xapp-...
    FIRMABLE_API_KEY
    HUBSPOT_ACCESS_TOKEN
"""

import csv
import io
import os
import re
import threading

import openpyxl
import requests as req
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from utils.firmable import FirmableClient
from utils.hubspot import HubSpotClient

load_dotenv()

app = App(token=os.getenv("SLACK_BOT_TOKEN"))

# ── In-memory session store ─────────────────────────────────────────────────
# sessions[user_id] = {
#     "channel": str,
#     "companies": list[dict],
#     "country": str,          # e.g. "AU"
#     "contacts": list[dict],
#     "list_name": str,
#     "preview": dict,
# }
sessions: dict = {}

COUNTRIES = [
    ("Australia",    "AU"),
    ("Singapore",    "SG"),
    ("New Zealand",  "NZ"),
    ("Malaysia",     "MY"),
    ("Indonesia",    "ID"),
    ("Philippines",  "PH"),
    ("Hong Kong",    "HK"),
    ("Japan",        "JP"),
]


# ── Phone normalisation ─────────────────────────────────────────────────────

def _normalise_phone(phone: str) -> str:
    return re.sub(r"[\s\-\(\)]", "", phone)


# ── File parsing (CSV + XLSX) ───────────────────────────────────────────────

def parse_companies_file(content: bytes, filename: str) -> list:
    """Parse a CSV or XLSX file and return rows with firmable_company_id."""
    if filename.lower().endswith(".xlsx"):
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        result = []
        for row in rows[1:]:
            d = {headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)}
            if d.get("firmable_company_id"):
                result.append(d)
        return result
    else:
        # CSV fallback
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [r for r in reader if r.get("firmable_company_id")]


# ── Firmable helpers ────────────────────────────────────────────────────────

SEARCH_PASSES = [
    {"seniority": 4, "cap": 5, "label": "VP/Director Sales"},
    {"seniority": 3, "cap": 2, "label": "C-Suite Sales"},
]
_SEARCH_SIZE = 100
_CONTACT_PRIORITY = {
    (True, True): 0,
    (True, False): 1,
    (False, True): 2,
    (False, False): 3,
}


def _extract_work_email(person: dict) -> str:
    emails = person.get("emails", {})
    if isinstance(emails, dict):
        for entry in emails.get("work", []):
            val = entry.get("value", "")
            if val:
                return val
    return ""


def _extract_phone(person: dict) -> str:
    for entry in person.get("phones", []):
        if not entry.get("is_dnd", True) and entry.get("value"):
            return entry["value"]
    return ""


def _linkedin_url(slug: str) -> str:
    if not slug:
        return ""
    if slug.startswith("http"):
        return slug
    return f"https://www.linkedin.com/in/{slug}"


def _contact_priority(row: dict) -> int:
    return _CONTACT_PRIORITY.get((bool(row["phone"]), bool(row["work_email"])), 3)


def _enrich_and_filter(client: FirmableClient, summaries: list,
                        company_name: str, domain: str, company_id: str,
                        cap: int) -> list:
    summaries.sort(key=lambda s: (
        0 if (s.get("has_phone") or s.get("has_mobile")) and s.get("has_email") else
        1 if (s.get("has_phone") or s.get("has_mobile")) else
        2 if s.get("has_email") else 3
    ))
    rows = []
    for summary in summaries:
        if len(rows) >= cap:
            break
        person_id = summary.get("person_id", "")
        if not person_id:
            continue
        try:
            person = client.get_person(id=person_id)
            work_email = _extract_work_email(person)
            phone = _extract_phone(person)
            if not work_email and not phone:
                continue
            rows.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "full_name": person.get("name", ""),
                "person_id": person_id,
                "position": person.get("position", summary.get("position", "")),
                "work_email": work_email,
                "phone": phone,
                "linkedin_url": _linkedin_url(person.get("linkedin", "")),
                "company_name": company_name,
                "domain": domain,
                "firmable_company_id": company_id,
            })
        except Exception:
            pass
    rows.sort(key=_contact_priority)
    return rows


def find_contacts_for_companies(companies: list, country: str) -> list:
    client = FirmableClient()
    all_rows = []
    for company in companies:
        company_id = company.get("firmable_company_id", "")
        company_name = company.get("company_name", "")
        domain = company.get("domain", "")
        if not company_id:
            continue
        seen_ids = set()
        for p in SEARCH_PASSES:
            try:
                results = client.find_contacts(
                    company_id=company_id,
                    seniority=p["seniority"],
                    department=2,
                    country=country,
                    size=_SEARCH_SIZE,
                )
                summaries = [r for r in (results or []) if r.get("person_id") not in seen_ids]
                seen_ids.update(r["person_id"] for r in summaries if r.get("person_id"))
                rows = _enrich_and_filter(client, summaries, company_name, domain, company_id, cap=p["cap"])
                all_rows.extend(rows)
            except Exception:
                pass
    return all_rows


# ── HubSpot helpers ─────────────────────────────────────────────────────────

def _contact_props(row: dict) -> dict:
    props = {}
    if row.get("first_name"):   props["firstname"] = row["first_name"]
    if row.get("last_name"):    props["lastname"] = row["last_name"]
    if row.get("position"):     props["jobtitle"] = row["position"]
    if row.get("work_email"):   props["email"] = row["work_email"]
    if row.get("phone"):        props["phone"] = row["phone"]
    if row.get("linkedin_url"): props["linkedin_profile"] = row["linkedin_url"]
    return props


def _company_props(row: dict) -> dict:
    props = {}
    if row.get("company_name"): props["name"] = row["company_name"]
    if row.get("domain"):       props["domain"] = row["domain"]
    return props


def hs_preview(hs: HubSpotClient, contacts: list) -> dict:
    company_existing, company_new = {}, []
    seen_domains = set()
    for row in contacts:
        domain = row.get("domain", "")
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        try:
            matches = hs.search_companies(domain)
            if matches:
                company_existing[domain] = matches[0]["id"]
            else:
                company_new.append(domain)
        except Exception:
            pass

    contact_existing, contact_new, contact_skipped = {}, [], []
    for row in contacts:
        person_id = row.get("person_id", "")
        email = row.get("work_email", "")
        phone = row.get("phone", "")
        if not email and not phone:
            contact_skipped.append(person_id)
            continue
        try:
            matches = hs.search_contacts("email", email) if email else hs.search_contacts("phone", _normalise_phone(phone))
            if matches:
                contact_existing[person_id] = matches[0]["id"]
            else:
                contact_new.append(person_id)
        except Exception:
            pass

    return {
        "company_existing": company_existing,
        "company_new": company_new,
        "contact_existing": contact_existing,
        "contact_new": contact_new,
        "contact_skipped": contact_skipped,
    }


def hs_execute(hs: HubSpotClient, contacts: list, list_name: str) -> dict:
    seen_domains = {}
    for row in contacts:
        domain = row.get("domain", "")
        if not domain or domain in seen_domains:
            continue
        try:
            matches = hs.search_companies(domain)
            props = _company_props(row)
            if matches:
                company_id = matches[0]["id"]
                hs.update_company(company_id, props)
            else:
                company_id = hs.create_company(props)["id"]
            seen_domains[domain] = company_id
        except Exception:
            seen_domains[domain] = None

    contact_ids = []
    for row in contacts:
        email = row.get("work_email", "")
        phone = row.get("phone", "")
        if not email and not phone:
            continue
        props = _contact_props(row)
        try:
            if email:
                matches = hs.search_contacts("email", email)
                if matches:
                    contact_id = matches[0]["id"]
                    hs.update_contact(contact_id, props)
                else:
                    contact_id = hs.create_contact(props)["id"]
            else:
                matches = hs.search_contacts("phone", _normalise_phone(phone))
                if matches:
                    contact_id = matches[0]["id"]
                    hs.update_contact(contact_id, props)
                else:
                    contact_id = hs.create_contact(props)["id"]

            contact_ids.append(contact_id)
            company_id = seen_domains.get(row.get("domain", ""))
            if company_id:
                try:
                    hs.associate_contact_to_company(contact_id, company_id)
                except Exception:
                    pass
        except Exception:
            pass

    if not contact_ids:
        return {"error": "No contacts synced."}

    list_result = hs.create_static_list(list_name)
    list_id = list_result.get("listId") or list_result.get("id") or list_result.get("list", {}).get("listId")
    hs.add_contacts_to_list(str(list_id), contact_ids)

    portal_id = hs.get_portal_id()
    url = f"https://app-ap1.hubspot.com/contacts/{portal_id}/objectLists/{list_id}/"
    return {"synced": len(contact_ids), "total": len(contacts), "url": url}


# ── Slack blocks ────────────────────────────────────────────────────────────

def _country_select_blocks(n_companies: int) -> list:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Got it — found *{n_companies} companies*. Which country should I search contacts for?",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": "select_country",
                    "placeholder": {"type": "plain_text", "text": "Select a country"},
                    "options": [
                        {"text": {"type": "plain_text", "text": label}, "value": code}
                        for label, code in COUNTRIES
                    ],
                }
            ],
        },
    ]


def _summary_blocks(contacts: list, user_id: str, country_label: str) -> list:
    total = len(contacts)
    with_both = sum(1 for r in contacts if r["work_email"] and r["phone"])
    phone_only = sum(1 for r in contacts if r["phone"] and not r["work_email"])
    email_only = sum(1 for r in contacts if r["work_email"] and not r["phone"])

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Found {total} contacts* across {len(set(r['company_name'] for r in contacts))} companies "
                    f"({country_label})\n"
                    f"Phone + email: {with_both}  |  Phone only: {phone_only}  |  Email only: {email_only}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Name this list →"},
                    "action_id": "name_list",
                    "style": "primary",
                    "value": user_id,
                }
            ],
        },
    ]


def _preview_blocks(list_name: str, preview: dict, user_id: str) -> list:
    n_ce = len(preview["company_existing"])
    n_cn = len(preview["company_new"])
    n_xe = len(preview["contact_existing"])
    n_xn = len(preview["contact_new"])
    n_xs = len(preview["contact_skipped"])

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*HubSpot preview*\n"
                    f"```\n"
                    f"List name : {list_name}\n\n"
                    f"Companies\n"
                    f"  existing : {n_ce}  (will be updated)\n"
                    f"  new      : {n_cn}  (will be created)\n\n"
                    f"Contacts\n"
                    f"  existing : {n_xe}  (will be updated)\n"
                    f"  new      : {n_xn}  (will be created)\n"
                    f"  skipped  : {n_xs}  (no email or phone)\n"
                    f"```"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✓ Confirm sync"},
                    "action_id": "confirm_sync",
                    "style": "primary",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✗ Cancel"},
                    "action_id": "cancel_sync",
                    "style": "danger",
                    "value": user_id,
                },
            ],
        },
    ]


# ── Slash command ───────────────────────────────────────────────────────────

@app.command("/find-contacts")
def handle_find_contacts(ack, body, client):
    ack()
    user_id = body["user_id"]
    channel_id = body["channel_id"]

    sessions[user_id] = {"channel": channel_id}

    client.chat_postMessage(
        channel=channel_id,
        text=(
            f"<@{user_id}> Upload your companies XLSX in this channel and I'll find the contacts.\n"
            "The file must have these columns: `company_name`, `domain`, `firmable_company_id`\n"
            "_(You can download this directly from Firmable)_"
        ),
    )


# ── File upload ─────────────────────────────────────────────────────────────

@app.event("file_shared")
def handle_file_shared(event, client, say):
    file_id = event.get("file_id")
    user_id = event.get("user_id")
    channel_id = event.get("channel_id")

    if user_id not in sessions:
        return

    sessions[user_id]["channel"] = channel_id

    try:
        file_info = client.files_info(file=file_id)["file"]
        filename = file_info.get("name", "upload.xlsx")
        url = file_info.get("url_private_download") or file_info.get("url_private")
        resp = req.get(url, headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"})
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        say(channel=channel_id, text=f"Could not read the file: {e}")
        return

    companies = parse_companies_file(content, filename)
    if not companies:
        say(channel=channel_id, text="The file doesn't look right — make sure it has `company_name`, `domain`, and `firmable_company_id` columns with at least one row.")
        return

    sessions[user_id]["companies"] = companies

    client.chat_postMessage(
        channel=channel_id,
        text=f"Got it — found {len(companies)} companies. Which country?",
        blocks=_country_select_blocks(len(companies)),
    )


# ── Country selection ───────────────────────────────────────────────────────

@app.action("select_country")
def handle_select_country(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    country_code = body["actions"][0]["selected_option"]["value"]
    country_label = body["actions"][0]["selected_option"]["text"]["text"]

    if user_id not in sessions:
        client.chat_postMessage(channel=channel_id, text="Session expired. Please run `/find-contacts` again.")
        return

    sessions[user_id]["country"] = country_code
    companies = sessions[user_id].get("companies", [])

    msg = client.chat_postMessage(
        channel=channel_id,
        text=f"Searching for contacts in *{country_label}*... :hourglass_flowing_sand:",
    )
    msg_ts = msg["ts"]

    def run_firmable():
        try:
            contacts = find_contacts_for_companies(companies, country_code)
            sessions[user_id]["contacts"] = contacts

            if not contacts:
                client.chat_update(
                    channel=channel_id,
                    ts=msg_ts,
                    text=f"No contacts found for these companies in {country_label}.",
                )
                return

            client.chat_update(
                channel=channel_id,
                ts=msg_ts,
                text=f"Found {len(contacts)} contacts.",
                blocks=_summary_blocks(contacts, user_id, country_label),
            )
        except Exception as e:
            client.chat_update(
                channel=channel_id,
                ts=msg_ts,
                text=f"Error finding contacts: {e}",
            )

    threading.Thread(target=run_firmable, daemon=True).start()


# ── "Name this list" button → open modal ───────────────────────────────────

@app.action("name_list")
def handle_name_list(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    user_id = body["actions"][0]["value"]

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "list_name_modal",
            "private_metadata": user_id,
            "title": {"type": "plain_text", "text": "Name your HubSpot list"},
            "submit": {"type": "plain_text", "text": "Next →"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "list_name_block",
                    "label": {"type": "plain_text", "text": "HubSpot list name"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "list_name_input",
                        "placeholder": {"type": "plain_text", "text": "e.g. B2B Marketing Leaders Sydney 2026"},
                    },
                }
            ],
        },
    )


# ── Modal submit → HubSpot preview ─────────────────────────────────────────

@app.view("list_name_modal")
def handle_list_name_submit(ack, body, client):
    ack()
    user_id = body["view"]["private_metadata"]
    list_name = body["view"]["state"]["values"]["list_name_block"]["list_name_input"]["value"].strip()

    if not list_name or user_id not in sessions:
        return

    sessions[user_id]["list_name"] = list_name
    channel = sessions[user_id]["channel"]
    contacts = sessions[user_id].get("contacts", [])

    msg = client.chat_postMessage(
        channel=channel,
        text="Checking HubSpot for existing records...",
    )
    msg_ts = msg["ts"]

    def run_preview():
        try:
            hs = HubSpotClient()
            preview = hs_preview(hs, contacts)
            sessions[user_id]["preview"] = preview

            client.chat_update(
                channel=channel,
                ts=msg_ts,
                text=f"HubSpot preview for *{list_name}*",
                blocks=_preview_blocks(list_name, preview, user_id),
            )
        except Exception as e:
            client.chat_update(
                channel=channel,
                ts=msg_ts,
                text=f"Error checking HubSpot: {e}",
            )

    threading.Thread(target=run_preview, daemon=True).start()


# ── Confirm sync ────────────────────────────────────────────────────────────

@app.action("confirm_sync")
def handle_confirm_sync(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    session = sessions.get(user_id)
    if not session:
        client.chat_postMessage(channel=channel, text="Session expired. Please run `/find-contacts` again.")
        return

    contacts = session.get("contacts", [])
    list_name = session.get("list_name", "")

    msg = client.chat_postMessage(
        channel=channel,
        text=f"Syncing {len(contacts)} contacts to HubSpot... :hourglass_flowing_sand:",
    )
    msg_ts = msg["ts"]

    def run_sync():
        try:
            hs = HubSpotClient()
            result = hs_execute(hs, contacts, list_name)

            if "error" in result:
                client.chat_update(channel=channel, ts=msg_ts, text=f"Sync failed: {result['error']}")
            else:
                client.chat_update(
                    channel=channel,
                    ts=msg_ts,
                    text=(
                        f":white_check_mark: Done. *{result['synced']}/{result['total']} contacts synced.*\n"
                        f"{result['url']}"
                    ),
                )
            sessions.pop(user_id, None)
        except Exception as e:
            client.chat_update(channel=channel, ts=msg_ts, text=f"Sync error: {e}")

    threading.Thread(target=run_sync, daemon=True).start()


# ── Cancel ──────────────────────────────────────────────────────────────────

@app.action("cancel_sync")
def handle_cancel(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    sessions.pop(user_id, None)
    client.chat_postMessage(channel=channel, text="Cancelled. Nothing was written to HubSpot.")


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    print("Contact Finder bot is running. Press Ctrl+C to stop.")
    handler.start()
