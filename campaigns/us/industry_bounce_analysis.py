"""
Industry-level bounce analysis for US SmartLead campaigns.

Data sources:
  - GET /campaigns/{id}/analytics  → bounce_count, unique_sent_count  (recipient bounces)
  - lead_category_id=9 via leads   → sender bounce count
  - NDR emails (bounce_detail CSV) → SMTP code breakdown per industry

Outputs:
  industry_summary_{ts}.csv    — industry, total_sent, bounced, bounce_rate, sender_bounced
  campaign_detail_{ts}.csv     — per-campaign breakdown with both bounce types
  smtp_by_industry_{ts}.csv    — SMTP code breakdown per industry (from NDR sample)

Usage:
  PYTHONPATH=. python3 campaigns/us/industry_bounce_analysis.py
"""

import csv
import glob
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

from scripts.smartlead_client import SmartLeadClient
from scripts.utils import ensure_dirs

OUTPUT_DIR   = "campaigns/us/output"
NDR_CSV_GLOB = "campaigns/us/output/bounce_detail_*.csv"

# ── Industry extraction ───────────────────────────────────────────────────────

INDUSTRY_PATTERNS = [
    (r"healthcare",  "Healthcare"),
    (r"education",   "Education"),
    (r"cybersec",    "Cybersecurity"),
    (r"insurance",   "Insurance"),
    (r"construct",   "Construction"),
]

def extract_industry(campaign_name: str) -> str:
    n = campaign_name.lower()
    for pattern, label in INDUSTRY_PATTERNS:
        if re.search(pattern, n):
            return label
    return "Other"

def is_us_campaign(name: str) -> bool:
    n = name.upper()
    return "US_SURVEY" in n and "ANZ" not in n and "SEA" not in n

# ── Lead pagination for sender bounce ────────────────────────────────────────

SENDER_BOUNCE_CATEGORY_ID = 9

def count_sender_bounced(client: SmartLeadClient, campaign_id: str) -> int:
    count, offset, limit = 0, 0, 100
    while True:
        page  = client._get(f"/campaigns/{campaign_id}/leads",
                            params={"limit": limit, "offset": offset})
        batch = page.get("data", [])
        if not batch:
            break
        for lead_item in batch:
            if lead_item.get("lead_category_id") == SENDER_BOUNCE_CATEGORY_ID:
                count += 1
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.5)
    return count

# ── SMTP from NDR CSV ─────────────────────────────────────────────────────────

def load_ndr_smtp_by_industry(campaign_industry_map: dict) -> dict:
    """
    Load the most recent bounce_detail CSV and bucket SMTP codes by industry.
    campaign_industry_map: {campaign_name_lower: industry}
    Returns: {industry: Counter({(smtp_code, smtp_description, bounce_type): count})}
    """
    files = sorted(glob.glob(NDR_CSV_GLOB), reverse=True)
    if not files:
        return {}
    latest = files[0]
    print(f"  Loading NDR SMTP data from {os.path.basename(latest)}")

    by_industry = defaultdict(Counter)
    with open(latest, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            campaign = (row.get("campaign") or "").strip()
            industry = None
            # Try exact match first, then substring
            camp_lower = campaign.lower()
            for known_name, ind in campaign_industry_map.items():
                if known_name in camp_lower or camp_lower in known_name:
                    industry = ind
                    break
            if not industry:
                industry = extract_industry(campaign)  # fallback via name pattern
            code  = row.get("smtp_code", "") or "(none)"
            desc  = row.get("smtp_description", "") or "(unparsed)"
            btype = row.get("bounce_type", "") or "unknown"
            by_industry[industry][(code, desc, btype)] += 1
    return by_industry

# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    ensure_dirs(OUTPUT_DIR)
    client = SmartLeadClient()

    print("Fetching US campaigns...")
    all_campaigns = client.list_campaigns()
    us_campaigns  = [c for c in all_campaigns if is_us_campaign(c.get("name", ""))]
    print(f"  {len(us_campaigns)} US campaigns (out of {len(all_campaigns)} total)\n")

    campaign_rows = []
    industry_stats = defaultdict(lambda: {
        "total_sent": 0, "bounced": 0, "sender_bounced": 0, "campaigns": []
    })
    campaign_industry_map = {}  # {name_lower: industry}

    for camp in us_campaigns:
        cid      = str(camp["id"])
        name     = camp.get("name", cid)
        industry = extract_industry(name)
        campaign_industry_map[name.lower()] = industry

        # Analytics
        analytics   = client.get_campaign_analytics(cid)
        total_sent  = int(analytics.get("unique_sent_count") or 0)
        bounce_ct   = int(analytics.get("bounce_count") or 0)

        # Sender bounce (lead category 9)
        print(f"  [{industry:15s}] {name[:55]}  —  bounce={bounce_ct}", flush=True)
        time.sleep(1)
        sender_ct = count_sender_bounced(client, cid)
        time.sleep(1)

        total_bounce = bounce_ct + sender_ct
        rate         = f"{bounce_ct / total_sent * 100:.1f}%" if total_sent else "n/a"
        total_rate   = f"{total_bounce / total_sent * 100:.1f}%" if total_sent else "n/a"

        campaign_rows.append({
            "campaign":           name,
            "industry":           industry,
            "total_sent":         total_sent,
            "bounced":            bounce_ct,
            "bounce_rate":        rate,
            "sender_bounced":     sender_ct,
            "total_bounce_rate":  total_rate,
        })

        industry_stats[industry]["total_sent"]     += total_sent
        industry_stats[industry]["bounced"]        += bounce_ct
        industry_stats[industry]["sender_bounced"] += sender_ct
        industry_stats[industry]["campaigns"].append(name)

    print()

    # SMTP by industry from NDR data
    print("Loading SMTP data from NDR emails...")
    smtp_by_industry = load_ndr_smtp_by_industry(campaign_industry_map)

    # ── Write CSVs ────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    summary_path = os.path.join(OUTPUT_DIR, f"industry_summary_{ts}.csv")
    detail_path  = os.path.join(OUTPUT_DIR, f"campaign_detail_{ts}.csv")
    smtp_path    = os.path.join(OUTPUT_DIR, f"smtp_by_industry_{ts}.csv")

    # industry summary
    sorted_industries = sorted(
        industry_stats.items(),
        key=lambda x: x[1]["bounced"], reverse=True
    )
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "industry", "campaign_count", "total_sent",
            "bounced", "bounce_rate",
            "sender_bounced", "sender_bounce_rate",
            "total_bounced", "total_bounce_rate"])
        writer.writeheader()
        for industry, stats in sorted_industries:
            ts_val = stats["total_sent"]
            b      = stats["bounced"]
            sb     = stats["sender_bounced"]
            tb     = b + sb
            writer.writerow({
                "industry":           industry,
                "campaign_count":     len(stats["campaigns"]),
                "total_sent":         ts_val,
                "bounced":            b,
                "bounce_rate":        f"{b/ts_val*100:.1f}%" if ts_val else "n/a",
                "sender_bounced":     sb,
                "sender_bounce_rate": f"{sb/ts_val*100:.1f}%" if ts_val else "n/a",
                "total_bounced":      tb,
                "total_bounce_rate":  f"{tb/ts_val*100:.1f}%" if ts_val else "n/a",
            })

    # campaign detail
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "campaign", "industry", "total_sent",
            "bounced", "bounce_rate",
            "sender_bounced", "total_bounce_rate"])
        writer.writeheader()
        writer.writerows(sorted(campaign_rows, key=lambda r: r["bounced"], reverse=True))

    # smtp by industry (NDR sample)
    with open(smtp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "industry", "smtp_code", "smtp_description", "bounce_type",
            "count", "pct_of_industry_ndrs"])
        writer.writeheader()
        for industry in sorted(smtp_by_industry):
            total_ndrs = sum(smtp_by_industry[industry].values())
            for (code, desc, btype), count in smtp_by_industry[industry].most_common():
                writer.writerow({
                    "industry":              industry,
                    "smtp_code":             code,
                    "smtp_description":      desc,
                    "bounce_type":           btype,
                    "count":                 count,
                    "pct_of_industry_ndrs":  f"{count/total_ndrs*100:.1f}%" if total_ndrs else "0%",
                })

    # ── Terminal summary ──────────────────────────────────────────────────────
    print(f"\n{'='*78}")
    print(f"Bounce Analysis by Industry — US Campaigns")
    print(f"{'='*78}")
    print(f"{'Industry':<16} {'Camps':>5} {'Sent':>7} {'Bounced':>8} {'Rate':>6}  "
          f"{'Sender↗':>8} {'Rate':>6}  {'Total':>7} {'Total%':>7}")
    print("-" * 78)
    for industry, stats in sorted_industries:
        ts_val = stats["total_sent"]
        b      = stats["bounced"]
        sb     = stats["sender_bounced"]
        tb     = b + sb
        rate   = f"{b/ts_val*100:.1f}%" if ts_val else "n/a"
        srate  = f"{sb/ts_val*100:.1f}%" if ts_val else "n/a"
        trate  = f"{tb/ts_val*100:.1f}%" if ts_val else "n/a"
        ncamps = len(stats["campaigns"])
        print(f"{industry:<16} {ncamps:>5} {ts_val:>7,} {b:>8,} {rate:>6}  "
              f"{sb:>8,} {srate:>6}  {tb:>7,} {trate:>7}")

    if smtp_by_industry:
        print(f"\nSMTP code breakdown by industry (NDR sample — {sum(sum(v.values()) for v in smtp_by_industry.values())} NDR emails):")
        for industry, counter in sorted(smtp_by_industry.items()):
            total_ndrs = sum(counter.values())
            print(f"\n  {industry} ({total_ndrs} NDRs):")
            for (code, desc, btype), count in counter.most_common(5):
                pct = count / total_ndrs * 100 if total_ndrs else 0
                print(f"    {(code or '(none)').ljust(8)} {count:3}x  {pct:4.0f}%  "
                      f"{(desc or '(unparsed)')[:48]}  [{btype.upper()}]")
    else:
        print("\nNo NDR SMTP data found. Run bounce_analysis.py first to generate bounce_detail CSV.")

    print(f"\nOutputs:")
    print(f"  {summary_path}")
    print(f"  {detail_path}")
    print(f"  {smtp_path}")


if __name__ == "__main__":
    run()
