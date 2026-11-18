#!/usr/bin/env python3
"""
US Tech Intel Outbound (SaaS only).

For each company: is it a SaaS vendor? If so, pick competitors (model knowledge) and integration
partners (read off the company's own integrations page where one exists), match both to the
Firmable technology counts CSV (NA_MATCHING), and render the outreach email.

Usage:
    # First batch (creates output file)
    PYTHONPATH=. python3 campaigns/us/tech-intel-outbound/scripts/run_pipeline.py --start 0 --count 10

    # Subsequent batches
    PYTHONPATH=. python3 campaigns/us/tech-intel-outbound/scripts/run_pipeline.py --start 10 --count 200 --append

Defaults: --input = newest company CSV/XLSX in input/ (excluding the counts file),
          --counts = newest technology_companies_by_region*.csv in input/
"""

import argparse
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

from scripts.ai import ask_claude
from scripts.firmable_api import FirmableClient
from scripts.normalize_company_names import normalize as normalize_name
from scripts.tech_matcher import TechCounts

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
INPUT_DIR = CAMPAIGN_DIR / "input"
OUTPUT_DIR = CAMPAIGN_DIR / "output"
CACHE_PATH = OUTPUT_DIR / "research_cache.jsonl"
COUNTS_GLOB = "technology_companies_by_region*.csv"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
WEBSITE_CHAR_LIMIT = 4000
INTEGRATIONS_CHAR_LIMIT = 8000
REC_VERSION = 2  # v2 = partners from integrations page + context-aware match confirm

# Horizontal platforms nearly every SaaS "integrates with"; they make the partner line generic.
# Most are also above --partner-max; this catches the ones below it. Exact TECHNOLOGY_NAMEs.
GENERIC_PARTNERS = {
    "Salesforce", "HubSpot", "Microsoft", "Microsoft 365", "Microsoft Azure", "Microsoft Teams",
    "Microsoft Excel", "Microsoft Entra ID", "AWS", "Google Workspace", "Google Maps",
    "Google Analytics", "WordPress", "Stripe", "Slack", "Zoom", "Zapier", "Oracle Cloud", "SAP",
}
INTEGRATIONS_LINK_RE = re.compile(
    r"(/(integrations?|marketplace|app-?marketplace|apps|app-directory|connectors|ecosystem|partners)(/|\?|#|$))"
    r"|(//(integrations?|marketplace|apps)\.)", re.IGNORECASE)

OUTPUT_COLUMNS = [
    "company_name", "company_name_original", "website", "firmable_id", "is_saas", "personas",
    "competitor1", "competitor2", "competitor3", "partner1", "partner2", "partner3",
    "competitor1_count", "competitor2_count", "partner1_count",
    "email_subject", "email_body", "partner_source", "integrations_url", "drop_reason",
]

# {firstname} is contact-level, so it stays as a literal placeholder for SmartLead
EMAIL_SUBJECT = "{competitor1} users in North America"
EMAIL_BODY = """Hi {firstname},

{competitor1} and {competitor2} seem to be among your main competitors, and companies already paying for them tend to be the warmest accounts for {company}: the budget exists and the problem is already understood.

Using Firmable's tech intelligence data, we found {competitor1_count} companies in North America running {competitor1} and {competitor2_count} running {competitor2}.

{partner_paragraph}For each account, we can surface the {personas} with verified work emails and direct dials, so your reps skip the research and go straight to outreach.

We currently track 75,317 technologies, including other platforms you likely compete or integrate with. Worth a quick call to walk through some of them?"""


# One partner only; no usable partner means the email is purely competitive
PARTNER_PARAGRAPH = "There's also a second pool: {partner1_count} companies on {partner1}, which I believe {company} integrates with, so the fit should already be there.\n\n"


def render(template: str, row: dict) -> str:
    fields = dict(row, company=row["company_name"])
    para = PARTNER_PARAGRAPH if row["partner1"] else ""
    fields["partner_paragraph"] = re.sub(r"\{(\w+)\}", lambda m: str(fields[m.group(1)]), para)
    return re.sub(r"\{(\w+)\}", lambda m: m.group(0) if m.group(1) == "firstname" else str(fields[m.group(1)]), template)

RESEARCH_PROMPT = """You are researching a company for a US outbound campaign run by Firmable, a B2B data platform that tracks which technologies companies use (technographics) plus verified contact details.

Company: {name}
Website: {website}

Website / description content:
\"\"\"
{context}
\"\"\"

Step 1: Is this company a SaaS vendor? SaaS = it sells its own software platform on a recurring subscription. NOT SaaS: agencies, consulting, IT services, MSPs, resellers, implementation partners, hardware, marketplaces where software is incidental, non-tech businesses.

Step 2 (only if SaaS):
- competitors: 3 named commercial products that directly compete with this company's core product, most direct competitor first. Prefer well-known products that are detectable on customer websites or in tech stacks.
- brand_name: the short name the COMPANY is commonly known by on its website (e.g. "Chili Piper", not "Chili Piper Inc."). Use the company name, not one of its product names. If the site only shows a generic abbreviation, use the full readable name instead.
- personas: the buyers this company sells to, at least two, formatted exactly as "<persona1> or <persona2>" in plural form, e.g. "Heads of Marketing or Ecommerce Managers".
Use product names, not company names, when they differ (e.g. "Salesforce Marketing Cloud", not "Salesforce").

Respond with JSON only, no other text:
{{"is_saas": true|false, "reason": "<one sentence>", "brand_name": "...", "competitors": ["..."], "personas": "<persona1> or <persona2>"}}
If not SaaS, return empty lists and empty brand_name and personas strings."""

CONFIRM_PROMPT = """You are matching product names to entries in a technology database.

Context: the queries are {role} of this company: {context}

For each query product below, pick the ONE candidate that is the same product from the same vendor (or that vendor's core/main product listing). If no candidate is clearly the same product, return null. Do not pick a different product that merely shares a word or an abbreviation; for short or ambiguous names (e.g. "Pearl", "IMS"), only match when the candidate's category fits the context.

{blocks}

Respond with JSON only, mapping each query exactly as written to the chosen candidate string or null:
{{"<query>": "<candidate or null>"}}"""

PARTNER_PROMPT = """You are picking integration partners for a US outbound email from Firmable, which counts how many companies use each technology. The email says "X companies run <partner>, which <company> integrates with, so the fit should already be there."

Company: {name} ({website})
What they do: {reason}
Their competitors (do not list these): {competitors}

Integrations / marketplace page content ({source}):
\"\"\"
{integrations}
\"\"\"

Return:
- company_name: the company's own name as shown on its website (not a product name, no legal suffix).
- partners: up to 6 named third-party products this company integrates with, best first. If integrations page content is given above, ONLY pick products listed there. If none is given, use your own knowledge and only name integrations you are confident exist.
  Rank by how good the product's users are as buyers for this company: specialised, category-specific tools first. Avoid horizontal platforms almost every SaaS connects to (Salesforce, HubSpot, Microsoft 365/Teams/Azure, Google Workspace/Analytics/Maps, AWS, Slack, Zoom, Zapier, Stripe, SAP, Oracle, WordPress) unless the company is built specifically around one of them.
  Use exact product names, e.g. "Salesforce Health Cloud" not "Salesforce" when that is what they integrate with.

Respond with JSON only, no other text:
{{"company_name": "...", "partners": ["..."]}}"""

TOPUP_PROMPT = """You are helping find technologies for a US outbound campaign run by Firmable, which counts how many companies use each technology (detected from websites and tech stacks).

Company: {name} ({website})
What they do: {reason}

We need more {kinds}. These were already tried and should NOT be repeated: {tried}

{asks}
Prefer widely adopted products that are detectable on customer websites or in tech stacks. Use product names, not parent company names.

Respond with JSON only, no other text:
{{"competitors": ["..."], "partners": ["..."]}}
Return an empty list for any type not asked for."""

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)
_cache_lock = threading.Lock()


# ---------- IO helpers ----------

def _find_latest(pattern_files: list, label: str) -> Path:
    files = sorted(pattern_files, key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No {label} found in {INPUT_DIR}")
    return files[0]


def _load_companies(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    norm = {c.lower().strip().replace(" ", "_"): c for c in df.columns}

    def pick(*cands):
        for c in cands:
            if c in norm:
                return norm[c]
        return None

    name_col = pick("company_name", "name", "company", "account_name")
    site_col = pick("website", "company_website", "domain", "company_domain", "url")
    # Firmable exports carry the ID inside "Firmable company link" (.../dashboard/company/<id>)
    id_col = pick("firmable_id", "firmable_company_id", "company_id", "id", "firmable_company_link")
    if not name_col or not site_col:
        raise ValueError(f"Need a company name and website column. Found: {list(df.columns)}")
    log.info(f"Columns: name={name_col}, website={site_col}, firmable_id={id_col}")
    original = df[name_col].fillna("").astype(str).str.strip()
    out = pd.DataFrame({
        "company_name_original": original,
        "company_name": original.apply(normalize_name),
        "website": df[site_col].fillna("").astype(str).str.strip(),
        "firmable_id": df[id_col].fillna("").astype(str).str.strip().str.rstrip("/").str.split("/").str[-1]
                       if id_col else "",
    })
    return out


def _domain(website: str) -> str:
    d = re.sub(r"^https?://", "", website.strip().lower()).split("/")[0]
    return d[4:] if d.startswith("www.") else d


def _load_cache() -> dict:
    cache = {}
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    cache[rec["domain"]] = rec
    return cache


def _append_cache(rec: dict):
    with _cache_lock:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "a") as f:
            f.write(json.dumps(rec) + "\n")


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in model response: {text[:200]}")
    return json.loads(match.group(0))


# ---------- Stage 1: context ----------

def _firecrawl(website: str, with_links: bool = False, main_only: bool = True) -> tuple:
    """Return (markdown, links, http_status) for a URL."""
    if not FIRECRAWL_API_KEY:
        raise ValueError("FIRECRAWL_API_KEY is not set in .env")
    url = website if website.startswith("http") else f"https://{website}"
    resp = requests.post(
        FIRECRAWL_SCRAPE_URL,
        headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown", "links"] if with_links else ["markdown"],
              "onlyMainContent": main_only},
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return data.get("markdown") or "", data.get("links") or [], data.get("metadata", {}).get("statusCode")


def get_context(company: dict, firmable: FirmableClient) -> tuple:
    """Return (context_text, source, homepage_links). Firecrawl first, Firmable description as fallback."""
    try:
        text, links, _ = _firecrawl(company["website"], with_links=True)
        if len(text.strip()) > 200:
            return text[:WEBSITE_CHAR_LIMIT], "firecrawl", links
    except Exception as e:
        log.warning(f"  [{company['company_name']}] Firecrawl failed for {company['website']}: {e}")
    if firmable and company["firmable_id"]:
        try:
            desc = firmable.lookup_company_by_id(company["firmable_id"]).get("description") or ""
            if desc.strip():
                return desc[:WEBSITE_CHAR_LIMIT], "firmable", []
        except Exception as e:
            log.warning(f"  [{company['company_name']}] Firmable lookup failed for id {company['firmable_id']}: {e}")
    return "", "none", []


def find_integrations_page(company: dict, links: list) -> tuple:
    """Return (page_markdown, url). Uses a homepage link if one looks like an integrations page,
    else tries <domain>/integrations. Empty string if nothing usable."""
    dom = _domain(company["website"])
    root = dom.split(".")[-2] if dom.count(".") >= 1 else dom
    # Trim deep links (e.g. /integrations/jira/) back to the index page they sit under
    def index_url(link):
        link = link.split("#")[0]
        m = INTEGRATIONS_LINK_RE.search(link)
        if not m or root not in link.lower():
            return None
        if m.group(4):  # integrations.<domain> style subdomain: use its root
            u = urlparse(link)
            return f"{u.scheme}://{u.netloc}/"
        return link[:m.end()].rstrip("?#")
    cands = {u for u in map(index_url, links) if u}
    cands = sorted(cands, key=lambda u: (("partner" in u.lower()), len(u)))  # prefer /integrations over /partners
    tries = cands[:2] or [f"https://{dom}/integrations"]
    for url in tries:
        try:
            md, _, status = _firecrawl(url, main_only=False)
            if (status is None or status < 400) and len(md.strip()) > 300:
                return md[:INTEGRATIONS_CHAR_LIMIT], url
        except Exception as e:
            log.warning(f"  [{company['company_name']}] integrations page fetch failed for {url}: {e}")
    return "", ""


# ---------- Stage 3: match ----------

def match_products(names: list, counts: TechCounts, role: str = "products", context: str = "") -> dict:
    """Map each free-text product name to an exact TECHNOLOGY_NAME (or None)."""
    result, pending = {}, {}
    for n in names:
        hit = counts.exact(n)
        if hit:
            result[n] = hit
        else:
            shortlist = counts.shortlist(n)
            if shortlist:
                pending[n] = shortlist
            else:
                result[n] = None
    if pending:
        blocks = "\n\n".join(
            f"Query: {q}\nCandidates:\n" + "\n".join(f"- {c} (category: {counts.rows[c]['category']})" for c in cands)
            for q, cands in pending.items()
        )
        chosen = _parse_json(ask_claude(CONFIRM_PROMPT.format(blocks=blocks, role=role, context=context or "n/a")))
        for q, cands in pending.items():
            pick = chosen.get(q)
            # Guard against the model inventing a name outside the shortlist
            result[q] = pick if pick in cands else None
    return result


# ---------- per-company ----------

def research(company: dict, counts: TechCounts, firmable: FirmableClient) -> dict:
    rec = {"domain": _domain(company["website"]), "is_saas": None, "reason": "",
           "personas": "", "competitors": [], "partners": [], "matches": {}, "context_source": ""}
    context, source, links = get_context(company, firmable)
    rec["context_source"] = source
    rec["links"] = [l for l in links if INTEGRATIONS_LINK_RE.search(l)]  # only what find_integrations_page needs
    if not context:
        rec["reason"] = "No website or Firmable description available"
        return rec

    data = _parse_json(ask_claude(RESEARCH_PROMPT.format(
        name=company["company_name"], website=company["website"], context=context)))
    rec["is_saas"] = bool(data.get("is_saas"))
    rec["reason"] = data.get("reason", "")
    if not rec["is_saas"]:
        return rec

    rec["brand_name"] = (data.get("brand_name") or "").strip()
    rec["personas"] = (data.get("personas") or "").strip()
    rec["competitors"] = [c for c in (data.get("competitors") or []) if c][:3]
    rec["matches"] = {}
    return rec


def research_partners(company: dict, rec: dict, counts: TechCounts):
    """v2 step: re-confirm competitor matches with context, then pick partners from the
    company's integrations page. Mutates rec and sets rec["v"] = REC_VERSION."""
    rec["matches"] = match_products(rec["competitors"], counts, "competitors", rec["reason"])
    links = rec.get("links")
    if links is None:  # records cached before v2 have no homepage links
        try:
            _, links, _ = _firecrawl(company["website"], with_links=True)
            links = [l for l in links if INTEGRATIONS_LINK_RE.search(l)]
        except Exception as e:
            log.warning(f"  [{company['company_name']}] homepage links fetch failed: {e}")
            links = []
        rec["links"] = links
    page, url = find_integrations_page(company, links)
    rec["integrations_url"] = url
    data = _parse_json(ask_claude(PARTNER_PROMPT.format(
        name=company["company_name"], website=company["website"], reason=rec["reason"],
        competitors=", ".join(rec["competitors"]) or "none",
        source=url or "no integrations page found",
        integrations=page or "(none)")))
    rec["site_name"] = (data.get("company_name") or "").strip()
    rec["partners"] = [p for p in (data.get("partners") or []) if p and p not in rec["competitors"]][:6]
    rec["partner_source"] = "integrations_page" if page else "model_knowledge"
    rec["matches"].update(match_products(rec["partners"], counts, "integration partners", rec["reason"]))
    rec["v"] = REC_VERSION


def usable_picks(rec: dict, counts: TechCounts, min_count: int, partner_min: int, partner_max: int) -> tuple:
    """(competitors, partners) as matched CSV names, in the model's relevance order.
    Competitors need >= min_count; partners must sit in [partner_min, partner_max] and not be generic."""
    def ranked(names, ok, exclude=()):
        matched = []
        for n in names:
            m = rec["matches"].get(n)
            if m and m not in matched and m not in exclude and ok(counts.count(m), m):
                matched.append(m)
        return matched

    # The company's own products can't be partners (e.g. commerce.com -> "BigCommerce")
    own = re.sub(r"[^a-z]", "", rec.get("domain", "").split(".")[0])
    is_own = lambda m: bool(own) and len(own) >= 4 and own in re.sub(r"[^a-z]", "", m.lower())
    comps = ranked(rec["competitors"], lambda c, m: c >= min_count)
    parts = ranked(rec.get("partners", []),
                   lambda c, m: partner_min <= c <= partner_max and m not in GENERIC_PARTNERS and not is_own(m),
                   exclude=comps)
    return comps, parts


def top_up(company: dict, rec: dict, counts: TechCounts):
    """One extra LLM call for more competitors when fewer than the minimum matched. Mutates rec.
    (Partners are not topped up: they come from the integrations page, and padding them with
    model guesses brings back the generic picks.)"""
    tried = rec["competitors"] + rec.get("partners", [])
    data = _parse_json(ask_claude(TOPUP_PROMPT.format(
        name=company["company_name"], website=company["website"], reason=rec["reason"],
        kinds="competitors", tried=", ".join(tried) or "none",
        asks="- competitors: up to 5 more named products that directly compete with this company, most direct first.")))
    new_c = [c for c in (data.get("competitors") or []) if c and c not in tried][:5]
    rec["competitors"] += new_c
    rec["matches"].update(match_products(new_c, counts, "competitors", rec["reason"]))


def _name_fits_domain(name: str, domain: str) -> bool:
    """True if any 3+ letter word of the name (or the whole name squashed) appears in the domain root."""
    root = re.sub(r"[^a-z]", "", domain.split(".")[0])
    words = re.findall(r"[a-z]{3,}", name.lower())
    return bool(root) and (any(w in root for w in words) or re.sub(r"[^a-z]", "", name.lower()) in root)


def final_name(company: dict, rec: dict) -> str:
    """Regex-normalised input name, swapped for the name read off the website when the input
    name is long (3+ words) or doesn't match the domain (bad source data like "link", "It Company")."""
    name = company["company_name"]
    site = rec.get("site_name") or rec.get("brand_name") or ""
    if site and (len(name.split()) >= 3 or not _name_fits_domain(name, _domain(company["website"]))):
        return normalize_name(site)
    return name


def build_row(company: dict, rec: dict, counts: TechCounts, args) -> dict:
    min_count, min_comps, min_parts = args.min_count, args.min_competitors, args.min_partners
    row = {c: "" for c in OUTPUT_COLUMNS}
    row.update(company_name=final_name(company, rec), company_name_original=company["company_name_original"],
               website=company["website"], firmable_id=company["firmable_id"],
               partner_source=rec.get("partner_source", ""), integrations_url=rec.get("integrations_url", ""))
    if rec["is_saas"] is None:
        row["drop_reason"] = rec["reason"]
        return row
    row["is_saas"] = "Yes" if rec["is_saas"] else "No"
    if not rec["is_saas"]:
        row["drop_reason"] = f"Not SaaS: {rec['reason']}"
        return row
    row["personas"] = rec["personas"]

    comps, parts = usable_picks(rec, counts, min_count, args.partner_min, args.partner_max)
    for i, m in enumerate(comps[:3], 1):
        row[f"competitor{i}"] = m
    for i, m in enumerate(parts[:3], 1):
        row[f"partner{i}"] = m
    for i, m in enumerate(comps[:2], 1):
        row[f"competitor{i}_count"] = f"{counts.count(m):,}"
    if parts:
        row["partner1_count"] = f"{counts.count(parts[0]):,}"
    if len(comps) < min_comps or len(parts) < min_parts:
        row["drop_reason"] = (f"Not enough picks: {len(comps)} competitors with >= {min_count} NA companies "
                              f"(need {min_comps}), {len(parts)} partners in {args.partner_min:,}-{args.partner_max:,} "
                              f"(need {min_parts}). Competitors tried: {', '.join(rec['competitors']) or 'none'}. "
                              f"Partners tried: {', '.join(rec.get('partners', [])) or 'none'}")
    elif len(comps) >= 2:
        # Competitor paragraph needs two; partner paragraph uses partner1 or is left out
        row["email_subject"] = render(EMAIL_SUBJECT, row)
        row["email_body"] = render(EMAIL_BODY, row)
    return row


def process(company: dict, cache: dict, counts: TechCounts, firmable, args) -> dict:
    dom = _domain(company["website"])
    rec = cache.get(dom) if dom else None
    try:
        dirty = False
        if rec is None:
            rec = research(company, counts, firmable)
            dirty = True
        if rec["is_saas"] and rec.get("v") != REC_VERSION:
            research_partners(company, rec, counts)
            rec.pop("topped_up", None)  # v1 top-ups mixed in partner guesses; allow a fresh competitor top-up
            dirty = True
        # Short on competitors: one top-up call per domain (topped_up is cached so reruns don't repeat it)
        if rec["is_saas"] and not rec.get("topped_up"):
            comps, _ = usable_picks(rec, counts, args.min_count, args.partner_min, args.partner_max)
            if len(comps) < args.min_competitors:
                top_up(company, rec, counts)
                rec["topped_up"] = True
                dirty = True
        # Don't cache "no content" so a flaky site gets retried next run
        if dirty and dom and rec["context_source"] != "none":
            _append_cache(rec)
    except Exception as e:
        log.error(f"  [{company['company_name']}] research failed: {e}")
        rec = {"is_saas": None, "reason": f"Error: {e}"}
    return build_row(company, rec, counts, args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path)
    ap.add_argument("--counts", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--min-count", type=int, default=100)
    ap.add_argument("--min-competitors", type=int, default=2)
    ap.add_argument("--min-partners", type=int, default=0,
                    help="Drop rows with fewer usable partners. Default 0: keep them, email drops the partner paragraph")
    ap.add_argument("--partner-min", type=int, default=500)
    ap.add_argument("--partner-max", type=int, default=150000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    counts_path = args.counts or _find_latest(list(INPUT_DIR.glob(COUNTS_GLOB)), "technology counts CSV")
    input_path = args.input or _find_latest(
        [p for p in list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
         if not p.match(COUNTS_GLOB)], "company CSV/XLSX")
    output_path = args.output or OUTPUT_DIR / f"tech_intel_{input_path.stem}.csv"

    log.info(f"Counts: {counts_path.name}")
    counts = TechCounts(counts_path)
    log.info(f"  {len(counts.rows):,} technologies loaded")
    log.info(f"Input:  {input_path.name}")
    companies = _load_companies(input_path)
    end = len(companies) if args.count is None else min(args.start + args.count, len(companies))
    batch = companies.iloc[args.start:end].to_dict("records")
    log.info(f"Processing rows {args.start + 1}-{end} of {len(companies)}")

    try:
        firmable = FirmableClient()
    except ValueError as e:
        log.warning(f"Firmable fallback disabled: {e}")
        firmable = None

    cache = _load_cache()
    cached = sum(1 for c in batch if _domain(c["website"]) in cache)
    log.info(f"  {cached} cached, {len(batch) - cached} to research")

    rows = [None] * len(batch)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, c, cache, counts, firmable, args): i
                   for i, c in enumerate(batch)}
        for done, fut in enumerate(as_completed(futures), 1):
            rows[futures[fut]] = fut.result()
            if done % 10 == 0 or done == len(batch):
                log.info(f"  {done}/{len(batch)} done")

    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.append and output_path.exists():
        out = pd.concat([pd.read_csv(output_path, dtype=str, keep_default_na=False), out], ignore_index=True)
    out.to_csv(output_path, index=False)

    kept = out[out["drop_reason"] == ""]
    batch_out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    print(f"\nBatch {args.start + 1}-{end} complete -> {output_path}")
    print(f"  Kept (SaaS + count):   {(batch_out['drop_reason'] == '').sum()}")
    print(f"  Dropped, not SaaS:     {batch_out['drop_reason'].str.startswith('Not SaaS').sum()}")
    print(f"  Dropped, too few picks:{batch_out['drop_reason'].str.startswith('Not enough').sum()}")
    print(f"  Dropped, error/no data:{(~batch_out['drop_reason'].isin(['']) & ~batch_out['drop_reason'].str.startswith(('Not SaaS', 'Not enough'))).sum():>4}")
    print(f"  File total kept:       {len(kept)} of {len(out)}")


if __name__ == "__main__":
    main()
