"""
Event Outbound Slack Bot.

Slash command: /event-contacts
Flow:
  /event-contacts → URL modal → scrape sponsors → confirm →
  fetch sales team sizes → set threshold modal → filter + confirm →
  find contacts → post CSV

Environment variables required:
    EVENT_BOT_SLACK_BOT_TOKEN
    EVENT_BOT_SLACK_APP_TOKEN
    FIRMABLE_API_KEY
    FIRMABLE_OS_API_KEY
    FIRECRAWL_API_KEY  (optional — skips LinkedIn resolution if missing)

Run locally:
    PYTHONPATH=. python3 workflows/event_outbound/bot.py

Railway start command:
    python workflows/event_outbound/bot.py

Note: Playwright chromium must be installed in the environment:
    playwright install chromium
"""

import importlib.util
import io
import csv
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from playwright.sync_api import sync_playwright

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from utils.firmable import FirmableClient  # noqa: E402

load_dotenv()


# ---------------------------------------------------------------------------
# Import helper modules that have numeric prefixes (can't use regular import)
# ---------------------------------------------------------------------------

def _load_module(name: str, relpath: str):
    path = Path(__file__).parent / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_scrape = _load_module("scrape_exhibitors", "0_scrape_exhibitors.py")
_ctcts  = _load_module("find_contacts",     "1_find_contacts.py")

find_exhibitor_url        = _scrape.find_exhibitor_url
scrape_listing_page       = _scrape.scrape_listing_page
resolve_missing_linkedin  = _scrape.resolve_missing_linkedin
enrich_with_firmable      = _scrape.enrich_with_firmable
find_contacts_for_company = _ctcts.find_contacts_for_company


# ---------------------------------------------------------------------------
# Slack app + session store
# ---------------------------------------------------------------------------

app = App(token=os.environ["EVENT_BOT_SLACK_BOT_TOKEN"])

# In-memory sessions keyed by user_id
sessions: dict = {}


# ---------------------------------------------------------------------------
# Slack helpers
# ---------------------------------------------------------------------------

def _post(client, channel: str, text: str, blocks=None) -> str:
    """Post a new message; return its ts."""
    resp = client.chat_postMessage(channel=channel, text=text, blocks=blocks or [])
    return resp["ts"]


def _update(client, channel: str, ts: str, text: str, blocks=None):
    kwargs = {"channel": channel, "ts": ts, "text": text}
    if blocks is not None:
        kwargs["blocks"] = blocks
    client.chat_update(**kwargs)


def _action_buttons(yes_id: str, no_id: str, value: str,
                    yes_label: str = "Yes, proceed", no_label: str = "Cancel") -> list:
    return [{
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": yes_label},
                "style": "primary",
                "action_id": yes_id,
                "value": value,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": no_label},
                "style": "danger",
                "action_id": no_id,
                "value": value,
            },
        ],
    }]


# ---------------------------------------------------------------------------
# Sales team size helpers
# ---------------------------------------------------------------------------

RANGES = ["0–4", "5–9", "10–24", "25+"]


def _range_label(total) -> str:
    if total is None or total <= 4:
        return "0–4"
    if total <= 9:
        return "5–9"
    if total <= 24:
        return "10–24"
    return "25+"


def _distribution(exhibitors: list, sizes: dict) -> dict:
    """Return {range_label: [company_name, ...]} for all exhibitors."""
    dist = {r: [] for r in RANGES}
    for ex in exhibitors:
        cid = ex.get("firmable_company_id", "")
        total = sizes.get(cid, {}).get("total_sales_team_size")
        dist[_range_label(total)].append(ex["company_name"])
    return dist


def _total_for(ex: dict, sizes: dict) -> int:
    cid = ex.get("firmable_company_id", "")
    return sizes.get(cid, {}).get("total_sales_team_size") or 0


# ---------------------------------------------------------------------------
# Phase 1: /event-contacts → open URL modal
# ---------------------------------------------------------------------------

@app.command("/event-contacts")
def handle_slash(ack, body, client):
    ack()
    user_id = body["user_id"]
    sessions.pop(user_id, None)
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "event_url_modal",
            "private_metadata": body["channel_id"],
            "title": {"type": "plain_text", "text": "Event Contacts"},
            "submit": {"type": "plain_text", "text": "Start"},
            "close":  {"type": "plain_text", "text": "Cancel"},
            "blocks": [{
                "type": "input",
                "block_id": "url_block",
                "label": {"type": "plain_text", "text": "Conference website URL"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "url_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "https://example-conference.com",
                    },
                },
            }],
        },
    )


# ---------------------------------------------------------------------------
# Phase 2: URL modal submit → start scrape in background
# ---------------------------------------------------------------------------

@app.view("event_url_modal")
def handle_url_modal(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    url = body["view"]["state"]["values"]["url_block"]["url_input"]["value"].strip()
    channel = body["view"]["private_metadata"]

    sessions[user_id] = {"channel": channel}
    msg_ts = _post(client, channel,
                   f":mag: Scraping sponsors from {url}…\n_This may take 1–2 minutes._")
    sessions[user_id]["msg_ts"] = msg_ts

    threading.Thread(
        target=_scrape_thread,
        args=(user_id, url, client, channel, msg_ts),
        daemon=True,
    ).start()


def _scrape_thread(user_id: str, url: str, client, channel: str, msg_ts: str):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ))
            page = ctx.new_page()
            listing_url = find_exhibitor_url(page, url)
            exhibitors = scrape_listing_page(page, listing_url)
            browser.close()

        exhibitors = resolve_missing_linkedin(exhibitors)
        exhibitors = enrich_with_firmable(exhibitors)

        if user_id not in sessions:
            return  # cancelled

        if not exhibitors:
            _update(client, channel, msg_ts,
                    f":warning: No sponsors found at {url}.\n"
                    "The page format may not be supported.")
            sessions.pop(user_id, None)
            return

        sessions[user_id]["exhibitors"] = exhibitors

        names = "\n".join(f"• {ex['company_name']}" for ex in exhibitors)
        text = f":white_check_mark: Found *{len(exhibitors)} sponsors* from {url}:\n{names}"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn",
             "text": "Proceed to fetch sales team sizes for all companies?"}},
        ] + _action_buttons(
            "proceed_to_sizes", "cancel_session", user_id,
            yes_label=":bar_chart: Yes, fetch sales team sizes",
        )
        _update(client, channel, msg_ts, text, blocks=blocks)

    except Exception:
        tb = traceback.format_exc()
        _update(client, channel, msg_ts,
                f":x: Scrape failed.\n```{tb[-800:]}```")
        sessions.pop(user_id, None)


# ---------------------------------------------------------------------------
# Phase 3: Proceed to sizes → fetch in background
# ---------------------------------------------------------------------------

@app.action("proceed_to_sizes")
def handle_proceed_to_sizes(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    if user_id not in sessions:
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text=":warning: Session expired. Run `/event-contacts` to start again.",
        )
        return

    channel = sessions[user_id]["channel"]
    msg_ts = _post(client, channel,
                   ":bar_chart: Fetching sales team sizes for all companies…")

    threading.Thread(
        target=_sizes_thread,
        args=(user_id, client, channel, msg_ts),
        daemon=True,
    ).start()


def _sizes_thread(user_id: str, client, channel: str, msg_ts: str):
    try:
        if user_id not in sessions:
            return
        exhibitors = sessions[user_id]["exhibitors"]
        firmable = FirmableClient()
        sizes: dict = {}
        _empty = {"au_sales_team_size": None, "nz_sales_team_size": None,
                  "sea_sales_team_size": None, "total_sales_team_size": None}

        for ex in exhibitors:
            cid = ex.get("firmable_company_id", "")
            if not cid:
                sizes[cid] = dict(_empty)
                continue
            try:
                sizes[cid] = firmable.get_sales_team_size(cid)
            except Exception as e:
                print(f"  [size-error] {ex['company_name']}: {e}")
                sizes[cid] = dict(_empty)

        if user_id not in sessions:
            return
        sessions[user_id]["sizes"] = sizes

        dist = _distribution(exhibitors, sizes)
        lines = [f":bar_chart: *Sales team size breakdown* ({len(exhibitors)} companies total):"]
        for rng in RANGES:
            companies = dist[rng]
            if not companies:
                continue
            label = "company" if len(companies) == 1 else "companies"
            names_str = ", ".join(companies)
            lines.append(f"  • *{rng}:*  {len(companies)} {label} — {names_str}")

        dist_text = "\n".join(lines)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": dist_text}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn",
             "text": "What is the *minimum* total sales team size to include? (0 = all)"}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Set minimum threshold"},
                        "style": "primary",
                        "action_id": "open_threshold_modal",
                        "value": user_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "style": "danger",
                        "action_id": "cancel_session",
                        "value": user_id,
                    },
                ],
            },
        ]
        _update(client, channel, msg_ts, dist_text, blocks=blocks)

    except Exception:
        tb = traceback.format_exc()
        _update(client, channel, msg_ts,
                f":x: Failed to fetch sales team sizes.\n```{tb[-800:]}```")
        sessions.pop(user_id, None)


# ---------------------------------------------------------------------------
# Phase 4: Open threshold modal
# ---------------------------------------------------------------------------

@app.action("open_threshold_modal")
def handle_open_threshold_modal(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    if user_id not in sessions:
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text=":warning: Session expired. Run `/event-contacts` to start again.",
        )
        return

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "threshold_modal",
            "private_metadata": user_id,
            "title": {"type": "plain_text", "text": "Set Threshold"},
            "submit": {"type": "plain_text", "text": "Apply"},
            "close":  {"type": "plain_text", "text": "Cancel"},
            "blocks": [{
                "type": "input",
                "block_id": "threshold_block",
                "label": {"type": "plain_text", "text": "Minimum total sales team size"},
                "hint": {"type": "plain_text", "text": "Enter 0 to include all companies"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "threshold_input",
                    "placeholder": {"type": "plain_text", "text": "e.g. 5"},
                    "initial_value": "0",
                },
            }],
        },
    )


# ---------------------------------------------------------------------------
# Phase 5: Threshold modal submit → filter companies + confirm
# ---------------------------------------------------------------------------

@app.view("threshold_modal")
def handle_threshold_modal(ack, body, client):
    raw = body["view"]["state"]["values"]["threshold_block"]["threshold_input"]["value"].strip()

    if not raw.isdigit():
        ack(response_action="errors",
            errors={"threshold_block": "Please enter a whole number (0 or more)."})
        return

    ack()
    user_id = body["view"]["private_metadata"]
    threshold = int(raw)

    if user_id not in sessions:
        return  # session expired between modal open and submit

    channel   = sessions[user_id]["channel"]
    exhibitors = sessions[user_id]["exhibitors"]
    sizes      = sessions[user_id]["sizes"]
    sessions[user_id]["threshold"] = threshold

    if threshold > 0:
        qualifying = [ex for ex in exhibitors if _total_for(ex, sizes) >= threshold]
        skipped    = [ex for ex in exhibitors if _total_for(ex, sizes) <  threshold]
    else:
        qualifying = list(exhibitors)
        skipped    = []

    sessions[user_id]["qualifying"] = qualifying

    if not qualifying:
        _post(client, channel,
              f":warning: No companies meet a minimum of {threshold}. "
              "Run `/event-contacts` to try again with a lower threshold.")
        sessions.pop(user_id, None)
        return

    lines = [f":white_check_mark: *Including {len(qualifying)} companies* "
             f"(total sales team ≥ {threshold}):"]
    for ex in qualifying:
        lines.append(f"  • {ex['company_name']} (total={_total_for(ex, sizes)})")

    if skipped:
        lines.append(f"\n:x: *Skipping {len(skipped)} companies* below threshold:")
        for ex in skipped:
            lines.append(f"  • {ex['company_name']} (total={_total_for(ex, sizes)})")

    text = "\n".join(lines)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"Find contacts for these *{len(qualifying)} companies*?"}},
    ] + _action_buttons(
        "proceed_to_contacts", "cancel_session", user_id,
        yes_label=":busts_in_silhouette: Yes, find contacts",
    )
    _post(client, channel, text, blocks=blocks)


# ---------------------------------------------------------------------------
# Phase 6: Find contacts in background → post CSV
# ---------------------------------------------------------------------------

@app.action("proceed_to_contacts")
def handle_proceed_to_contacts(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    if user_id not in sessions:
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text=":warning: Session expired. Run `/event-contacts` to start again.",
        )
        return

    channel = sessions[user_id]["channel"]
    msg_ts = _post(client, channel,
                   ":busts_in_silhouette: Finding contacts… this may take a few minutes.")

    threading.Thread(
        target=_contacts_thread,
        args=(user_id, client, channel, msg_ts),
        daemon=True,
    ).start()


def _contacts_thread(user_id: str, client, channel: str, msg_ts: str):
    try:
        if user_id not in sessions:
            return
        qualifying = sessions[user_id]["qualifying"]
        sizes      = sessions[user_id]["sizes"]
        firmable   = FirmableClient()

        all_contacts: list = []
        _empty_sizes = {"au_sales_team_size": None, "nz_sales_team_size": None,
                        "sea_sales_team_size": None, "total_sales_team_size": None}

        for ex in qualifying:
            try:
                rows = find_contacts_for_company(firmable, ex)
                cid = ex.get("firmable_company_id", "")
                size_data = sizes.get(cid, dict(_empty_sizes))
                for row in rows:
                    row.update(size_data)
                all_contacts.extend(rows)
            except Exception as e:
                print(f"  [contacts-error] {ex['company_name']}: {e}")

        if user_id not in sessions:
            return

        total      = len(all_contacts)
        with_both  = sum(1 for r in all_contacts if r.get("work_email") and r.get("phone"))
        phone_only = sum(1 for r in all_contacts if r.get("phone") and not r.get("work_email"))
        email_only = sum(1 for r in all_contacts if r.get("work_email") and not r.get("phone"))

        summary = (
            f":white_check_mark: *Found {total} contacts* "
            f"across {len(qualifying)} companies:\n"
            f"  • phone + email: {with_both}\n"
            f"  • phone only:    {phone_only}\n"
            f"  • email only:    {email_only}"
        )
        _update(client, channel, msg_ts, summary)

        if all_contacts:
            fieldnames = [
                "first_name", "last_name", "full_name", "person_id", "position",
                "work_email", "phone", "linkedin_url", "company_name", "domain",
                "firmable_company_id",
                "au_sales_team_size", "nz_sales_team_size",
                "sea_sales_team_size", "total_sales_team_size",
            ]
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_contacts)

            filename = f"event_contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            client.files_upload_v2(
                channel=channel,
                content=buf.getvalue(),
                filename=filename,
                title=f"Event Contacts — {total} rows",
            )

        sessions.pop(user_id, None)

    except Exception:
        tb = traceback.format_exc()
        _update(client, channel, msg_ts,
                f":x: Contact search failed.\n```{tb[-800:]}```")
        sessions.pop(user_id, None)


# ---------------------------------------------------------------------------
# Cancel — shared by all stages
# ---------------------------------------------------------------------------

@app.action("cancel_session")
def handle_cancel(ack, body, client):
    ack()
    user_id = body["actions"][0]["value"]
    sessions.pop(user_id, None)
    client.chat_postMessage(
        channel=body["channel"]["id"],
        text=":no_entry: Cancelled. Run `/event-contacts` to start a new search.",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["EVENT_BOT_SLACK_APP_TOKEN"])
    print("Event Outbound Bot is running (Socket Mode)…")
    handler.start()
