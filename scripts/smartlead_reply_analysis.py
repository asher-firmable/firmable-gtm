"""
SmartLead reply analysis — 2D provider breakdown.

For every reply in the main inbox over the past 30 days, shows:
  - Which provider OUR sending inbox uses (Google / Microsoft)
  - Which provider the PROSPECT'S email uses (Google / Microsoft / Other)

Prospect provider is determined by MX record lookup on their email domain,
so it correctly identifies Google Workspace and Microsoft 365 on custom domains.
Results are cached per domain to avoid duplicate DNS queries.

Run from repo root:
    PYTHONPATH=. python3 scripts/smartlead_reply_analysis.py
"""

import dns.resolver
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from scripts.smartlead_client import SmartLeadClient

LOOKBACK_DAYS = 30

# Well-known consumer domains — skip MX lookup
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
OUTLOOK_DOMAINS = {"outlook.com", "hotmail.com", "live.com", "msn.com",
                   "hotmail.co.uk", "live.com.au", "hotmail.com.au"}

SEND_LABEL = {
    "GMAIL":   "Google (Gmail/Workspace)",
    "OUTLOOK": "Microsoft (Outlook/365)",
    "SMTP":    "SMTP/Other",
    "UNKNOWN": "Unknown",
}
REPLY_LABEL = {
    "GOOGLE":    "Google (Gmail/Workspace)",
    "MICROSOFT": "Microsoft (Outlook/365)",
    "OTHER":     "Other / Unknown",
}


def build_account_id_map(client):
    """Paginate all SmartLead email accounts → {account_id: GMAIL/OUTLOOK/SMTP}."""
    id_map = {}
    offset = 0
    while True:
        page = client.get_email_accounts(limit=100, offset=offset)
        if not page:
            break
        for a in page:
            id_map[a["id"]] = a.get("type", "SMTP")
        if len(page) < 100:
            break
        offset += 100
    return id_map


def fetch_all_replies(client, start_iso, end_iso):
    """Paginate the main inbox-replies endpoint for the given date window."""
    all_records = []
    offset = 0
    limit = 20
    while True:
        result = client.get_inbox_replies(offset=offset, limit=limit,
                                          start_date=start_iso, end_date=end_iso)
        batch = result.get("data", [])
        all_records.extend(batch)
        print(f"  Fetched {len(all_records)} replies...", end="\r", flush=True)
        if len(batch) < limit:
            break
        offset += limit
    print()
    return all_records


_mx_cache = {}

def get_prospect_provider(email):
    """Return 'GOOGLE', 'MICROSOFT', or 'OTHER' for the given email address."""
    if not email or "@" not in email:
        return "OTHER"
    domain = email.split("@")[-1].strip().lower()

    if domain in _mx_cache:
        return _mx_cache[domain]

    # Fast path for well-known consumer domains
    if domain in GMAIL_DOMAINS:
        _mx_cache[domain] = "GOOGLE"
        return "GOOGLE"
    if domain in OUTLOOK_DOMAINS:
        _mx_cache[domain] = "MICROSOFT"
        return "MICROSOFT"

    # MX lookup for business domains
    try:
        records = dns.resolver.resolve(domain, "MX", lifetime=5)
        mx_hosts = " ".join(str(r.exchange).lower() for r in records)
        if any(g in mx_hosts for g in ("google.com", "googlemail.com", "gmail.com", "aspmx")):
            result = "GOOGLE"
        elif any(m in mx_hosts for m in ("outlook.com", "microsoft.com", "protection.outlook")):
            result = "MICROSOFT"
        else:
            result = "OTHER"
    except Exception:
        result = "OTHER"

    _mx_cache[domain] = result
    return result


def main():
    client = SmartLeadClient()

    print("Loading email accounts...")
    account_id_map = build_account_id_map(client)
    print(f"  {len(account_id_map)} accounts: "
          f"{sum(1 for v in account_id_map.values() if v=='GMAIL')} Gmail, "
          f"{sum(1 for v in account_id_map.values() if v=='OUTLOOK')} Outlook\n")

    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)
    print(f"Fetching replies: {start.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}")
    records = fetch_all_replies(client,
                                start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    total = len(records)

    # Resolve prospect provider (with domain caching)
    print(f"Resolving email providers for {total} replies (MX lookups, cached per domain)...")
    unique_domains = {r.get("lead_email", "").split("@")[-1].lower()
                      for r in records if r.get("lead_email")}
    print(f"  {len(unique_domains)} unique domains to look up...")

    for i, domain in enumerate(unique_domains, 1):
        get_prospect_provider(f"x@{domain}")
        print(f"  Resolved {i}/{len(unique_domains)} domains...", end="\r", flush=True)
    print()

    # Build 2D counts: send_provider → reply_provider → count
    matrix = defaultdict(lambda: defaultdict(int))
    send_totals = defaultdict(int)
    reply_totals = defaultdict(int)

    for r in records:
        acct_id = r.get("email_account_id")
        send_prov = account_id_map.get(acct_id, "UNKNOWN")
        reply_prov = get_prospect_provider(r.get("lead_email", ""))
        matrix[send_prov][reply_prov] += 1
        send_totals[send_prov] += 1
        reply_totals[reply_prov] += 1

    # Print 2D breakdown table
    send_keys = [k for k in ("GMAIL", "OUTLOOK", "SMTP", "UNKNOWN") if send_totals.get(k)]
    reply_keys = [k for k in ("GOOGLE", "MICROSOFT", "OTHER") if reply_totals.get(k)]

    col_w = 20
    print(f"\n{'=' * (18 + col_w * len(reply_keys) + 8)}")
    print(f"  REPLY PROVIDER BREAKDOWN — past {LOOKBACK_DAYS} days  (rows = our inbox, cols = prospect's inbox)")
    print(f"{'=' * (18 + col_w * len(reply_keys) + 8)}")

    # Header row
    header = f"  {'Our inbox':<18}"
    for rk in reply_keys:
        header += f"{'Reply: ' + REPLY_LABEL[rk][:12]:>{col_w}}"
    header += f"{'TOTAL':>{col_w}}"
    print(header)
    print(f"  {'-' * (16 + col_w * (len(reply_keys) + 1))}")

    for sk in send_keys:
        row = f"  {SEND_LABEL[sk]:<18}"
        for rk in reply_keys:
            count = matrix[sk][rk]
            pct = (count / total * 100) if total else 0
            row += f"{f'{count} ({pct:.0f}%)':>{col_w}}"
        row += f"{send_totals[sk]:>{col_w}}"
        print(row)

    # Totals row
    print(f"  {'-' * (16 + col_w * (len(reply_keys) + 1))}")
    totrow = f"  {'TOTAL':<18}"
    for rk in reply_keys:
        totrow += f"{reply_totals[rk]:>{col_w}}"
    totrow += f"{total:>{col_w}}"
    print(totrow)
    print(f"{'=' * (18 + col_w * len(reply_keys) + 8)}")

    # Per-provider summaries
    print(f"\n  Our sending inbox breakdown:")
    for sk in send_keys:
        pct = (send_totals[sk] / total * 100) if total else 0
        print(f"    {SEND_LABEL[sk]:<34} {send_totals[sk]:>4}  ({pct:.1f}%)")

    print(f"\n  Prospect email provider breakdown:")
    for rk in reply_keys:
        pct = (reply_totals[rk] / total * 100) if total else 0
        print(f"    {REPLY_LABEL[rk]:<34} {reply_totals[rk]:>4}  ({pct:.1f}%)")

    print()


if __name__ == "__main__":
    main()
