import os
import re
import warnings

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()

from scripts.smartlead_client import SmartLeadClient
from scripts.firmable_api import FirmableClient
from scripts.ai import ask_claude

CAMPAIGN_NAME = "20260414 - ANZ_Conference (Sydney Build Expo 2026)"
# 1=Interested, 2=Meeting Request, 5=Positive redirect ("come to our booth"/"talk to X")
POSITIVE_CATEGORY_IDS = {1, 2, 5}

REPLY_TYPE_MAP = {
    2: "Meeting at event",
    5: "Redirect to contact",
}


def _classify_reply(reply_text: str) -> str:
    """Use Claude to produce a short (4-8 word) reply type label from the reply body."""
    prompt = (
        "You are summarising a reply to a cold sales email for a sales rep's review.\n"
        "Given the reply text below, write a SHORT (4-8 words) label that captures WHAT the person said "
        "— e.g. 'Invited to visit booth', 'OOO auto-reply', 'Uses Cognism, raised internally', "
        "'Open to chat at event'. Be specific. Output ONLY the label, no punctuation at the end.\n\n"
        f"Reply:\n{reply_text[:800]}"
    )
    return ask_claude(prompt).strip().strip(".")


def _strip_html(text):
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def _extract_position(lead):
    cf = lead.get("custom_fields") or {}
    if isinstance(cf, list):
        cf = {item.get("key", ""): item.get("value", "") for item in cf}
    return (
        cf.get("Position")
        or cf.get("position")
        or lead.get("title")
        or lead.get("position")
        or "N/A"
    )


def _get_reply_text(sl, campaign_id, lead_id) -> str:
    """Return full cleaned reply text (up to 800 chars) for classification and display."""
    try:
        h = sl._get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")
        replies = [m for m in h.get("history", []) if m.get("type") == "REPLY"]
        if not replies:
            return ""
        return _strip_html(replies[-1].get("email_body", ""))[:800]
    except Exception:
        return ""


def main():
    sl = SmartLeadClient()
    firmable = FirmableClient()

    # Find campaign
    campaigns = sl.list_campaigns()
    campaign = next((c for c in campaigns if c.get("name") == CAMPAIGN_NAME), None)
    if not campaign:
        print(f"Campaign not found: {CAMPAIGN_NAME!r}")
        print("Available campaigns:")
        for c in campaigns:
            print(f"  - {c.get('name')}")
        return

    campaign_id = campaign["id"]
    print(f"Campaign : {CAMPAIGN_NAME}")
    print(f"ID       : {campaign_id}")

    # Analytics
    analytics = sl._get(f"/campaigns/{campaign_id}/analytics")
    unique_contacted = analytics.get("unique_sent_count", "N/A")
    print(f"\nTotal leads contacted (unique): {unique_contacted}")

    # Paginate all leads
    all_leads = []
    limit = 100
    offset = 0
    while True:
        page = sl._get(f"/campaigns/{campaign_id}/leads", {"limit": limit, "offset": offset})
        batch = page.get("data", [])
        if not batch:
            break
        all_leads.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    # Filter positive replies
    positive = [l for l in all_leads if l.get("lead_category_id") in POSITIVE_CATEGORY_IDS]
    print(f"Positive replies (Interested)  : {len(positive)}\n")

    if not positive:
        print("No positive replies found.")
        return

    # Firmable enrichment — cached per domain
    domain_cache = {}

    def get_firmable_sizes(domain):
        if domain in domain_cache:
            return domain_cache[domain]
        try:
            company = firmable.lookup_company(domain)
            firmable_id = company.get("id")
            if not firmable_id:
                domain_cache[domain] = ("N/A", "N/A")
                return domain_cache[domain]
            sizes = firmable.get_sales_team_size(firmable_id)
            au = sizes.get("au_sales_team_size") or 0
            nz = sizes.get("nz_sales_team_size") or 0
            sea = sizes.get("sea_sales_team_size") or 0
            domain_cache[domain] = (au + nz, sea)
        except Exception:
            domain_cache[domain] = ("N/A", "N/A")
        return domain_cache[domain]

    # Pre-fetch reply snippets and classify category-1 replies with Claude
    enriched = []
    for lead_item in positive:
        lead = lead_item.get("lead", {})
        cat_id = lead_item.get("lead_category_id")
        first = lead.get("first_name", "")
        last = lead.get("last_name", "")
        name = f"{first} {last}".strip() or "Unknown"
        email = lead.get("email", "")
        domain = email.split("@")[-1] if "@" in email else "unknown"
        position = _extract_position(lead)
        snippet = _get_reply_text(sl, campaign_id, lead.get("id"))
        if cat_id == 1:
            reply_type = _classify_reply(snippet) if snippet else "Interested"
        else:
            reply_type = REPLY_TYPE_MAP.get(cat_id, "Interested")
        anz, sea = get_firmable_sizes(domain)
        enriched.append({
            "name": name, "email": email, "domain": domain,
            "position": position, "reply_type": reply_type,
            "snippet": snippet, "anz": anz, "sea": sea,
        })

    # Table
    col = [22, 26, 30, 30, 12, 12]
    header = (
        f"{'Name':<{col[0]}} "
        f"{'Domain':<{col[1]}} "
        f"{'Position':<{col[2]}} "
        f"{'Reply Type':<{col[3]}} "
        f"{'ANZ Sales':<{col[4]}} "
        f"{'SEA Sales':<{col[5]}}"
    )
    print(header)
    print("-" * (sum(col) + len(col) - 1))
    for r in enriched:
        print(
            f"{r['name']:<{col[0]}} "
            f"{r['domain']:<{col[1]}} "
            f"{r['position']:<{col[2]}} "
            f"{r['reply_type']:<{col[3]}} "
            f"{str(r['anz']):<{col[4]}} "
            f"{str(r['sea']):<{col[5]}}"
        )

    # Reply snippets
    print("\n\n--- Reply Snippets ---\n")
    for r in enriched:
        print(f"{r['name']} ({r['email']})")
        print(f"  Type   : {r['reply_type']}")
        display = r["snippet"]
        if display:
            display = display[:150] + ("…" if len(display) > 150 else "")
        print(f"  Reply  : {display or '[no reply text found]'}")
        print()


if __name__ == "__main__":
    main()
