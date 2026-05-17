"""
Bounce analysis from SmartLead master inbox untracked replies.

Produces three output CSVs:
  bounce_detail_{ts}.csv       — one row per bounce NDR with campaign, SMTP code, description
  bounce_by_code_{ts}.csv      — aggregated by SMTP code with descriptions
  non_bounce_categories_{ts}.csv — all non-bounce untracked replies categorised

Usage:
  PYTHONPATH=. python3 campaigns/us/bounce_analysis.py
"""

import csv
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

from scripts.smartlead_client import SmartLeadClient
from scripts.utils import ensure_dirs

OUTPUT_DIR = "campaigns/us/output"

# ── SMTP descriptions ────────────────────────────────────────────────────────

SMTP_DESCRIPTIONS = {
    "5.1.0":  "Unknown address error",
    "5.1.1":  "Bad destination mailbox — address doesn't exist",
    "5.1.2":  "Bad destination system address",
    "5.2.1":  "Mailbox disabled / not accepting messages",
    "5.2.2":  "Mailbox full",
    "5.4.1":  "Recipient address rejected (Microsoft DBEB — tenant blocks external senders)",
    "5.4.14": "Routing loop detected",
    "5.7.1":  "Delivery not authorized / message refused",
    "550":    "Mailbox unavailable",
    "551":    "User not local",
    "552":    "Exceeded storage allocation",
    "553":    "Mailbox name invalid",
    "554":    "Transaction failed / spam suspected",
    "421":    "Service temporarily unavailable",
    "450":    "Mailbox temporarily unavailable",
    "451":    "Local processing error (temporary)",
    "452":    "Insufficient system storage",
}

HARD_CODES = {"500","501","502","503","504","510","511","512","513","514","515",
              "550","551","552","553","554"}
SOFT_CODES = {"420","421","422","431","432","441","442","446","447","449","450","451","452"}

# ── Bounce detection ─────────────────────────────────────────────────────────

BOUNCE_PATTERNS = [
    "delivery status notification",
    "undeliverable",
    "undelivered mail",
    "returned mail",
    "mail delivery",
    "message couldn",
    "message could not",
    "failure notice",
    "non-delivery",
    "mail system error",
    "delivery failure",
]

def is_bounce_ndr(subject: str) -> bool:
    s = subject.lower()
    return any(p in s for p in BOUNCE_PATTERNS)

# ── Non-bounce categorisation ─────────────────────────────────────────────────

NON_BOUNCE_RULES = [
    ("security alert",             "Sending account security notification"),
    ("[product update]",           "Vendor product update email"),
    ("product update",             "Vendor product update email"),
    ("weekly digest",              "Vendor weekly digest"),
    ("microsoft service",          "Microsoft service notification"),
    ("activate your new google",   "Sending account setup email"),
    ("[action required]",          "Account management alert"),
    ("action required",            "Account management alert"),
    ("ooo",                        "Auto-reply — out of office"),
    ("out of office",              "Auto-reply — out of office"),
    ("automatic reply",            "Auto-reply"),
    ("delayed response",           "Auto-reply — delayed response"),
    ("re:",                        "Possible human reply"),
    ("re: ",                       "Possible human reply"),
]

def categorise_non_bounce(subject: str) -> str:
    s = subject.lower()
    for keyword, label in NON_BOUNCE_RULES:
        if keyword in s:
            return label
    return "Uncategorised"

# ── SMTP extraction & classification ─────────────────────────────────────────

ENHANCED_RE = re.compile(r"\b([45])\.\d+\.\d+\b")
BARE_RE     = re.compile(r"\b([45]\d\d)\b")

def extract_field(text: str, field: str) -> str:
    m = re.search(rf"^{re.escape(field)}:\s*(.+?)(?=\n\S|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).replace("\n", " ").strip() if m else ""

def classify_bounce(visible_text: str):
    """Return (bounce_type, smtp_code, diagnostic_message)"""
    diag    = extract_field(visible_text, "Diagnostic-Code")
    status  = extract_field(visible_text, "Status")
    search  = diag or visible_text

    m = ENHANCED_RE.search(search)
    if m:
        code = m.group(0)
        btype = "hard" if m.group(1) == "5" else "soft"
        return btype, code, diag[:200]

    m = BARE_RE.search(search)
    if m:
        code = m.group(1)
        if code in HARD_CODES or code.startswith("5"):
            return "hard", code, diag[:200]
        if code in SOFT_CODES or code.startswith("4"):
            return "soft", code, diag[:200]

    if status:
        m = BARE_RE.search(status)
        if m:
            code = m.group(1)
            return ("hard" if code.startswith("5") else "soft"), code, diag[:200]

    return "unknown", "", diag[:200]

def extract_bounced_email(visible_text: str, subject: str) -> str:
    final = extract_field(visible_text, "Final-Recipient")
    if final:
        m = re.search(r"rfc822;?\s*<?([^\s>]+@[^\s>]+)>?", final, re.IGNORECASE)
        if m:
            return m.group(1).strip("<>")
    for pattern in [
        r"following message to\s*<?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})>?",
        r"deliver\w* to\s*['\"]?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})['\"]?",
        r"recipient.*?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    ]:
        m = re.search(pattern, visible_text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""

# ── Campaign linking ──────────────────────────────────────────────────────────

def build_subject_campaign_map(client: SmartLeadClient) -> dict:
    """Build {subject_fragment_lower: campaign_name} from all campaign sequences."""
    subject_map = {}
    campaigns = client.list_campaigns()
    print(f"  Building campaign subject map from {len(campaigns)} campaigns...")
    for camp in campaigns:
        cid  = str(camp["id"])
        name = camp.get("name", cid)
        try:
            seqs = client.get_campaign_sequences(cid)
        except Exception:
            continue
        for seq in (seqs or []):
            for variant in (seq.get("sequence_variants") or []):
                subj = (variant.get("subject") or "").strip()
                if subj:
                    subject_map[subj.lower()] = name
            top_subj = (seq.get("subject") or "").strip()
            if top_subj:
                subject_map[top_subj.lower()] = name
    return subject_map

def extract_original_subject(ndr_subject: str, visible_text: str) -> str:
    """Pull the original email subject out of the NDR."""
    # "Undeliverable: [original]" or "Undelivered mail: [original]"
    m = re.match(r"undeliverable[:\s]+(.+)", ndr_subject, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.match(r"undelivered mail[:\s]+(.+)", ndr_subject, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Parse Subject: header from NDR body (appears in original message headers)
    m = re.search(r"^Subject:\s*(.+?)$", visible_text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""

def infer_campaign(ndr: dict, subject_map: dict) -> str:
    original_subj = extract_original_subject(
        ndr.get("subject", ""), ndr.get("visible_text", "")
    )
    if original_subj:
        orig_lower = original_subj.lower()
        # Exact match
        if orig_lower in subject_map:
            return subject_map[orig_lower]
        # Substring match (original subject may be truncated or prefixed with "Re:")
        for key, camp_name in subject_map.items():
            if key and (key in orig_lower or orig_lower in key):
                return camp_name

    # Fall back to sending account domain
    recipient = ndr.get("recipient_detail", "")
    m = re.search(r"@([\w.\-]+)", recipient)
    return f"(domain: {m.group(1)})" if m else "(unknown)"

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_all_untracked_replies(client: SmartLeadClient) -> list:
    replies, offset, limit = [], 0, 100
    while True:
        result = client._get("/master-inbox/untracked-replies", params={"limit": limit, "offset": offset})
        batch  = result.get("data", {}).get("data", {}).get("replies", [])
        if not batch:
            break
        replies.extend(batch)
        total = result.get("data", {}).get("data", {}).get("totalCount", 0)
        print(f"  Fetched {len(replies)} / {total}", end="\r")
        if len(replies) >= total or len(batch) < limit:
            break
        offset += limit
    print()
    return replies

# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    ensure_dirs(OUTPUT_DIR)
    client = SmartLeadClient()

    print("Fetching untracked replies from SmartLead master inbox...")
    all_replies = fetch_all_untracked_replies(client)
    total = len(all_replies)

    bounce_ndrs = [r for r in all_replies if is_bounce_ndr(r.get("subject", ""))]
    non_bounces = [r for r in all_replies if not is_bounce_ndr(r.get("subject", ""))]

    print(f"Total untracked replies : {total}")
    print(f"Bounce NDRs             : {len(bounce_ndrs)}")
    print(f"Non-bounce replies      : {len(non_bounces)}")

    print("\nBuilding campaign subject map...")
    subject_map = build_subject_campaign_map(client)
    print(f"  {len(subject_map)} sequence subjects indexed")

    # ── Process bounces ───────────────────────────────────────────────────────
    bounce_rows = []
    for ndr in bounce_ndrs:
        visible   = ndr.get("visible_text", "")
        subj      = ndr.get("subject", "")
        btype, code, diag = classify_bounce(visible)
        desc      = SMTP_DESCRIPTIONS.get(code, "")
        campaign  = infer_campaign(ndr, subject_map)
        bounced   = extract_bounced_email(visible, subj)
        bounce_rows.append({
            "received_at":       ndr.get("reply_picked_time", "")[:19],
            "campaign":          campaign,
            "sending_account":   ndr.get("recipient_detail", ""),
            "bounced_email":     bounced,
            "bounce_type":       btype,
            "smtp_code":         code,
            "smtp_description":  desc,
            "diagnostic_message": diag,
        })

    # ── Process non-bounces ───────────────────────────────────────────────────
    cat_counts   = Counter()
    cat_examples = defaultdict(list)
    for ndr in non_bounces:
        subj = ndr.get("subject", "")
        cat  = categorise_non_bounce(subj)
        cat_counts[cat] += 1
        if len(cat_examples[cat]) < 2:
            cat_examples[cat].append(subj[:80])

    # ── Write CSVs ────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail_path = os.path.join(OUTPUT_DIR, f"bounce_detail_{ts}.csv")
    by_code_path = os.path.join(OUTPUT_DIR, f"bounce_by_code_{ts}.csv")
    non_bounce_path = os.path.join(OUTPUT_DIR, f"non_bounce_categories_{ts}.csv")

    # bounce detail
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "received_at","campaign","sending_account","bounced_email",
            "bounce_type","smtp_code","smtp_description","diagnostic_message"])
        writer.writeheader()
        writer.writerows(bounce_rows)

    # bounce by code
    code_counts = Counter((r["smtp_code"], r["smtp_description"], r["bounce_type"])
                           for r in bounce_rows)
    nb = len(bounce_rows)
    with open(by_code_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "smtp_code","smtp_description","bounce_type","count","pct_of_bounces"])
        writer.writeheader()
        for (code, desc, btype), count in code_counts.most_common():
            writer.writerow({
                "smtp_code":        code or "(none)",
                "smtp_description": desc or "(unparsed)",
                "bounce_type":      btype,
                "count":            count,
                "pct_of_bounces":   f"{count/nb*100:.1f}%" if nb else "0%",
            })

    # non-bounce categories
    nn = len(non_bounces)
    with open(non_bounce_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category","count","pct_of_non_bounces","example_subjects"])
        writer.writeheader()
        for cat, count in cat_counts.most_common():
            writer.writerow({
                "category":            cat,
                "count":               count,
                "pct_of_non_bounces":  f"{count/nn*100:.1f}%" if nn else "0%",
                "example_subjects":    " | ".join(cat_examples[cat]),
            })

    # ── Terminal summary ──────────────────────────────────────────────────────
    hard = sum(1 for r in bounce_rows if r["bounce_type"] == "hard")
    soft = sum(1 for r in bounce_rows if r["bounce_type"] == "soft")
    unk  = nb - hard - soft

    print(f"\n{'='*60}")
    print(f"Bounce Analysis — All Campaigns")
    print(f"{'='*60}")
    print(f"Total untracked replies : {total}")
    print(f"  Bounce NDRs           : {nb} ({nb/total*100:.1f}%)")
    print(f"  Non-bounce replies    : {nn} ({nn/total*100:.1f}%)")
    print(f"\nBounce type:")
    print(f"  Hard  : {hard} ({hard/nb*100:.1f}%)" if nb else "  Hard  : 0")
    print(f"  Soft  : {soft} ({soft/nb*100:.1f}%)" if nb else "  Soft  : 0")
    print(f"  Unknown: {unk} ({unk/nb*100:.1f}%)" if nb else "  Unknown: 0")

    print(f"\nBounce breakdown by SMTP code:")
    for (code, desc, btype), count in code_counts.most_common(10):
        code_disp = (code or "(none)").ljust(8)
        desc_disp = (desc or "(unparsed)")[:50].ljust(52)
        print(f"  {code_disp} {count:4}x  {desc_disp}  {btype.upper()}")

    print(f"\nNon-bounce categories:")
    for cat, count in cat_counts.most_common():
        print(f"  {count:4}x  {cat}")

    print(f"\nOutputs:")
    print(f"  {detail_path}")
    print(f"  {by_code_path}")
    print(f"  {non_bounce_path}")


if __name__ == "__main__":
    run()
