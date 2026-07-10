"""
SmartLead domain reply rate analysis.

For every sending domain across all mailboxes, shows:
  - Number of mailboxes on that domain
  - Number of active campaigns currently using this domain/mailbox
  - Replies received in the past 14 days

A domain or mailbox is only flagged when it IS in an active campaign
and receiving no replies in the past 14 days. Inactive domains with
zero replies are expected and are not flagged.

Run from repo root:
    PYTHONPATH=. python3 scripts/smartlead_domain_reply_analysis.py
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from scripts.smartlead_client import SmartLeadClient

LOOKBACK_DAYS = 14


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_email(account: dict) -> str:
    """Return the sending email address from an email account object."""
    for field in ("from_email", "username", "email", "smtp_username"):
        val = account.get(field, "")
        if val and "@" in val:
            return val.strip().lower()
    return ""


def _extract_vendor(tags: list) -> str:
    """Infer vendor from SmartLead account tags. Returns 'InboxKit', 'ScaledMail', or ''."""
    if not tags:
        return ""
    names = [t.get("tag_name", "") for t in tags]
    for name in names:
        if name == "InboxKit":
            return "InboxKit"
    for name in names:
        if name == "ScaledMail":
            return "ScaledMail"
    for name in names:
        if name.startswith("InboxKit"):
            return "InboxKit"
    for name in names:
        if name.startswith("ScaledMail"):
            return "ScaledMail"
    return ""


def build_account_domain_map(client: SmartLeadClient) -> tuple:
    """
    Paginate all email accounts.
    Returns:
      - id_to_domain: {account_id: domain}
      - id_to_email: {account_id: full_email_address}
      - id_to_vendor: {account_id: 'InboxKit' | 'ScaledMail' | ''}
      - domain_to_esp: {domain: 'Google' | 'Microsoft' | 'Other'}
    """
    id_to_domain = {}
    id_to_email = {}
    id_to_vendor = {}
    domain_type_votes = defaultdict(lambda: defaultdict(int))
    offset = 0
    while True:
        page = client.get_email_accounts(limit=100, offset=offset)
        if not page:
            break
        for acc in page:
            email = _extract_email(acc)
            domain = email.split("@")[-1] if email else f"unknown-{acc['id']}"
            id_to_domain[acc["id"]] = domain
            id_to_email[acc["id"]] = email or f"unknown-{acc['id']}"
            id_to_vendor[acc["id"]] = _extract_vendor(acc.get("tags") or [])
            acc_type = acc.get("type", "").upper()
            if acc_type == "GMAIL":
                domain_type_votes[domain]["Google"] += 1
            elif acc_type == "OUTLOOK":
                domain_type_votes[domain]["Microsoft"] += 1
            else:
                domain_type_votes[domain]["Other"] += 1
        if len(page) < 100:
            break
        offset += 100

    domain_to_esp = {
        domain: max(votes, key=votes.get)
        for domain, votes in domain_type_votes.items()
    }
    return id_to_domain, id_to_email, id_to_vendor, domain_to_esp


def fetch_active_campaigns_per_account(client: SmartLeadClient, campaigns: list) -> tuple:
    """
    For each campaign with status ACTIVE, get the email accounts assigned to it.
    Returns:
      - account_active_count: {account_id: int} — how many active campaigns this account is in
      - total_active: int — number of active campaigns found
    """
    account_active_count = defaultdict(int)
    active = [c for c in campaigns if c.get("status") == "ACTIVE"]

    print(f"  {len(active)} active campaigns (of {len(campaigns)} total)")

    for i, camp in enumerate(active, 1):
        camp_id = str(camp["id"])
        camp_name = camp.get("name", camp_id)
        print(f"  [{i}/{len(active)}] {camp_name}", end="\r", flush=True)

        try:
            camp_accounts = client._get(f"/campaigns/{camp_id}/email-accounts")
        except Exception:
            continue

        for acc in (camp_accounts or []):
            acc_id = acc.get("id")
            if acc_id:
                account_active_count[acc_id] += 1

    if active:
        print()  # newline after \r progress

    return dict(account_active_count), len(active)


def _get_inbox_replies_with_retry(client, offset, limit, start_iso, end_iso, max_retries=5):
    """Call get_inbox_replies with exponential backoff on 429."""
    delay = 2
    for attempt in range(max_retries):
        try:
            return client.get_inbox_replies(offset=offset, limit=limit,
                                            start_date=start_iso, end_date=end_iso)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429 and attempt < max_retries - 1:
                print(f"\n  Rate limited — waiting {delay}s before retry...", flush=True)
                time.sleep(delay)
                delay *= 2
            else:
                raise
    return {"data": []}


def fetch_replies_per_account(client: SmartLeadClient, start_iso: str, end_iso: str) -> dict:
    """
    Paginate master inbox replies for the given date window.
    Returns {account_id: reply_count}.
    """
    account_replies = defaultdict(int)
    offset = 0
    limit = 20
    total = 0
    while True:
        result = _get_inbox_replies_with_retry(client, offset, limit, start_iso, end_iso)
        batch = result.get("data", [])
        for record in batch:
            acc_id = record.get("email_account_id")
            if acc_id:
                account_replies[acc_id] += 1
        total += len(batch)
        print(f"  Fetched {total} replies...", end="\r", flush=True)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.5)
    print()
    return dict(account_replies)


def aggregate_by_domain(
    account_to_domain: dict,
    domain_to_esp: dict,
    account_active_count: dict,
    account_replies: dict,
) -> list:
    """Aggregate active campaign count + replies by domain."""
    domain_mailboxes = defaultdict(set)
    for acc_id, domain in account_to_domain.items():
        domain_mailboxes[domain].add(acc_id)

    rows = []
    for domain, acc_ids in domain_mailboxes.items():
        active_campaigns = sum(account_active_count.get(a, 0) for a in acc_ids)
        replies = sum(account_replies.get(a, 0) for a in acc_ids)
        rows.append({
            "domain": domain,
            "esp": domain_to_esp.get(domain, "Other"),
            "mailboxes": len(acc_ids),
            "active_campaigns": active_campaigns,
            "replies_14d": replies,
            "is_active": active_campaigns > 0,
        })

    # Sort: active + no replies first (most urgent), then active + replies, then inactive
    rows.sort(key=lambda r: (
        0 if (r["is_active"] and r["replies_14d"] == 0) else
        1 if r["is_active"] else 2,
        -r["replies_14d"]
    ))
    return rows


def _status_class(is_active: bool, replies: int) -> str:
    if not is_active:
        return "status-inactive"
    if replies == 0:
        return "status-alert"
    return "status-ok"


def print_table(rows: list, lookback_days: int):
    """Print domain stats as a terminal table."""
    col_domain = max(len(r["domain"]) for r in rows) if rows else 20
    col_domain = max(col_domain, 6)
    col_esp = 11

    total_width = col_domain + col_esp + 12 + 18 + 12 + 18
    divider = "=" * total_width

    print(f"\n{divider}")
    print(f"  DOMAIN HEALTH REPORT  —  Replies: last {lookback_days} days")
    print(f"{divider}")

    header = (
        f"  {'Domain':<{col_domain}}"
        f"  {'ESP':<{col_esp}}"
        f"  {'Mailboxes':>9}"
        f"  {'Active Campaigns':>16}"
        f"  {'Replies (14d)':>13}"
        f"  Status"
    )
    print(header)
    print(f"  {'-' * (total_width - 2)}")

    for r in rows:
        is_active = r["is_active"]
        replies = r["replies_14d"]

        if not is_active:
            status = "Inactive"
        elif replies == 0:
            status = "⚠ No replies"
        else:
            status = "Active"

        print(
            f"  {r['domain']:<{col_domain}}"
            f"  {r['esp']:<{col_esp}}"
            f"  {r['mailboxes']:>9}"
            f"  {r['active_campaigns']:>16}"
            f"  {replies:>13}"
            f"  {status}"
        )

    print(f"{divider}")

    active_no_replies = [r for r in rows if r["is_active"] and r["replies_14d"] == 0]
    active_ok = [r for r in rows if r["is_active"] and r["replies_14d"] > 0]
    inactive = [r for r in rows if not r["is_active"]]
    print(f"  Active, getting replies: {len(active_ok)} domain(s)")
    print(f"  Active, NO replies (action needed): {len(active_no_replies)} domain(s)")
    print(f"  Inactive (not in use): {len(inactive)} domain(s)")
    print(f"{divider}\n")


def print_mailbox_table(
    account_to_domain: dict,
    id_to_email: dict,
    domain_to_esp: dict,
    account_active_count: dict,
    account_replies: dict,
    domain_rows: list,
    lookback_days: int,
):
    """Print per-mailbox breakdown grouped by domain, ordered to match domain_rows."""
    col_email = max(len(e) for e in id_to_email.values()) if id_to_email else 30
    col_email = max(col_email, 10)

    total_width = col_email + 10 + 18 + 13 + 16
    divider = "=" * total_width

    print(f"\n{divider}")
    print(f"  MAILBOX BREAKDOWN  —  Replies: last {lookback_days} days")
    print(f"{divider}")

    domain_to_acc_ids = defaultdict(list)
    for acc_id, domain in account_to_domain.items():
        domain_to_acc_ids[domain].append(acc_id)

    for dr in domain_rows:
        domain = dr["domain"]
        esp = domain_to_esp.get(domain, "Other")
        acc_ids = domain_to_acc_ids.get(domain, [])

        def mailbox_sort_key(acc_id):
            active = account_active_count.get(acc_id, 0)
            replies = account_replies.get(acc_id, 0)
            # Active + no replies first, then active + replies, then inactive
            if active > 0 and replies == 0:
                return (0, -active)
            elif active > 0:
                return (1, -replies)
            else:
                return (2, -replies)

        acc_ids_sorted = sorted(acc_ids, key=mailbox_sort_key)

        print(f"\n  {domain}  ({esp})")
        print(
            f"  {'Mailbox':<{col_email}}"
            f"  {'Active Campaigns':>16}"
            f"  {'Replies (14d)':>13}"
            f"  Status"
        )
        print(f"  {'-' * (total_width - 2)}")

        for acc_id in acc_ids_sorted:
            email = id_to_email.get(acc_id, str(acc_id))
            active = account_active_count.get(acc_id, 0)
            replies = account_replies.get(acc_id, 0)

            if active == 0:
                status = "Inactive"
            elif replies == 0:
                status = "⚠ No replies"
            else:
                status = "Active"

            print(
                f"  {email:<{col_email}}"
                f"  {active:>16}"
                f"  {replies:>13}"
                f"  {status}"
            )

    print(f"\n{divider}\n")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def write_html_report(
    rows: list,
    account_to_domain: dict,
    id_to_email: dict,
    id_to_vendor: dict,
    domain_to_esp: dict,
    account_active_count: dict,
    account_replies: dict,
    lookback_days: int,
    total_active_campaigns: int,
    output_path: str,
    generated_at: str,
):
    active_alert = [r for r in rows if r["is_active"] and r["replies_14d"] == 0]
    active_ok    = [r for r in rows if r["is_active"] and r["replies_14d"] > 0]
    inactive     = [r for r in rows if not r["is_active"]]

    domain_to_acc_ids = defaultdict(list)
    for acc_id, domain in account_to_domain.items():
        domain_to_acc_ids[domain].append(acc_id)

    all_vendors = sorted(set(v for v in id_to_vendor.values() if v))

    def mailbox_rows_html(domain):
        acc_ids = domain_to_acc_ids.get(domain, [])
        def sort_key(a):
            active = account_active_count.get(a, 0)
            replies = account_replies.get(a, 0)
            if active > 0 and replies == 0:
                return (0, -active)
            elif active > 0:
                return (1, -replies)
            else:
                return (2, -replies)
        acc_ids = sorted(acc_ids, key=sort_key)
        html = []
        for acc_id in acc_ids:
            email = id_to_email.get(acc_id, str(acc_id))
            vendor = id_to_vendor.get(acc_id, "")
            active = account_active_count.get(acc_id, 0)
            replies = account_replies.get(acc_id, 0)
            sc = _status_class(active > 0, replies)
            if active == 0:
                status_html = '<span class="status-badge status-inactive">Inactive</span>'
            elif replies == 0:
                status_html = '<span class="status-badge status-alert">No replies</span>'
            else:
                status_html = '<span class="status-badge status-ok">Active</span>'
            vendor_slug = vendor.lower().replace(" ", "-") if vendor else "unknown"
            vendor_html = (
                f'<span class="vendor-badge vendor-{vendor_slug}">{vendor}</span>'
                if vendor else
                '<span class="vendor-badge vendor-unknown">—</span>'
            )
            html.append(
                f'<tr data-vendor="{vendor_slug}">'
                f'<td class="mono col-email">{email}</td>'
                f'<td>{vendor_html}</td>'
                f'<td class="mono num">{active}</td>'
                f'<td class="mono num">{replies}</td>'
                f'<td>{status_html}</td>'
                f'</tr>'
            )
        return "\n".join(html)

    domain_rows_html = []
    for r in rows:
        sc = _status_class(r["is_active"], r["replies_14d"])
        if not r["is_active"]:
            status_html = '<span class="status-badge status-inactive">Inactive</span>'
        elif r["replies_14d"] == 0:
            status_html = '<span class="status-badge status-alert">Active · No replies</span>'
        else:
            status_html = '<span class="status-badge status-ok">Active</span>'
        domain_rows_html.append(
            f'<tr data-esp="{r["esp"]}" data-active="{1 if r["is_active"] else 0}">'
            f'<td class="mono col-domain">{r["domain"]}</td>'
            f'<td><span class="esp-badge esp-{r["esp"].lower()}">{r["esp"]}</span></td>'
            f'<td class="mono num">{r["mailboxes"]}</td>'
            f'<td class="mono num">{r["active_campaigns"]}</td>'
            f'<td class="mono num">{r["replies_14d"]}</td>'
            f'<td>{status_html}</td>'
            f'</tr>'
        )

    vendor_filter_btns = "".join(
        f'<button class="filter-btn" onclick="filterMailboxes(\'{v.lower().replace(" ", "-")}\', this)">{v}</button>'
        for v in all_vendors
    )

    mailbox_sections_html = []
    for r in rows:
        domain = r["domain"]
        esp    = domain_to_esp.get(domain, "Other")
        sc = _status_class(r["is_active"], r["replies_14d"])
        if not r["is_active"]:
            pill_text = "Inactive"
            pill_class = "rate-none"
        elif r["replies_14d"] == 0:
            pill_text = "Active · No replies"
            pill_class = "rate-low"
        else:
            pill_text = f"Active · {r['replies_14d']} repl{'ies' if r['replies_14d'] != 1 else 'y'}"
            pill_class = "rate-good"
        domain_vendors = " ".join(sorted(set(
            (id_to_vendor.get(a, "") or "unknown").lower().replace(" ", "-")
            for a in domain_to_acc_ids.get(domain, [])
        )))
        active_count_display = f'{r["active_campaigns"]} campaign{"s" if r["active_campaigns"] != 1 else ""}' if r["is_active"] else "Inactive"
        mailbox_sections_html.append(f"""
        <details class="domain-group" data-vendors="{domain_vendors}" data-active="{1 if r['is_active'] else 0}">
          <summary class="domain-group-header">
            <span class="mono dg-domain">{domain}</span>
            <span class="esp-badge esp-{esp.lower()}">{esp}</span>
            <span class="dg-meta">{r["mailboxes"]} mailbox{"es" if r["mailboxes"] != 1 else ""}</span>
            <span class="dg-meta">{active_count_display}</span>
            <span class="rate-pill {pill_class}">{pill_text}</span>
          </summary>
          <div class="domain-group-body">
            <table class="mailbox-table">
              <thead>
                <tr>
                  <th>Mailbox</th>
                  <th>Vendor</th>
                  <th class="num">Active Campaigns</th>
                  <th class="num">Replies (14d)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {mailbox_rows_html(domain)}
              </tbody>
            </table>
          </div>
        </details>""")

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Firmable Domain Health Report</title>
<style>
  :root {{
    --ground:    #F8FAFC;
    --surface:   #FFFFFF;
    --surface-2: #F1F5F9;
    --surface-3: #E4ECF5;
    --border:    #D0DCE8;
    --text:      #0F1929;
    --text-2:    #3D5470;
    --text-3:    #7A94B0;
    --accent:    #C46A00;
    --teal:      #0A8F6A;
    --danger:    #C0292E;
    --mono: ui-monospace,'SF Mono','Cascadia Code','Consolas',monospace;
    --sans: system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  }}
  *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--ground); color:var(--text); font-family:var(--sans);
          font-size:15px; line-height:1.6; -webkit-font-smoothing:antialiased; }}
  .report {{ max-width:960px; margin:0 auto; padding:48px 24px 96px; }}

  /* Header */
  .report-header {{ border-bottom:1px solid var(--border); padding-bottom:36px; margin-bottom:56px; }}
  .header-meta {{ display:flex; flex-wrap:wrap; gap:0; margin-bottom:20px; }}
  .header-meta .tag {{ font-family:var(--mono); font-size:10px; letter-spacing:.12em;
    text-transform:uppercase; color:var(--text-3); padding:4px 12px;
    border:1px solid var(--border); border-right:none; }}
  .header-meta .tag:last-child {{ border-right:1px solid var(--border); }}
  .report-header h1 {{ font-family:var(--mono); font-size:clamp(22px,4vw,32px);
    font-weight:700; line-height:1.2; letter-spacing:-.02em; margin-bottom:10px; }}
  .header-sub {{ font-family:var(--mono); font-size:12px; color:var(--text-3); letter-spacing:.04em; }}

  /* Hero */
  .hero-contrast {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center;
    gap:24px; background:var(--surface); border:1px solid var(--border); border-radius:4px;
    padding:48px 40px; margin-bottom:72px; }}
  .hero-stat {{ text-align:center; }}
  .hero-number {{ font-family:var(--mono); font-size:clamp(48px,9vw,80px); font-weight:700;
    line-height:1; letter-spacing:-.04em; display:block; margin-bottom:12px; }}
  .hero-number--pass {{ color:var(--teal); text-shadow:0 2px 12px rgba(10,143,106,.18); }}
  .hero-number--fail {{ color:var(--danger); text-shadow:0 2px 12px rgba(192,41,46,.18); }}
  .hero-number--neutral {{ color:var(--text-3); }}
  .hero-label {{ font-family:var(--mono); font-size:11px; letter-spacing:.1em;
    text-transform:uppercase; color:var(--text-2); margin-bottom:4px; }}
  .hero-sub {{ font-size:12px; color:var(--text-3); }}
  .hero-divider {{ font-family:var(--mono); font-size:13px; color:var(--text-3);
    letter-spacing:.1em; text-align:center; padding:0 8px; }}
  @media(max-width:520px) {{
    .hero-contrast {{ grid-template-columns:1fr; padding:32px 24px; }}
    .hero-divider {{ display:none; }}
  }}

  /* Sections */
  .section {{ margin-bottom:72px; }}
  .section-eyebrow {{ font-family:var(--mono); font-size:10px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--accent); margin-bottom:8px; }}
  .section > h2 {{ font-family:var(--mono); font-size:clamp(18px,3vw,24px); font-weight:700;
    letter-spacing:-.02em; margin-bottom:8px; }}
  .section > .section-desc {{ color:var(--text-2); font-size:13px; max-width:640px; margin-bottom:28px; }}

  /* ESP badges */
  .esp-badge {{ display:inline-block; font-family:var(--mono); font-size:10px;
    letter-spacing:.06em; padding:2px 7px; border-radius:2px; text-transform:uppercase; }}
  .esp-google    {{ background:#E8F5E9; color:#1B5E20; }}
  .esp-microsoft {{ background:#E3F2FD; color:#0D47A1; }}
  .esp-other     {{ background:var(--surface-2); color:var(--text-3); }}

  /* Status badges (inline in table cells) */
  .status-badge {{ display:inline-block; font-family:var(--mono); font-size:10px;
    letter-spacing:.06em; padding:2px 8px; border-radius:3px; white-space:nowrap; }}
  .status-ok       {{ background:#E8F5E9; color:#1B5E20; }}
  .status-alert    {{ background:#FFEBEE; color:#B71C1C; font-weight:600; }}
  .status-inactive {{ background:var(--surface-2); color:var(--text-3); }}

  /* Domain summary table */
  .scroll-wrap {{ overflow-x:auto; }}
  .domain-table {{ width:100%; border-collapse:collapse; font-size:13px;
    font-variant-numeric:tabular-nums; min-width:600px; }}
  .domain-table th {{ font-family:var(--mono); font-size:10px; letter-spacing:.1em;
    text-transform:uppercase; color:var(--text-3); padding:10px 14px;
    text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }}
  .domain-table th.num {{ text-align:right; }}
  .domain-table td {{ padding:11px 14px; border-bottom:1px solid var(--border); vertical-align:middle; }}
  .domain-table tr:last-child td {{ border-bottom:none; }}
  .domain-table tr:hover td {{ background:var(--surface-2); }}
  .mono {{ font-family:var(--mono); }}
  .num  {{ text-align:right; }}
  .col-domain {{ font-size:13px; color:var(--text); }}
  .col-email  {{ font-size:12px; color:var(--text-2); }}

  /* Domain group (mailbox breakdown) */
  .domain-group {{ border:1px solid var(--border); border-radius:4px;
    margin-bottom:8px; overflow:hidden; background:var(--surface); }}
  .domain-group-header {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
    padding:12px 16px; cursor:pointer; list-style:none; user-select:none;
    border-bottom:1px solid transparent; }}
  .domain-group[open] .domain-group-header {{ border-bottom-color:var(--border);
    background:var(--surface-2); }}
  .domain-group-header::-webkit-details-marker {{ display:none; }}
  .domain-group-header::before {{ content:"›"; font-family:var(--mono); font-size:14px;
    color:var(--text-3); margin-right:2px; transition:transform .2s; }}
  .domain-group[open] .domain-group-header::before {{ transform:rotate(90deg); }}
  .dg-domain {{ font-size:13px; color:var(--text); flex:1; min-width:0;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .dg-meta {{ font-size:12px; color:var(--text-3); white-space:nowrap; }}
  .rate-pill {{ font-size:11px; padding:2px 8px; border-radius:20px; font-family:var(--mono); }}
  .rate-good {{ background:#E8F5E9; color:#1B5E20; }}
  .rate-low  {{ background:#FFEBEE; color:#B71C1C; font-weight:600; }}
  .rate-none {{ background:var(--surface-2); color:var(--text-3); }}
  .domain-group-body {{ padding:0; }}

  /* Vendor badges */
  .vendor-badge {{ display:inline-block; font-family:var(--mono); font-size:10px;
    letter-spacing:.05em; padding:2px 7px; border-radius:2px; white-space:nowrap; }}
  .vendor-inboxkit   {{ background:#EDE9FE; color:#4C1D95; }}
  .vendor-scaledmail {{ background:#E0F2FE; color:#075985; }}
  .vendor-unknown    {{ background:var(--surface-2); color:var(--text-3); }}

  /* Filter bars */
  .filter-bar {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:20px; }}
  .filter-btn {{ font-family:var(--mono); font-size:11px; letter-spacing:.06em;
    text-transform:uppercase; padding:5px 12px; background:var(--surface);
    border:1px solid var(--border); border-radius:3px; color:var(--text-3);
    cursor:pointer; transition:all .15s; }}
  .filter-btn:hover {{ background:var(--surface-2); color:var(--text-2); }}
  .filter-btn.active {{ background:var(--text); color:var(--surface); border-color:var(--text); }}

  /* Mailbox inner table */
  .mailbox-table {{ width:100%; border-collapse:collapse; font-size:12px;
    font-variant-numeric:tabular-nums; }}
  .mailbox-table th {{ font-family:var(--mono); font-size:10px; letter-spacing:.08em;
    text-transform:uppercase; color:var(--text-3); padding:8px 16px;
    text-align:left; border-bottom:1px solid var(--border); background:var(--surface); }}
  .mailbox-table th.num {{ text-align:right; }}
  .mailbox-table td {{ padding:9px 16px; border-bottom:1px solid var(--border); }}
  .mailbox-table tr:last-child td {{ border-bottom:none; }}
  .mailbox-table tr:hover td {{ background:var(--surface-2); }}

  /* Mailbox section header row */
  .mailbox-section-header {{ display:flex; align-items:flex-start; justify-content:space-between;
    gap:16px; margin-bottom:0; }}
  .mailbox-section-header h2 {{ margin-bottom:8px; }}
  .mailbox-section-header .section-desc {{ margin-bottom:28px; }}

  /* Expand all button */
  .expand-btn {{ flex-shrink:0; margin-top:4px; font-family:var(--mono); font-size:11px;
    letter-spacing:.06em; text-transform:uppercase; padding:7px 14px;
    background:var(--surface); border:1px solid var(--border); border-radius:3px;
    color:var(--text-2); cursor:pointer; white-space:nowrap; transition:background .15s,color .15s; }}
  .expand-btn:hover {{ background:var(--surface-2); color:var(--text); }}

  /* Footer */
  .report-footer {{ border-top:1px solid var(--border); padding-top:24px; margin-top:24px;
    font-family:var(--mono); font-size:11px; color:var(--text-3); }}
</style>
</head>
<body>
<div class="report">

  <div class="report-header">
    <div class="header-meta">
      <span class="tag">Firmable</span>
      <span class="tag">Domain Health</span>
      <span class="tag">{total_active_campaigns} active campaigns</span>
      <span class="tag">{generated_at}</span>
    </div>
    <h1>Domain Health Report</h1>
    <div class="header-sub">Replies: last {lookback_days} days &nbsp;·&nbsp; Active = currently assigned to an active campaign</div>
  </div>

  <div class="hero-contrast">
    <div class="hero-stat">
      <span class="hero-number hero-number--pass">{len(active_ok)}</span>
      <div class="hero-label">Active &amp; getting replies</div>
      <div class="hero-sub">domains in live campaigns with replies</div>
    </div>
    <div class="hero-divider">vs</div>
    <div class="hero-stat">
      <span class="hero-number hero-number--fail">{len(active_alert)}</span>
      <div class="hero-label">Active, no replies</div>
      <div class="hero-sub">in live campaigns but silent — check these</div>
    </div>
  </div>

  <div class="section">
    <div class="section-eyebrow">Summary</div>
    <h2>By Domain</h2>
    <p class="section-desc">
      All {len(rows)} sending domains across {sum(len(v) for v in domain_to_acc_ids.values())} mailboxes.
      {len(inactive)} inactive (not in any active campaign). Sorted by urgency: active with no replies first.
    </p>
    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterDomains('all', this)">All</button>
      <button class="filter-btn" onclick="filterDomains('active', this)">Active only</button>
      <button class="filter-btn" onclick="filterDomains('Google', this)">Google</button>
      <button class="filter-btn" onclick="filterDomains('Microsoft', this)">Microsoft</button>
    </div>
    <div class="scroll-wrap">
      <table class="domain-table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>ESP</th>
            <th class="num">Mailboxes</th>
            <th class="num">Active Campaigns</th>
            <th class="num">Replies (14d)</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {''.join(domain_rows_html)}
        </tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-eyebrow">Detail</div>
    <div class="mailbox-section-header">
      <div>
        <h2>By Mailbox</h2>
        <p class="section-desc">Click a domain to expand individual mailbox stats. Sorted by urgency within each domain.</p>
      </div>
      <button class="expand-btn" id="expandAllBtn" onclick="toggleAll()">Expand all</button>
    </div>
    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterMailboxes('all', this)">All</button>
      <button class="filter-btn" onclick="filterMailboxes('active-only', this)">Active only</button>
      {vendor_filter_btns}
    </div>
    {''.join(mailbox_sections_html)}
  </div>

  <div class="report-footer">
    Generated {generated_at} &nbsp;·&nbsp; Replies window: last {lookback_days} days &nbsp;·&nbsp; {total_active_campaigns} active campaigns at time of report
  </div>

</div>
<script>
  function toggleAll() {{
    var btn = document.getElementById('expandAllBtn');
    var details = document.querySelectorAll('.domain-group:not([style*="display: none"])');
    var anyOpen = Array.from(details).some(function(d) {{ return d.open; }});
    details.forEach(function(d) {{ d.open = !anyOpen; }});
    btn.textContent = anyOpen ? 'Expand all' : 'Collapse all';
  }}

  function filterDomains(esp, btn) {{
    document.querySelectorAll('#domainFilterBar .filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    document.querySelectorAll('.domain-table tbody tr').forEach(function(row) {{
      var show = esp === 'all'
        || (esp === 'active' && row.dataset.active === '1')
        || row.dataset.esp === esp;
      row.style.display = show ? '' : 'none';
    }});
  }}

  function filterMailboxes(vendor, btn) {{
    document.querySelectorAll('#mailboxFilterBar .filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    document.querySelectorAll('.domain-group').forEach(function(group) {{
      if (vendor === 'active-only') {{
        var show = group.dataset.active === '1';
        group.style.display = show ? '' : 'none';
        return;
      }}
      var rows = group.querySelectorAll('.mailbox-table tbody tr');
      var visible = 0;
      rows.forEach(function(row) {{
        var show = vendor === 'all' || row.dataset.vendor === vendor;
        row.style.display = show ? '' : 'none';
        if (show) visible++;
      }});
      group.style.display = visible > 0 ? '' : 'none';
    }});
    var expandBtn = document.getElementById('expandAllBtn');
    if (expandBtn) expandBtn.textContent = 'Expand all';
  }}

  // Wire up filter bars by ID so the active-class logic is scoped correctly
  document.addEventListener('DOMContentLoaded', function() {{
    var filterBars = document.querySelectorAll('.filter-bar');
    if (filterBars[0]) filterBars[0].id = 'domainFilterBar';
    if (filterBars[1]) filterBars[1].id = 'mailboxFilterBar';

    // Re-wire domain filter buttons to use the scoped function
    if (filterBars[0]) {{
      filterBars[0].querySelectorAll('.filter-btn').forEach(function(btn) {{
        var orig = btn.getAttribute('onclick');
        btn.onclick = function() {{
          filterBars[0].querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          btn.classList.add('active');
          var m = orig.match(/filterDomains\('([^']+)'/);
          if (m) filterDomains(m[1], btn);
        }};
      }});
    }}
    if (filterBars[1]) {{
      filterBars[1].querySelectorAll('.filter-btn').forEach(function(btn) {{
        var orig = btn.getAttribute('onclick');
        btn.onclick = function() {{
          filterBars[1].querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          btn.classList.add('active');
          var m = orig.match(/filterMailboxes\('([^']+)'/);
          if (m) filterMailboxes(m[1], btn);
        }};
      }});
    }}
  }});
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML report written to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    client = SmartLeadClient()

    print("Loading email accounts...")
    account_to_domain, id_to_email, id_to_vendor, domain_to_esp = build_account_domain_map(client)
    domain_count = len(set(account_to_domain.values()))
    print(f"  {len(account_to_domain)} mailboxes across {domain_count} domains\n")

    print("Fetching active campaigns...")
    campaigns = client.list_campaigns()
    account_active_count, total_active_campaigns = fetch_active_campaigns_per_account(client, campaigns)

    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\nFetching replies: {start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}...")
    account_replies = fetch_replies_per_account(client, start_iso, end_iso)

    rows = aggregate_by_domain(account_to_domain, domain_to_esp, account_active_count, account_replies)
    print_table(rows, LOOKBACK_DAYS)
    print_mailbox_table(
        account_to_domain, id_to_email, domain_to_esp,
        account_active_count, account_replies, rows,
        LOOKBACK_DAYS,
    )

    import os
    os.makedirs("docs", exist_ok=True)
    write_html_report(
        rows=rows,
        account_to_domain=account_to_domain,
        id_to_email=id_to_email,
        id_to_vendor=id_to_vendor,
        domain_to_esp=domain_to_esp,
        account_active_count=account_active_count,
        account_replies=account_replies,
        lookback_days=LOOKBACK_DAYS,
        total_active_campaigns=total_active_campaigns,
        output_path="docs/domain-report.html",
        generated_at=now.strftime("%d %b %Y"),
    )


if __name__ == "__main__":
    main()
