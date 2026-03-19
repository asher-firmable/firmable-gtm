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

Usage (local):
    PYTHONPATH=. python3 find-contacts/scripts/bot.py

Railway start command:
    PYTHONPATH=. python find-contacts/scripts/bot.py

Required .env keys:
    CONTACT_FINDER_SLACK_BOT_TOKEN   xoxb-...
    CONTACT_FINDER_SLACK_APP_TOKEN   xapp-...
    FIRMABLE_API_KEY
    HUBSPOT_ACCESS_TOKEN
"""

import csv
import io
import json
import os
import re
import threading

import openpyxl
import requests as req
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from applications.firmable import FirmableClient
from applications.hubspot import HubSpotClient

load_dotenv()

app = App(token=os.getenv("CONTACT_FINDER_SLACK_BOT_TOKEN"))

# ── Session store (persisted to disk so restarts don't lose state) ───────────
# sessions[user_id] = {
#     "channel": str,
#     "companies": list[dict],
#     "country": str,          # e.g. "AU"
#     "contacts": list[dict],
#     "list_name": str,
#     "preview": dict,
# }

SESSIONS_FILE = os.path.join(os.path.dirname(__file__), "sessions.json")


def _load_sessions() -> dict:
    try:
        with open(SESSIONS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sessions():
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f)


sessions: dict = _load_sessions()

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


def _normalise_domain(domain: str) -> str:
    """Strip protocol and www. prefix so HubSpot domain search matches reliably."""
    domain = domain.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    return domain.split("/")[0]


# ── File parsing (CSV + XLSX) ───────────────────────────────────────────────

def _extract_firmable_id(val: str) -> str:
    """Extract Firmable company ID from a URL or return the value as-is if it's already an ID."""
    if not val:
        return ""
    val = val.strip()
    # Already an ID: f000000117238
    if re.match(r"^f\d+$", val):
        return val
    # Extract the last path segment from any URL ending in /f000000117238
    m = re.search(r"/(f\d+)/?$", val)
    if m:
        return m.group(1)
    return val


def _normalise_headers(raw_headers: list) -> dict:
    """
    Map raw column headers (any casing/spacing) to the canonical names the bot uses.
    Returns a dict of {canonical_name: index}.
    """
    ALIASES = {
        "company_name": ["company name", "company_name", "name"],
        "domain":       ["domain name", "domain", "website", "fqdn"],
        "firmable_company_id": [
            "firmable company link", "firmable company id", "firmable_company_id",
            "company id", "firmable id", "firmable url", "profile url", "url",
        ],
    }
    index_map = {}
    for i, h in enumerate(raw_headers):
        normalised = h.strip().lower().replace("_", " ")
        for canonical, aliases in ALIASES.items():
            if normalised in aliases and canonical not in index_map:
                index_map[canonical] = i
    return index_map


def parse_companies_file(content: bytes, filename: str):
    """
    Parse a CSV or XLSX file and return (rows, raw_headers).
    rows is a list of dicts with keys: company_name, domain, firmable_company_id.
    raw_headers is the list of original column names (for debug messages).
    """
    if filename.lower().endswith(".xlsx"):
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        raw_headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        index_map = _normalise_headers(raw_headers)

        result = []
        for row in rows[1:]:
            def cell(col, _row=row):
                idx = index_map.get(col)
                return str(_row[idx]).strip() if idx is not None and idx < len(_row) and _row[idx] is not None else ""

            firmable_id = _extract_firmable_id(cell("firmable_company_id"))
            if not firmable_id:
                continue
            result.append({
                "company_name": cell("company_name"),
                "domain":       cell("domain"),
                "firmable_company_id": firmable_id,
            })
        return result, raw_headers
    else:
        # CSV fallback — also normalise headers
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        raw_headers = reader.fieldnames or []
        result = []
        for r in reader:
            normalised = {k.strip().lower().replace("_", " "): v for k, v in r.items()}
            firmable_id = _extract_firmable_id(
                normalised.get("firmable company id") or
                normalised.get("firmable_company_id") or
                normalised.get("firmable url") or ""
            )
            if not firmable_id:
                continue
            result.append({
                "company_name": normalised.get("company name") or normalised.get("company_name") or "",
                "domain":       normalised.get("domain name") or normalised.get("domain") or "",
                "firmable_company_id": firmable_id,
            })
        return result, list(raw_headers)


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
    # Build domain → company_name map from contacts
    domain_to_name = {row.get("domain", ""): row.get("company_name", "") for row in contacts}

    company_existing = {}   # domain -> hs_object_id
    company_new = []        # list of (company_name, domain)
    seen_domains = set()
    for row in contacts:
        raw_domain = row.get("domain", "")
        domain = _normalise_domain(raw_domain)
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        try:
            company_name = row.get("company_name", "")
            matches = hs.search_companies(domain) or (hs.search_companies_by_name(company_name) if company_name else [])
            if matches:
                company_existing[domain] = matches[0]["id"]
            else:
                company_new.append((company_name or domain, domain))
        except Exception:
            pass

    contact_existing = {}   # person_id -> hs_object_id
    contact_new = []        # list of (full_name, position)
    contact_skipped = []    # list of full_name
    for row in contacts:
        person_id = row.get("person_id", "")
        email = row.get("work_email", "")
        phone = row.get("phone", "")
        full_name = row.get("full_name") or f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        position = row.get("position", "")
        if not email and not phone:
            contact_skipped.append(full_name)
            continue
        try:
            matches = hs.search_contacts("email", email) if email else hs.search_contacts("phone", _normalise_phone(phone))
            if matches:
                contact_existing[person_id] = matches[0]["id"]
            else:
                contact_new.append((full_name, position))
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
        raw_domain = row.get("domain", "")
        domain = _normalise_domain(raw_domain)
        if not domain or domain in seen_domains:
            continue
        try:
            company_name = row.get("company_name", "")
            matches = hs.search_companies(domain) or (hs.search_companies_by_name(company_name) if company_name else [])
            props = _company_props(row)
            if matches:
                company_id = matches[0]["id"]
                hs.update_company(company_id, props)
            else:
                company_id = hs.create_company(props)["id"]
            seen_domains[raw_domain] = company_id
            seen_domains[domain] = company_id
        except Exception:
            seen_domains[raw_domain] = None
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

    # Build detail lines for new companies and new contacts
    new_company_lines = "\n".join(f"    • {name} ({domain})" for name, domain in preview["company_new"]) or "    (none)"
    new_contact_lines = "\n".join(
        f"    • {name}{', ' + pos if pos else ''}" for name, pos in preview["contact_new"]
    ) or "    (none)"

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
                    f"  new      : {n_cn}  (will be created)\n"
                    f"{new_company_lines}\n\n"
                    f"Contacts\n"
                    f"  existing : {n_xe}  (will be updated)\n"
                    f"  new      : {n_xn}  (will be created)\n"
                    f"{new_contact_lines}\n"
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

    sessions[user_id] = {"channel": channel_id}  # always reset, clears any previous state
    _save_sessions()

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
    channel_id = event.get("channel_id") or (sessions.get(user_id, {}).get("channel"))

    print(f"[file_shared] user={user_id} file={file_id} channel={channel_id} session_exists={user_id in sessions}")

    if user_id not in sessions:
        if channel_id:
            client.chat_postMessage(
                channel=channel_id,
                text="Please run `/find-contacts` first, then upload your file.",
            )
        return

    sessions[user_id]["channel"] = channel_id
    _save_sessions()

    try:
        file_info = client.files_info(file=file_id)["file"]
        filename = file_info.get("name", "upload.xlsx")
        url = file_info.get("url_private_download") or file_info.get("url_private")
        token = os.getenv("CONTACT_FINDER_SLACK_BOT_TOKEN")
        if not token:
            client.chat_postMessage(
                channel=channel_id,
                text="Bot misconfiguration: `CONTACT_FINDER_SLACK_BOT_TOKEN` is not set. Contact the bot admin.",
            )
            return
        print(f"[file_shared] url={url}")
        resp = req.get(url, headers={"Authorization": f"Bearer {token}"}, allow_redirects=True)
        print(f"[file_shared] status={resp.status_code} content-type={resp.headers.get('content-type')}")
        resp.raise_for_status()
        content = resp.content
        if "html" in resp.headers.get("content-type", ""):
            client.chat_postMessage(
                channel=channel_id,
                text=f"Could not download the file (Slack returned HTML). Ensure the bot token has `files:read` scope.",
            )
            return
        companies, raw_headers = parse_companies_file(content, filename)
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text=f"Could not read the file: {e}")
        return

    if not companies:
        client.chat_postMessage(channel=channel_id, text=(
            f"The file doesn't look right. Here are the column headers I found:\n"
            f"`{raw_headers}`\n\n"
            "I need columns for: company name, domain, and a Firmable company URL or ID."
        ))
        return

    sessions[user_id]["companies"] = companies
    _save_sessions()

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
    _save_sessions()
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
            _save_sessions()

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
    channel = body["user"]["id"]  # fallback: DM the user if channel unknown

    list_name = body["view"]["state"]["values"]["list_name_block"]["list_name_input"]["value"].strip()

    if not list_name:
        return

    if user_id not in sessions:
        client.chat_postMessage(
            channel=channel,
            text="Session expired — the bot was restarted. Please run `/find-contacts` and upload your file again.",
        )
        return

    sessions[user_id]["list_name"] = list_name
    _save_sessions()
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
            _save_sessions()

            client.chat_update(
                channel=channel,
                ts=msg_ts,
                text=f"HubSpot preview for *{list_name}*",
                blocks=_preview_blocks(list_name, preview, user_id),
            )
        except Exception as e:
            import traceback
            client.chat_update(
                channel=channel,
                ts=msg_ts,
                text=f"Error checking HubSpot: {e}\n```{traceback.format_exc()}```",
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
            _save_sessions()
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
    _save_sessions()
    client.chat_postMessage(
        channel=channel,
        text="Cancelled. Nothing was written to HubSpot.\nRun `/find-contacts` to start a new search.",
    )


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("CONTACT_FINDER_SLACK_APP_TOKEN"))
    print("Contact Finder bot is running. Press Ctrl+C to stop.")
    handler.start()
