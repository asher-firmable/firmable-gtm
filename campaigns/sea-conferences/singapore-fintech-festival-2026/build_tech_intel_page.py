"""
Build the SFF 2026 eligible-exhibitor tech intel page (step 3 of the tech intel page).

Merges:
  output/hubspot_check.csv + output/exhibitors.csv   eligible rows, HubSpot status, booth/hall/focus
  output/tech_intel_research.jsonl                   bucket, description, picks (research_tech_intel.py)
  output/tech_counts_mcp.json                        {tech: {"id", "anz", "sgmy"}} from the Firmable MCP

Writes:
  output/sff_2026_eligible_tech_intel.html           standalone page (open locally / share as a file)
  output/sff_2026_eligible_tech_intel.artifact.html  same page without the html/head/body wrapper,
                                                     for publishing as a claude.ai artifact
  --downloads also copies the standalone page to ~/Downloads.

Layout and filters follow the GovWare 2026 page (govware-singapore-2026/output/govware_sponsor_tech_intel.html),
with Hall in place of sponsor Tier and status buckets from the event exhibitor check.

Run from repo root:
    PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/build_tech_intel_page.py --downloads
"""

import argparse
import csv
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from scripts.normalize_company_names import normalize

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
RESEARCH = OUT / "tech_intel_research.jsonl"
MCP_COUNTS = OUT / "tech_counts_mcp.json"
PAGE = OUT / "sff_2026_eligible_tech_intel.html"
ARTIFACT = OUT / "sff_2026_eligible_tech_intel.artifact.html"
DOWNLOADS = Path.home() / "Downloads" / PAGE.name

ANZ_INFLATED = 50_000
GLOBAL_INFLATED = 3_000_000
OPENER_MIN_POOL = 50  # ANZ + SG+MY companies
FIRMABLE_URL = "https://app.firmable.com/dashboard/company/{}"
BUCKET_LABEL = {"saas": ("SaaS Vendor", "badge-blue"), "services": ("Service Provider", "badge-purple"),
                "na": ("Not Applicable", "badge-grey")}
KIND_LABEL = {"competitor": ("Competitor", "badge-competitor"), "integration": ("Integration", "badge-integration"),
              "partner": ("Partner Platform", "badge-partner")}
STATUS_LABEL = {"no_hs": "Not in HubSpot", "sdr": "In HubSpot, SDR assigned", "no_sdr": "In HubSpot, no SDR",
                "recent": "Contacted in last 30 days"}

e = html.escape


def bare_domain(url: str) -> str:
    return re.sub(r"^(https?://)?(www\.)?", "", (url or "").strip().lower()).split("/")[0]


def display_name(name: str) -> str:
    n = re.sub(r"\s*\([^)]*\)", "", normalize(name) or name).strip(" ,.")
    if n.isupper() and len(n) > 4:
        n = " ".join(w if len(w) <= 3 else w.title() for w in n.split())
    return n or name


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else "n/a"


def load_rows() -> list:
    ex = list(csv.DictReader(open(OUT / "exhibitors.csv", encoding="utf-8")))
    hs = list(csv.DictReader(open(OUT / "hubspot_check.csv", encoding="utf-8")))
    seen, rows = set(), []
    for x, h in zip(ex, hs):
        key = (h["company_name"], h["company_website"])
        if key in seen:
            continue
        seen.add(key)
        if h["status"] != "Eligible":
            continue
        sdr = h["sdr_sea"] or h["sdr_au"] or h["sdr_nz"]
        if h["reason"].startswith("Contacted"):
            status = "recent"
        elif h["exists_in_hubspot"] == "NO":
            status = "no_hs"
        else:
            status = "sdr" if sdr else "no_sdr"
        rows.append({**h, "hall": x["hall"], "stand": x["stand"], "focus": x["category"], "country": x["country"],
                     "website_full": x["website"] or h["company_website"], "sdr": sdr, "status_key": status,
                     "domain": bare_domain(x["website"] or h["company_website"])})
    return rows


def pick_html(p: dict, mcp: dict) -> str:
    c = mcp.get(p["tech"], {})
    anz, sgmy = c.get("anz"), c.get("sgmy")
    warn = (isinstance(anz, int) and anz > ANZ_INFLATED) or p["global"] > GLOBAL_INFLATED
    label, cls = KIND_LABEL[p["kind"]]
    warn_html = (' <span class="warn-icon" title="Very large count: this tag covers generic tech most companies use. '
                 'Directional only.">⚠</span>') if warn else ""
    counts = (f'<span class="count-anz">{fmt(anz)} ANZ</span> <span class="count-sgmy">{fmt(sgmy)} SG+MY</span> '
              f'<span class="count-global">{fmt(p["global"])} global</span>')
    return f"""
        <div class="pick-card">
          <div class="pick-header"><span class="badge {cls}">{label}</span> <strong class="pick-name">{e(p["tech"])}</strong>{warn_html}</div>
          <div class="pick-counts">{counts}</div>
          <div class="pick-reason">{e(p["reason"])}</div>
        </div>"""


# Horizontal platforms: real counts, but they say little about the exhibitor's buyers. Used for the
# opener only when nothing more specific has a count.
GENERIC = {"Microsoft Azure", "AWS", "Amazon Web Services China", "Google Cloud Platform", "Alibaba Cloud",
           "IBM Cloud", "Salesforce", "HubSpot", "Microsoft", "Microsoft 365", "Microsoft Teams", "Microsoft Excel",
           "Microsoft Word", "SAP", "Oracle", "Kubernetes", "GitHub", "GitLab", "WhatsApp", "Whatsapp Business",
           "Telegram", "Cloudflare CDN", "ChatGPT (OpenAI)", "ChatGPT", "Visa", "Mastercard", "Stripe"}


def opener(name: str, picks: list, mcp: dict) -> str:
    """Prefer a competitor, then a specific integration/partner, then a generic platform; larger pool breaks ties."""
    ranked = []
    for p in picks:
        c = mcp.get(p["tech"], {})
        anz, sgmy = c.get("anz") or 0, c.get("sgmy") or 0
        if anz > ANZ_INFLATED or p["global"] > GLOBAL_INFLATED or (anz + sgmy) == 0:
            continue
        small = (anz + sgmy) < OPENER_MIN_POOL  # "1 ANZ company" is not a pitch; use it only if nothing else
        ranked.append(((small, p["tech"] in GENERIC, p["kind"] != "competitor", -(anz + sgmy)), p, anz, sgmy))
    if not ranked:
        return ""
    _, p, anz, sgmy = min(ranked, key=lambda x: x[0])
    tail = {"competitor": f"a direct competitor to {name}",
            "integration": f"which {name} integrates with",
            "partner": f"a platform {name} delivers"}[p["kind"]]
    verb = "already running" if p["kind"] == "competitor" else "using"
    return (f"Firmable maps {anz:,} ANZ and {sgmy:,} SG+MY companies {verb} {p['tech']}, {tail}.")


def card_html(r: dict, rec: dict, mcp: dict) -> str:
    name = display_name(r["company_name"])
    bucket = rec.get("bucket", "na")
    blabel, bcls = BUCKET_LABEL[bucket]
    st = r["status_key"]
    if st == "recent":
        status_badges = (f'<span class="badge badge-orange">Contacted in last 30 days</span> '
                         f'<span class="badge badge-grey">Last contact: {e(r["last_contacted"])}</span>')
        border = "border-orange"
    else:
        status_badges = f'<span class="badge badge-grey">{STATUS_LABEL[st]}</span>'
        border = "border-green" if bucket != "na" else "border-grey"
    meta = [f'<span class="booth-tag">Booth {e(r["stand"])}</span>' if r["stand"] else "",
            f'<span class="booth-tag">Hall {e(r["hall"])}</span>' if r["hall"] else "",
            f'<span class="hq-tag">HQ: {e(r["hq_country"] or r["country"])}</span>' if (r["hq_country"] or r["country"]) else "",
            f'<span class="hq-tag">{e(r["focus"])}</span>' if r["focus"] else "", status_badges]
    links = []
    if r["company_hubspot_url"]:
        links.append(f'<a href="{e(r["company_hubspot_url"])}" target="_blank" rel="noopener" class="link-btn link-hs">HubSpot</a>')
    if r["firmable_id"]:
        links.append(f'<a href="{FIRMABLE_URL.format(e(r["firmable_id"]))}" target="_blank" rel="noopener" class="link-btn link-firmable">Firmable</a>')
    if r["website_full"]:
        url = r["website_full"] if r["website_full"].startswith("http") else "https://" + r["website_full"]
        links.append(f'<a href="{e(url)}" target="_blank" rel="noopener" class="link-btn link-web">Website</a>')
    owners = [f"Owner: {r['company_owner']}" if r["company_owner"] else "",
              f"SEA owner: {r['company_owner_sea']}" if r["company_owner_sea"] else "",
              f"SDR: {r['sdr']}" if r["sdr"] else ""]
    owner_line = " · ".join(o for o in owners if o)
    picks = rec.get("picks", [])
    if picks:
        body = '<div class="picks-grid">' + "".join(pick_html(p, mcp) for p in picks) + "\n      </div>"
        op = opener(name, picks, mcp)
        if op:
            body += f'\n      <div class="opener"><strong>Opener:</strong> {e(op)}</div>'
    else:
        body = '<p class="no-picks">No tracked competitor or partner technology for this company.</p>'
    search = f"{name} {r['company_name']} {r['domain']} " + " ".join(p["tech"] for p in picks)
    return f"""
    <article class="card {border}" data-hall="{e(r['hall'])}" data-bucket="{bucket}" data-status="{st}" data-search="{e(search.lower())}">
      <div class="card-title-row">
        <h3 class="company-name">{e(name)}</h3>
        <span class="badge {bcls}">{blabel}</span>
      </div>
      <div class="card-meta">{" ".join(m for m in meta if m)}</div>
      <div class="card-links">{" ".join(links)}</div>
      {f'<div class="owner-info">{e(owner_line)}</div>' if owner_line else ""}
      <p class="card-description">{e(rec.get("description") or "")}</p>
      {body}
    </article>"""


def filter_buttons(group: str, options: list) -> str:
    btns = [f'<button type="button" class="filter-btn active" data-group="{group}" data-value="all" aria-pressed="true">All</button>']
    for value, label, n in options:
        btns.append(f'<button type="button" class="filter-btn" data-group="{group}" data-value="{value}" aria-pressed="false">{e(label)} ({n})</button>')
    return "".join(btns)


CSS = """
/* Layout: GovWare battlecard grid. Summary header, sticky filter bar, two-up cards on desktop, one column on phones. */
:root {
  --bg: #f1f5f9; --surface: #ffffff; --surface-2: #f8fafc; --text: #0f172a; --muted: #64748b; --border: #e2e8f0;
  --accent: #1d4ed8; --accent-soft: #eff6ff; --accent-line: #bfdbfe; --accent-text: #1e40af;
  --green: #15803d; --green-soft: #dcfce7; --green-line: #16a34a;
  --orange: #b45309; --orange-soft: #fef3c7; --orange-line: #d97706;
  --red: #dc2626; --red-soft: #fee2e2;
  --purple: #7c3aed; --purple-soft: #ede9fe;
  --blue-soft: #dbeafe; --teal: #0891b2; --grey-line: #94a3b8;
  --hs: #c2410c; --hs-soft: #fff7ed; --hs-line: #fed7aa;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0b1220; --surface: #121a2b; --surface-2: #172036; --text: #e5e9f2; --muted: #94a3b8; --border: #26324a;
  --accent: #7aa2ff; --accent-soft: #16213d; --accent-line: #2b3f73; --accent-text: #b8ccff;
  --green: #4ade80; --green-soft: #12301f; --green-line: #22c55e;
  --orange: #fbbf24; --orange-soft: #3a2a0c; --orange-line: #f59e0b;
  --red: #f87171; --red-soft: #3b1515;
  --purple: #c4b5fd; --purple-soft: #2a1f4a;
  --blue-soft: #1a2950; --teal: #22d3ee; --grey-line: #475569;
  --hs: #fdba74; --hs-soft: #331d0d; --hs-line: #7c3a12; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0b1220; --surface: #121a2b; --surface-2: #172036; --text: #e5e9f2; --muted: #94a3b8; --border: #26324a;
  --accent: #7aa2ff; --accent-soft: #16213d; --accent-line: #2b3f73; --accent-text: #b8ccff;
  --green: #4ade80; --green-soft: #12301f; --green-line: #22c55e;
  --orange: #fbbf24; --orange-soft: #3a2a0c; --orange-line: #f59e0b;
  --red: #f87171; --red-soft: #3b1515;
  --purple: #c4b5fd; --purple-soft: #2a1f4a;
  --blue-soft: #1a2950; --teal: #22d3ee; --grey-line: #475569;
  --hs: #fdba74; --hs-soft: #331d0d; --hs-line: #7c3a12; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; }
.wrap { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header { background: var(--surface); border-bottom: 2px solid var(--accent); }
header .wrap { padding-block: 16px; }
h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--accent); text-wrap: balance; }
.subtitle { color: var(--muted); font-size: 13px; margin-top: 4px; max-width: 80ch; line-height: 1.5; }
.stats-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.stat { background: var(--bg); border-radius: 6px; padding: 6px 12px; font-size: 13px; font-variant-numeric: tabular-nums; }
.stat strong { color: var(--accent); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--surface); }
.controls { background: var(--surface); border-bottom: 1px solid var(--border); position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; }
.controls .wrap { padding-block: 12px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.controls input { border: 1px solid var(--border); background: var(--surface-2); color: var(--text); border-radius: 6px; padding: 7px 12px; font-size: 13px; width: 260px; max-width: 100%; }
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.filter-label { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: .02em; }
.filter-btn, .clear-btn { border: 1px solid var(--border); background: var(--bg); color: var(--text); border-radius: 20px; padding: 4px 10px; font-size: 12px; cursor: pointer; font-family: inherit; }
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--accent); color: var(--surface); border-color: var(--accent); }
.clear-btn { background: none; color: var(--muted); }
.clear-btn:hover { border-color: var(--red); color: var(--red); }
button:focus-visible, input:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.result-count { padding-block: 8px; font-size: 13px; color: var(--muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 460px), 1fr)); gap: 16px; padding-block: 8px 24px; }
.card { background: var(--surface); border-radius: 10px; border: 1px solid var(--border); border-left: 4px solid var(--grey-line); padding: 16px; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.card.border-green { border-left-color: var(--green-line); }
.card.border-orange { border-left-color: var(--orange-line); }
.card-title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.company-name { margin: 0; font-size: 15px; font-weight: 700; }
.card-meta, .card-links { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.owner-info { font-size: 12px; color: var(--muted); }
.card-description { margin: 0; font-size: 13px; color: var(--muted); font-style: italic; line-height: 1.45; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.badge-orange { background: var(--orange-soft); color: var(--orange); }
.badge-grey { background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }
.badge-blue, .badge-partner { background: var(--blue-soft); color: var(--accent); }
.badge-purple { background: var(--purple-soft); color: var(--purple); }
.badge-competitor { background: var(--red-soft); color: var(--red); }
.badge-integration { background: var(--green-soft); color: var(--green); }
.booth-tag, .hq-tag { font-size: 11px; color: var(--muted); background: var(--bg); border-radius: 4px; padding: 2px 6px; border: 1px solid var(--border); }
.link-btn { display: inline-block; padding: 3px 10px; border-radius: 5px; font-size: 12px; font-weight: 500; text-decoration: none; border: 1px solid; }
.link-hs { color: var(--hs); border-color: var(--hs-line); background: var(--hs-soft); }
.link-firmable { color: var(--accent); border-color: var(--accent-line); background: var(--accent-soft); }
.link-web { color: var(--muted); border-color: var(--border); background: var(--surface-2); }
.picks-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr)); gap: 8px; }
.pick-card { background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; min-width: 0; }
.pick-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; flex-wrap: wrap; }
.pick-name { font-size: 13px; font-weight: 600; }
.pick-counts { font-size: 12px; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
.count-anz { color: var(--accent); font-weight: 600; }
.count-sgmy { color: var(--teal); font-weight: 600; }
.count-global { color: var(--muted); }
.pick-reason { font-size: 11px; color: var(--muted); line-height: 1.4; }
.warn-icon { cursor: help; color: var(--orange); }
.no-picks { margin: 0; color: var(--muted); font-size: 13px; font-style: italic; }
.opener { background: var(--accent-soft); border: 1px solid var(--accent-line); border-radius: 6px; padding: 8px 10px; font-size: 12px; color: var(--accent-text); line-height: 1.45; }
.opener strong { color: var(--accent); }
footer { border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); }
footer .wrap { padding-block: 20px 28px; }
footer h4 { color: var(--text); margin: 0 0 8px; }
footer ul { margin: 0; padding-left: 16px; line-height: 1.8; max-width: 90ch; }
[hidden] { display: none !important; }
"""

JS = """
const state = { hall: 'all', bucket: 'all', status: 'all' };
const cards = Array.from(document.querySelectorAll('.card'));
const search = document.getElementById('search');
function apply() {
  const q = search.value.trim().toLowerCase();
  let shown = 0;
  cards.forEach(c => {
    const ok = (state.hall === 'all' || c.dataset.hall === state.hall)
      && (state.bucket === 'all' || c.dataset.bucket === state.bucket)
      && (state.status === 'all' || c.dataset.status === state.status)
      && (!q || c.dataset.search.includes(q));
    c.hidden = !ok;
    if (ok) shown++;
  });
  document.getElementById('result-count').textContent = shown + ' of ' + cards.length + ' companies shown';
}
document.querySelectorAll('.filter-btn').forEach(b => b.addEventListener('click', () => {
  state[b.dataset.group] = b.dataset.value;
  document.querySelectorAll('.filter-btn[data-group="' + b.dataset.group + '"]').forEach(x => {
    const on = x === b; x.classList.toggle('active', on); x.setAttribute('aria-pressed', on);
  });
  apply();
}));
document.getElementById('clear').addEventListener('click', () => {
  Object.keys(state).forEach(k => state[k] = 'all');
  search.value = '';
  document.querySelectorAll('.filter-btn').forEach(x => {
    const on = x.dataset.value === 'all'; x.classList.toggle('active', on); x.setAttribute('aria-pressed', on);
  });
  apply();
});
search.addEventListener('input', apply);
apply();
"""


def build() -> tuple:
    rows = load_rows()
    research = {}
    for line in RESEARCH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            research[r["domain"]] = r  # later lines win
    mcp = json.loads(MCP_COUNTS.read_text(encoding="utf-8")) if MCP_COUNTS.exists() else {}
    missing = [r["company_name"] for r in rows if r["domain"] not in research]
    if missing:
        print(f"WARNING: {len(missing)} eligible companies have no research record: {missing[:10]}")

    order = {"saas": 0, "services": 1, "na": 2}
    rows.sort(key=lambda r: (order.get(research.get(r["domain"], {}).get("bucket", "na"), 3), display_name(r["company_name"]).lower()))

    buckets = Counter(research.get(r["domain"], {}).get("bucket", "na") for r in rows)
    statuses = Counter(r["status_key"] for r in rows)
    halls = Counter(r["hall"] for r in rows if r["hall"])
    with_picks = sum(1 for r in rows if research.get(r["domain"], {}).get("picks"))

    cards = "".join(card_html(r, research.get(r["domain"], {}), mcp) for r in rows)
    hall_opts = [(h, f"Hall {h}", n) for h, n in sorted(halls.items())]
    bucket_opts = [(b, BUCKET_LABEL[b][0].replace(" Vendor", "").replace(" Provider", "s"), buckets[b])
                   for b in ("saas", "services", "na") if buckets[b]]
    status_opts = [(s, STATUS_LABEL[s], statuses[s]) for s in ("no_hs", "sdr", "no_sdr", "recent") if statuses[s]]

    head = f"""<title>SFF 2026 Exhibitor Tech Intel</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>"""
    body = f"""
<header><div class="wrap">
  <h1>Singapore FinTech Festival 2026: eligible exhibitor tech intel</h1>
  <p class="subtitle">Battlecard for SDRs and AEs. Singapore EXPO, 18 to 20 Nov 2026. Every exhibitor that passed the HubSpot eligibility check, with the competitor and integration technologies Firmable can count. ANZ = companies headquartered in AU or NZ; SG+MY = headquartered in Singapore or Malaysia.</p>
  <div class="stats-row">
    <div class="stat"><strong>{len(rows)}</strong> eligible exhibitors</div>
    <div class="stat"><strong>{buckets['saas']}</strong> SaaS vendors</div>
    <div class="stat"><strong>{buckets['services']}</strong> service providers</div>
    <div class="stat"><strong>{buckets['na']}</strong> not applicable</div>
    <div class="stat"><strong>{with_picks}</strong> with tech picks</div>
    <div class="stat"><strong>{statuses['recent']}</strong> contacted in last 30 days</div>
  </div>
</div></header>
<div class="controls"><div class="wrap">
  <input type="search" id="search" placeholder="Search company, domain or technology" aria-label="Search company, domain or technology">
  <div class="filter-group"><span class="filter-label">Hall</span>{filter_buttons("hall", hall_opts)}</div>
  <div class="filter-group"><span class="filter-label">Type</span>{filter_buttons("bucket", bucket_opts)}</div>
  <div class="filter-group"><span class="filter-label">Status</span>{filter_buttons("status", status_opts)}</div>
  <button type="button" class="clear-btn" id="clear">Clear filters</button>
</div></div>
<main class="wrap">
  <div class="result-count" id="result-count">{len(rows)} companies shown</div>
  <div class="grid">{cards}
  </div>
</main>
<footer><div class="wrap">
  <h4>How to read this page</h4>
  <ul>
    <li>Eligible = found in Firmable, not an active customer or trial, no open deal, and (if an SDR is assigned) no scheduled next step. Companies contacted in the last 30 days are still eligible; their cards have an orange edge and the last-contact date, so check with whoever made contact first.</li>
    <li>Competitor = companies already paying for this kind of product. Integration = products the exhibitor connects to, so those companies are a natural fit. Partner Platform = a platform a services firm implements or resells.</li>
    <li>ANZ and SG+MY counts are live Firmable searches (company HQ country). Global counts come from Firmable's technology export. ⚠ marks very large counts (over 50,000 ANZ or 3M global) from generic tags such as AWS or Microsoft Azure; treat them as directional only.</li>
    <li>Picks and descriptions are AI-researched from each company's website and are a starting point for review, not verified integrations.</li>
    <li>This is a company-level screen. Run the contact-level SmartLead pre-campaign check before any upload.</li>
  </ul>
</div></footer>
<script>{JS}</script>
"""
    standalone = f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">\n{head}\n</head>\n<body>{body}</body>\n</html>\n'
    artifact = f"{head}\n{body}"
    return standalone, artifact, len(rows), buckets, statuses, with_picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--downloads", action="store_true", help="Also copy the standalone page to ~/Downloads")
    args = ap.parse_args()
    standalone, artifact, n, buckets, statuses, with_picks = build()
    PAGE.write_text(standalone, encoding="utf-8")
    ARTIFACT.write_text(artifact, encoding="utf-8")
    if args.downloads:
        shutil.copyfile(PAGE, DOWNLOADS)
    print(f"{n} cards | buckets {dict(buckets)} | status {dict(statuses)} | {with_picks} with picks")
    print(f"-> {PAGE}\n-> {ARTIFACT}" + (f"\n-> {DOWNLOADS}" if args.downloads else ""))


if __name__ == "__main__":
    main()
