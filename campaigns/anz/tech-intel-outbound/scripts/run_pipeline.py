#!/usr/bin/env python3
"""
ANZ Tech Intel (review sheet, any company type).

For each company: classify what kind of business it is, pick competitors (model knowledge) and
integration partners (read off the company's own integrations/partners page where one exists),
match both to the Firmable technology counts CSV, and attach US (NA_MATCHING) and APAC
(APAC_MATCHING) counts. No SaaS gate and no drops: every row gets an outreach_fit verdict so the
list can be reviewed for a technographics angle. No email rendering.

Usage:
    # First batch (creates output file)
    PYTHONPATH=. python3 campaigns/anz/tech-intel-outbound/scripts/run_pipeline.py --start 0 --count 10

    # Subsequent batches
    PYTHONPATH=. python3 campaigns/anz/tech-intel-outbound/scripts/run_pipeline.py --start 10 --append

Defaults: --input = newest company CSV/XLSX in input/ (excluding the counts file),
          --counts = newest technology_companies_by_region*.csv in input/
"""

import argparse
import json
import logging
import os
import re
import threading
from collections import Counter
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
US_COL, APAC_COL = "NA_MATCHING", "APAC_MATCHING"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
WEBSITE_CHAR_LIMIT = 4000
INTEGRATIONS_CHAR_LIMIT = 8000
REC_VERSION = 4  # v2+ = partners picked from the tracked-technology list (integrates / complementary)

RETAILER = "Energy retailer or generator"
COMPANY_TYPES = ["Software vendor", "Hardware or equipment", RETAILER, "Services or installer", "Other"]
RELATIONSHIPS = ("integrates", "complementary")
# Categories offered to the partner step: where energy hardware connects (OT protocols, control
# systems, devices) and what its buyers run (field service, maintenance, construction, asset tools)
PARTNER_CATEGORIES = ["OT, ICS & Industrial", "IoT & Embedded Devices", "Workplace & Facility Devices",
                      "Specialized & Regulated Devices", "Industry Operations"]

# Horizontal platforms nearly everything "integrates with"; they say nothing about the buyer.
GENERIC_PARTNERS = {
    "Salesforce", "HubSpot", "Microsoft", "Microsoft 365", "Microsoft Azure", "Microsoft Teams",
    "Microsoft Excel", "Microsoft Entra ID", "AWS", "Google Workspace", "Google Maps",
    "Google Analytics", "WordPress", "Stripe", "Slack", "Zoom", "Zapier", "Oracle Cloud", "SAP",
}
INTEGRATIONS_LINK_RE = re.compile(
    r"(/(integrations?|marketplace|app-?marketplace|apps|app-directory|connectors|ecosystem|partners|"
    r"compatib\w*|technology-partners)(/|\?|#|$))"
    r"|(//(integrations?|marketplace|apps)\.)", re.IGNORECASE)

PICK_COLUMNS = ([f"competitor{i}{s}" for i in (1, 2, 3) for s in ("", "_us_count", "_apac_count")]
                + [f"partner{i}{s}" for i in (1, 2, 3)
                   for s in ("", "_us_count", "_apac_count", "_relationship", "_why")])
OUTPUT_COLUMNS = [
    "company_name", "company_name_original", "website", "firmable_id", "company_type", "what_they_do",
    "personas", *PICK_COLUMNS, "integrations_url",
    "competitors_unmatched", "partners_unmatched", "outreach_fit", "fit_note",
    "copy", "copy_competitors", "copy_partners", "copy_error",
]

RESEARCH_PROMPT = """You are researching an Australian / New Zealand company, most likely in the energy sector, for Firmable, a B2B data platform that tracks which technologies companies use (technographics) plus verified contact details. We want to know which named products this company competes with, so we can count how many companies run those products.

Company: {name}
Website: {website}

Website / description content:
\"\"\"
{context}
\"\"\"

Return:
- company_type: exactly one of {types}.
- what_they_do: one plain sentence on what they sell and to whom.
- brand_name: the short name the COMPANY is commonly known by on its website, no legal suffix. Use the company name, not one of its product names.
- personas: the buyers this company sells to, at least two, formatted exactly as "<persona1> or <persona2>" in plural form, e.g. "Facilities Managers or Energy Managers".
- competitors: up to 5 named commercial PRODUCTS (software, platforms, or branded equipment/control systems) that directly compete with this company's core offering, most direct first. Use product names, not parent company names, when they differ (e.g. "Schneider EcoStruxure", not "Schneider Electric"). If the company sells no product (e.g. a retailer, installer or consultancy), name the products its competitors are best known for only if that is meaningful; otherwise return an empty list. Do not invent products.

Respond with JSON only, no other text:
{{"company_type": "...", "what_they_do": "...", "brand_name": "...", "personas": "<persona1> or <persona2>", "competitors": ["..."]}}"""

CONFIRM_PROMPT = """You are matching product names to entries in a technology database.

Context: the queries are {role} of this company: {context}

For each query product below, pick the ONE candidate that is the same product from the same vendor (or that vendor's core/main product listing). If no candidate is clearly the same product, return null. Do not pick a different product that merely shares a word or an abbreviation; for short or ambiguous names, only match when the candidate's category fits the context.

{blocks}

Respond with JSON only, mapping each query exactly as written to the chosen candidate string or null:
{{"<query>": "<candidate or null>"}}"""

PARTNER_PROMPT = """You are picking technology partners for an Australian / New Zealand company, for Firmable, which counts how many companies use each technology. The pitch: "X companies run <technology>, which fits with what you sell, so they are a warm pool of buyers."

Company: {name} ({website})
Type: {company_type}
What they do: {reason}
Who they sell to: {personas}
Their competitors (do not pick these): {competitors}

Website content:
\"\"\"
{context}
\"\"\"

Integrations / partners / compatibility page ({source}):
\"\"\"
{integrations}
\"\"\"

Tracked technologies you may choose from (grouped by category):
{candidates}

Pick up to 5 technologies from the list above, best buyer pool first, each with one relationship:
- "integrates": the company's products connect to, are compatible with, or are certified for this technology (a protocol, control system, platform or device). Set evidence to "website" if the content above shows it, or "standard" if it is standard for this exact product type (e.g. Modbus for inverters and generator controllers, BACnet for building controls). If it only "could work alongside" or "is common in the same setting", do not pick it.
- "complementary": companies running this technology are the businesses that buy from this company (e.g. electrical contractors running Simpro or AroFlo, as buyers for an electrical wholesaler). Set evidence to "buyer_fit".
The counts are of BUSINESSES. If this company mainly sells to households or consumers, return an empty list unless it also clearly sells to businesses, and then pick only for that business side.
Be strict: fewer, defensible picks beat a full list. Skip generic office and IT tech (printers, phones, NAS, video conferencing) unless the company sells into exactly that. Return an empty list if nothing fits.

Also return company_name: the company's own name as shown on its website (not a product name, no legal suffix).

Respond with JSON only, no other text. Names must be copied exactly from the list:
{{"company_name": "...", "partners": [{{"name": "...", "relationship": "integrates|complementary", "evidence": "website|standard|buyer_fit", "why": "<one short sentence>"}}]}}"""

TOPUP_PROMPT = """You are helping find technologies for Firmable, which counts how many companies use each technology (software, platforms, OT/industrial systems, devices).

Company: {name} ({website})
What they do: {reason}

We need more competitors. These were already tried and should NOT be repeated: {tried}

- competitors: up to 5 more named products that directly compete with this company's offering, most direct first. Use product names, not parent company names. Return an empty list rather than guess.

Respond with JSON only, no other text:
{{"competitors": ["..."]}}"""

# Fills {copy} in the All Energy Australia 2026 email. The line before it asks how their team
# generates leads beyond events; the line after it asks for a chat at the event.
# Internal or generic tools the selection call kept letting through on the energy list. They stay in
# the partner columns for review but are never named in copy.
COPY_EXCLUDE = {
    "Microsoft Purview", "Avetta", "ISNetworld", "BloombergNEF", "Wood Mackenzie", "PTC Windchill",
    "Siemens Teamcenter", "Dassault Systemes", "Google Drive", "Laserfiche", "SAM.gov", "IBM TRIRIGA",
    "ServiceNow Software Asset Management", "Oracle Primavera P6 Enterprise Project Portfolio Management",
    "Microsoft Project", "ArcGIS StoryMaps", "Cisco Emergency Responder", "Veriforce",
}
COPY_VERSION = 9  # bump after editing COPY_PROMPT so cached copy is regenerated
FALLBACK_COPY = ("We're Firmable, a B2B contact database purpose-built for the ANZ market. We support sales "
                 "teams to create highly targeted prospect lists with verified contact details.")

# Closing idea appended by code (not the model) so Firmable's own claim is never hedged. Same
# meaning, varied wording; picked per domain so reruns are stable.
CLOSING_LINES = [
    "We also go past the company list to the decision-makers at each one, with verified emails and mobile numbers. Might be worth a look.",
    "And it doesn't stop at company-level data. We can show you who makes the buying call at each of these companies, with verified emails and phone numbers. Could be worth a look.",
    "Beyond the company list, we can point you to the key decision-makers at each one, with verified emails and direct dials. Could be worth exploring.",
    "From there, we can take you to the people who sign off on purchases at each company, with verified contact numbers. Might be worth a look.",
]

COPY_PROMPT = """You are writing one section of a cold email from Firmable, a B2B contact database built for the ANZ market, to {company}. The email is sent before the All Energy Australia 2026 conference.

The section sits between these two lines of a fixed template:
BEFORE: "Saw that {company} will be at tomorrow's All Energy Australia 2026 conference in Melbourne. Curious how your team is generating leads beyond events like this one?"
AFTER: "Our team will also be attending the event. Would you or a colleague from your team be up for a quick chat? Would love to drop by and share more on this!"
A closing sentence about Firmable's contact data is added after your text automatically. Do not write one.

About {company}: {what_they_do}
They sell to: {personas}

Technologies to mention, exactly these and no others (counts are numbers of companies running each one). Each has a kind, and the kind decides WHY the number matters to {company}:
{techs}

The three kinds:
- competitor: a product that competes with what {company} sells. Why it matters: companies running it already pay for this kind of product, so they are prospects to win over.
- integrates: something {company}'s products plug into or work with (a protocol, control system, platform). Why it matters: sites running it already have the setup {company}'s products fit into.
- buyer_signal: software that {company}'s own customers tend to run (e.g. job management software used by electrical contractors). It is NOT a competitor and NOT a partner, so never call it either. Why it matters: businesses running it are the type of business that buys from {company}, so the count is effectively a list of potential customers. Say who those businesses are (e.g. "installers", "fleet operators").

How to write it:
- Exactly two sentences per technology, no more:
  1. The guess, hedged ("I'm guessing", "I'd assume", "My hunch is", "I'd imagine", varied).
  2. The numbers, stated plainly, plus what they mean for you per the kind above, in a short clause. Give both the APAC and the North America count, copied exactly (with commas). Only the very first numbers sentence mentions "Firmable's tech intelligence dataset"; later ones just give the numbers.
- Guess wording must fit the kind: "come up against" / "compete" is only for competitors. For integrates, guess that your products integrate with or work with it, using those plain words (never "talk", "speak" or "plug into"). For buyer_signal, guess that the businesses you sell to run it.
- Two technologies of the same kind can share one guess sentence (e.g. "I'm guessing Hikvision and Axis are the brands you come up against most"), then one numbers sentence each.
- Paragraphs: one technology, or two of the same kind, = ONE paragraph. A competitor plus another kind = two paragraphs (competitors first).
- Do not restate a technology after its numbers sentence. Each number appears once.
- Write to the reader as "you" / "your", never "they". Australian English. Straight apostrophes (').
- Long product names can be shortened to what people call them (e.g. "Primavera P6", "Ignition", "Eaton").
- No em dashes or en dashes, no semicolons, no colons, no bold, no exclamation marks, no greeting or sign-off, no "leverage", "unlock", "seamless", "robust", "natural fit".

Examples (closing sentence omitted, it is added later):
---
[competitors Hikvision, Axis + integrates-style access control]
I'm guessing Hikvision and Axis are the brands you come up against most. Using Firmable's tech intelligence dataset, we found 2,053 companies across APAC running Hikvision and 3,175 in North America, all already paying for cameras. Axis adds 99 in APAC and 332 in North America.

I'd also assume your systems work alongside access control like Lenel S2. That's 169 sites in APAC and 328 in North America with the setup your cameras slot into.
---
[buyer_signal AroFlo for a solar wholesaler]
I'm guessing a lot of the installers you supply run their jobs on AroFlo. Using Firmable's tech intelligence dataset, we found 973 businesses across APAC on AroFlo and 132 in North America, which is a ready-made list of installers you could be selling to.
---
[integrates Modbus for an inverter maker]
I'd assume your inverters integrate with Modbus. Using Firmable's tech intelligence dataset, we found 5,639 companies across APAC running Modbus and 8,973 in North America, all sites where your gear would fit straight in.
---

Respond with JSON only, no other text:
{{"copy": "..."}}"""

SELECT_PROMPT = """You are vetting technologies before they go into a cold email to {company}. The email will say things like "I'm guessing <competitor> is one you come up against; we found N companies running it" and "I'd assume the people you sell to run <partner>; that's another N companies".

About {company}: {what_they_do}
They sell to: {personas}

Candidate competitors (most direct first):
{competitors}
Candidate partners (relationship: "integrates" = their products connect to it; "complementary" = companies running it are their likely buyers):
{partners}

A sales leader at {company} will read this. Keep a pick only if they would see straight away why those companies matter to them:
- Competitor: a product that genuinely competes with what they sell. Drop it if the name looks like a mismatch for their field (e.g. "3M 360 Encompass" is medical coding software, not a cable-management brand) or if it is a tool they would use rather than compete with (e.g. project planning software for a contractor).
- Partner: technology their buyers clearly run, or that their products clearly connect to. Drop generic business tools almost every company uses (file sharing like Google Drive, document management like Laserfiche, Microsoft products), tools they would use internally (planning, PLM/CAD like Dassault, compliance or contractor prequalification like Avetta, research or news subscriptions, government tender portals like SAM.gov, IT governance), products from an unrelated field, consumer framing (the counts are businesses, not households), another brand of the same product they make, and anything whose link to their buyers needs a long explanation. Judge each candidate on its own: if the first one fails, the next one is not automatically fine.
- Do not drop a real competitor just because it is a broad platform or the company is large (e.g. Schneider EcoStruxure for a grid automation vendor is fine).
Limits: up to 2 competitors in the given order. Partners: exactly 1 if any competitor is kept (the best one), otherwise up to 2. Keeping nothing is fine and better than a stretch.

Respond with JSON only, no other text:
{{"competitors": ["<exact name>"], "partners": ["<exact name>"]}}"""

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
    site_col = pick("website", "company_website", "domain", "domain_name", "company_domain", "url")
    # Firmable exports carry the ID inside "Firmable company link" (.../dashboard/company/<id>)
    id_col = pick("firmable_id", "firmable_company_id", "company_id", "id", "firmable_company_link",
                  "firmable_company_url")
    if not site_col:
        raise ValueError(f"Need a website/domain column. Found: {list(df.columns)}")
    log.info(f"Columns: name={name_col}, website={site_col}, firmable_id={id_col}")
    website = df[site_col].fillna("").astype(str).str.strip()
    # Name is optional: a URL-only list falls back to the domain, replaced later by the site's own name
    original = df[name_col].fillna("").astype(str).str.strip() if name_col else website.apply(_domain)
    out = pd.DataFrame({
        "company_name_original": original,
        "company_name": original.apply(normalize_name),
        "website": website,
        "firmable_id": df[id_col].fillna("").astype(str).str.strip().str.rstrip("/").str.split("/").str[-1]
                       if id_col else "",
    })
    return out[out["website"] != ""]


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
    raw = match.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Models occasionally emit stray backslashes (e.g. "\'"); escape any that aren't valid JSON escapes
        return json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw.replace("\\'", "'")))


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
    if firmable:
        try:
            if company["firmable_id"]:
                info = firmable.lookup_company_by_id(company["firmable_id"])
            else:
                info = firmable.lookup_company(domain=_domain(company["website"]))
            desc = (info or {}).get("description") or ""
            if desc.strip():
                return desc[:WEBSITE_CHAR_LIMIT], "firmable", []
        except Exception as e:
            log.warning(f"  [{company['company_name']}] Firmable lookup failed: {e}")
    return "", "none", []


def find_integrations_page(company: dict, links: list) -> tuple:
    """Return (page_markdown, url). Uses a homepage link if one looks like an integrations/partners
    page, else tries <domain>/integrations then <domain>/partners. Empty string if nothing usable."""
    dom = _domain(company["website"])
    # Trim deep links (e.g. /integrations/tesla/) back to the index page they sit under.
    # Only the company's own host counts: app-store links (play.google.com/store/apps/...) don't.
    def index_url(link):
        link = link.split("#")[0]
        m = INTEGRATIONS_LINK_RE.search(link)
        host = _domain(urlparse(link).netloc)
        if not m or not (host == dom or host.endswith("." + dom)):
            return None
        if m.group(4):  # integrations.<domain> style subdomain: use its root
            u = urlparse(link)
            return f"{u.scheme}://{u.netloc}/"
        return link[:m.end()].rstrip("?#")
    cands = sorted({u for u in map(index_url, links) if u}, key=lambda u: (("partner" in u.lower()), len(u)))
    tries = cands[:2] or [f"https://{dom}/integrations", f"https://{dom}/partners"]
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

def partner_candidates(counts: TechCounts, min_count: int, partner_max: int) -> tuple:
    """(prompt text grouped by category, set of names) for the partner step."""
    groups = {}
    for name, row in counts.rows.items():
        if row["category"] in PARTNER_CATEGORIES and min_count <= _best(counts, name) <= partner_max \
                and name not in GENERIC_PARTNERS:
            groups.setdefault(row["category"], []).append(name)
    text = "\n".join(f"{cat}: " + "; ".join(sorted(names)) for cat, names in groups.items())
    return text, {n for names in groups.values() for n in names}


def research(company: dict, counts: TechCounts, firmable: FirmableClient, candidates: tuple) -> dict:
    """Classify the company, pick competitors and match them to the counts CSV, then pick partners."""
    rec = {"domain": _domain(company["website"]), "company_type": "", "reason": "", "personas": "",
           "competitors": [], "partners": [], "matches": {}, "context_source": ""}
    context, source, links = get_context(company, firmable)
    rec["context_source"] = source
    if not context:
        rec["reason"] = "No website or Firmable description available"
        return rec

    data = _parse_json(ask_claude(RESEARCH_PROMPT.format(
        name=company["company_name"], website=company["website"], context=context,
        types=" / ".join(COMPANY_TYPES))))
    rec["company_type"] = data.get("company_type") if data.get("company_type") in COMPANY_TYPES else "Other"
    rec["reason"] = (data.get("what_they_do") or "").strip()
    rec["brand_name"] = (data.get("brand_name") or "").strip()
    rec["personas"] = (data.get("personas") or "").strip()
    rec["competitors"] = [c for c in (data.get("competitors") or []) if c][:5]
    rec["matches"] = match_products(rec["competitors"], counts, "competitors", rec["reason"])
    research_partners(company, rec, context, links, candidates)
    return rec


def research_partners(company: dict, rec: dict, context: str, links: list, candidates: tuple):
    """v2 step: pick partners straight from the tracked-technology list, each labelled integrates /
    complementary with a reason. Mutates rec and sets rec["v"] = REC_VERSION."""
    text, names = candidates
    rec["partners"], rec["partner_info"] = [], {}
    rec["v"] = REC_VERSION
    # Every business buys electricity, so no technology predicts a retailer's buyers; the model
    # only stretches here (e.g. "Simpro users need power"), so skip rather than invent a pool
    if rec["company_type"] == RETAILER:
        return
    page, url = find_integrations_page(company, [l for l in links if INTEGRATIONS_LINK_RE.search(l)])
    rec["integrations_url"] = url
    data = _parse_json(ask_claude(PARTNER_PROMPT.format(
        name=company["company_name"], website=company["website"], company_type=rec["company_type"],
        reason=rec["reason"], personas=rec["personas"], competitors=", ".join(rec["competitors"]) or "none",
        context=context, source=url or "no integrations page found", integrations=page or "(none)",
        candidates=text)))
    rec["site_name"] = (data.get("company_name") or "").strip() or rec.get("site_name", "")
    for p in data.get("partners") or []:
        name = (p.get("name") or "").strip()
        # Guard against names outside the list (the list only holds exact TECHNOLOGY_NAMEs)
        if name in names and name not in rec["partners"] and p.get("relationship") in RELATIONSHIPS:
            rec["partners"].append(name)
            rec["matches"][name] = name
            rel = p["relationship"] + (f" ({p['evidence']})" if p["relationship"] == "integrates" and p.get("evidence") else "")
            rec["partner_info"][name] = {"relationship": rel, "why": (p.get("why") or "").strip()}
        elif name:
            log.info(f"  [{company['company_name']}] partner pick dropped (not in list): {name}")
    rec.pop("partner_source", None)


def _best(counts: TechCounts, name: str) -> int:
    return max(counts.count_in(name, US_COL), counts.count_in(name, APAC_COL))


def usable_picks(rec: dict, counts: TechCounts, min_count: int, partner_max: int) -> tuple:
    """(competitors, partners) as matched CSV names, in the model's relevance order.
    A pick needs >= min_count companies in US or APAC; partners also must be <= partner_max
    there and not generic or the company's own product."""
    def ranked(names, ok, exclude=()):
        matched = []
        for n in names:
            m = rec["matches"].get(n)
            if m and m not in matched and m not in exclude and ok(m):
                matched.append(m)
        return matched

    own = re.sub(r"[^a-z]", "", rec.get("domain", "").split(".")[0])
    is_own = lambda m: bool(own) and len(own) >= 4 and own in re.sub(r"[^a-z]", "", m.lower())
    comps = ranked(rec["competitors"], lambda m: _best(counts, m) >= min_count and not is_own(m))
    parts = ranked(rec.get("partners", []),
                   lambda m: min_count <= _best(counts, m) <= partner_max and m not in GENERIC_PARTNERS
                   and not is_own(m), exclude=comps)
    return comps, parts


def unmatched(names: list, usable: list, rec: dict, counts: TechCounts) -> str:
    """Suggested names not shown in the 1-3 columns: not tracked, filtered out, or usable but past the top 3."""
    out = []
    for n in names:
        m = rec["matches"].get(n)
        if not m:
            out.append(f"{n} (not tracked)")
        elif m not in usable[:3]:
            status = "also fits" if m in usable else "filtered"
            out.append(f"{n} (US {counts.count_in(m, US_COL):,} / APAC {counts.count_in(m, APAC_COL):,}, {status})")
    return "; ".join(out)


def top_up(company: dict, rec: dict, counts: TechCounts):
    """One extra LLM call for more competitors when fewer than 2 matched. Mutates rec."""
    tried = rec["competitors"] + rec.get("partners", [])
    data = _parse_json(ask_claude(TOPUP_PROMPT.format(
        name=company["company_name"], website=company["website"], reason=rec["reason"],
        tried=", ".join(tried) or "none")))
    new_c = [c for c in (data.get("competitors") or []) if c and c not in tried][:5]
    rec["competitors"] += new_c
    rec["matches"].update(match_products(new_c, counts, "competitors", rec["reason"]))


def _name_fits_domain(name: str, domain: str) -> bool:
    """True if any 3+ letter word of the name (or the whole name squashed) appears in the domain root."""
    root = re.sub(r"[^a-z]", "", domain.split(".")[0])
    words = re.findall(r"[a-z]{3,}", name.lower())
    return bool(root) and (any(w in root for w in words) or re.sub(r"[^a-z]", "", name.lower()) in root)


def final_name(company: dict, rec: dict) -> str:
    """Input name, swapped for the name read off the website when the input name is long (3+ words),
    missing (URL-only input) or doesn't match the domain."""
    name = company["company_name"]
    dom = _domain(company["website"])
    site = rec.get("site_name") or rec.get("brand_name") or ""
    no_name = company["company_name_original"] == dom
    if site and (no_name or len(name.split()) >= 3 or not _name_fits_domain(name, dom)):
        return normalize_name(site)
    return name


def fit_verdict(comps: list, parts: list, counts: TechCounts) -> tuple:
    """(outreach_fit, fit_note). Strong = 2+ usable picks, Weak = 1, None = 0."""
    picks = comps + parts
    if not picks:
        return "None", "No suggested competitor or partner is tracked by Firmable above the minimum count"
    top = max(picks, key=lambda m: _best(counts, m))
    note = (f"{len(comps)} competitor(s), {len(parts)} partner(s) tracked; largest pool: {top} "
            f"(US {counts.count_in(top, US_COL):,} / APAC {counts.count_in(top, APAC_COL):,})")
    return ("Strong" if len(picks) >= 2 else "Weak"), note


def build_row(company: dict, rec: dict, counts: TechCounts, args) -> dict:
    row = {c: "" for c in OUTPUT_COLUMNS}
    row.update(company_name=final_name(company, rec), company_name_original=company["company_name_original"],
               website=company["website"], firmable_id=company["firmable_id"],
               company_type=rec.get("company_type", ""), what_they_do=rec.get("reason", ""),
               personas=rec.get("personas", ""), integrations_url=rec.get("integrations_url", ""))
    if not rec.get("company_type"):
        row["outreach_fit"], row["fit_note"] = "None", rec.get("reason", "")
        return row
    comps, parts = usable_picks(rec, counts, args.min_count, args.partner_max)
    for kind, picks in (("competitor", comps), ("partner", parts)):
        for i, m in enumerate(picks[:3], 1):
            row[f"{kind}{i}"] = m
            row[f"{kind}{i}_us_count"] = f"{counts.count_in(m, US_COL):,}"
            row[f"{kind}{i}_apac_count"] = f"{counts.count_in(m, APAC_COL):,}"
    for i, m in enumerate(parts[:3], 1):
        info = rec.get("partner_info", {}).get(m, {})
        row[f"partner{i}_relationship"], row[f"partner{i}_why"] = info.get("relationship", ""), info.get("why", "")
    row["competitors_unmatched"] = unmatched(rec["competitors"], comps, rec, counts)
    row["partners_unmatched"] = unmatched(rec.get("partners", []), parts, rec, counts)
    row["outreach_fit"], row["fit_note"] = fit_verdict(comps[:3], parts[:3], counts)
    if rec["company_type"] == RETAILER:
        row["fit_note"] += "; partner step skipped for energy retailers (every business buys power)"
    return row


def _row_picks(row: dict, kind: str) -> dict:
    """{name: (apac_count, us_count)} for the competitor/partner columns of a row, as formatted strings,
    minus COPY_EXCLUDE."""
    return {row[f"{kind}{i}"]: (row[f"{kind}{i}_apac_count"], row[f"{kind}{i}_us_count"])
            for i in (1, 2, 3) if row[f"{kind}{i}"] and row[f"{kind}{i}"] not in COPY_EXCLUDE}


def _check_copy(text: str, comps: dict, parts: dict, all_names: list) -> str:
    """Problems with a generated copy block ("" if fine): numbers that are not the exact counts of the
    selected picks, missing or repeated counts, dashes."""
    if re.search("[\u2013\u2014]", text):
        return "contains an em/en dash"
    allowed = {c for picks in (comps, parts) for pair in picks.values() for c in pair}
    # Product names carry digits (ServiceM8, Dynamics 365, 3M 360); drop them before reading numbers
    bare = text
    for n in sorted(all_names, key=len, reverse=True):
        bare = bare.replace(n, " ")
    numbers = [m.rstrip(",") for m in re.findall(r"(?<![\w.])\d[\d,]*", bare)]
    found = set(numbers)
    if len(numbers) != len(found):
        return "a number is repeated"
    if found - allowed:
        return f"numbers that are not counts of the listed technologies: {sorted(found - allowed)}"
    if allowed - found:
        return f"counts missing from the copy: {sorted(allowed - found)}"
    return ""


def _check_shape(text: str, n_techs: int, paragraphs: int, company: str, has_comps: bool) -> str:
    """Padding and framing checks: two sentences per technology at most, the expected paragraph count,
    "Firmable's tech intelligence dataset" once, no third person, no competitor framing without a competitor."""
    if text.count("Firmable's tech intelligence dataset") != 1:
        return "mention \"Firmable's tech intelligence dataset\" exactly once, in the first numbers sentence only"
    if re.search(r"\b(talks?|speaks?|plugs? into)\b", text, re.IGNORECASE):
        return 'uses "talk", "speak" or "plug into"; say "integrate with" or "work with" instead'
    if re.search(rf"\b{re.escape(company)}\b", text):
        return f"refers to {company} by name; write to them as \"you\" / \"your\""
    if not has_comps and re.search(r"come up against|up against|compet", text, re.IGNORECASE):
        return "uses competitor framing but none of these technologies is a competitor"
    sentences = [x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x]
    if len(sentences) > 2 * n_techs:
        return f"{len(sentences)} sentences for {n_techs} technologies; write exactly two per technology, no extra sentences"
    if len([x for x in text.split("\n\n") if x.strip()]) > max(paragraphs, 2):
        return f"use at most {max(paragraphs, 2)} paragraphs"
    return ""


def write_copy(row: dict, counts: TechCounts) -> dict:
    """{copy, copy_competitors, copy_partners, copy_error} for the {copy} slot of the event email.
    Two calls: a strict selection of which picks are worth naming, then the writing. Fixed fallback
    when nothing survives selection; one retry with feedback if the written copy fails the check."""
    comps, parts = _row_picks(row, "competitor"), _row_picks(row, "partner")
    fallback = {"copy": FALLBACK_COPY, "copy_competitors": "", "copy_partners": "", "copy_error": ""}
    if not comps and not parts:
        return fallback
    rel = {row[f"partner{i}"]: f"{row[f'partner{i}_relationship']}: {row[f'partner{i}_why']}" for i in (1, 2, 3)}
    kind = {row[f"partner{i}"]: ("integrates" if row[f"partner{i}_relationship"].startswith("integrates")
                                 else "buyer_signal") for i in (1, 2, 3)}
    fmt = lambda picks, with_counts: "\n".join(
        f"- {n} (category: {counts.rows.get(n, {}).get('category', '')})"
        + (f": APAC {a}, North America {u}" if with_counts else "")
        + (f" [{rel[n]}]" if n in rel else "")
        for n, (a, u) in picks.items()) or "(none)"
    info = dict(company=row["company_name"], what_they_do=row["what_they_do"], personas=row["personas"])

    sel = _parse_json(ask_claude(SELECT_PROMPT.format(**info, competitors=fmt(comps, False), partners=fmt(parts, False))))
    keep_c = [n for n in (sel.get("competitors") or []) if n in comps][:2]
    keep_p = [n for n in (sel.get("partners") or []) if n in parts][:1 if keep_c else 2]
    if not keep_c and not keep_p:
        return dict(fallback, copy_error="no pick survived selection; fallback used")
    comps, parts_all, parts = {n: comps[n] for n in keep_c}, parts, {n: parts[n] for n in keep_p}

    techs = "\n".join([f"- {n} (kind: competitor): APAC {a}, North America {u}" for n, (a, u) in comps.items()]
                      + [f"- {n} (kind: {kind[n]}): APAC {a}, North America {u}" for n, (a, u) in parts.items()])
    prompt = COPY_PROMPT.format(**info, techs=techs)
    problem = ""
    for _ in range(3):
        data = _parse_json(ask_claude(prompt + (f"\n\nYour previous attempt was rejected: {problem}. Fix it." if problem else "")))
        text = (data.get("copy") or "").replace("\u2019", "'").replace("\u2018", "'").strip()
        # Single line breaks inside a paragraph become spaces; blank lines stay paragraph breaks
        text = "\n\n".join(re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip())
        problem = (_check_copy(text, comps, parts, list(comps) + list(parts_all))
                   or _check_shape(text, n_techs=len(comps) + len(parts), paragraphs=2 if comps and parts else 1,
                                   company=row["company_name"], has_comps=bool(comps))
                   if text else "empty copy")
        if not problem:
            # Joins the last paragraph when there are two; becomes its own paragraph after a single one
            text += ("\n\n" if "\n\n" not in text else " ") + CLOSING_LINES[sum(map(ord, row["website"])) % len(CLOSING_LINES)]
            return {"copy": text, "copy_competitors": "; ".join(keep_c), "copy_partners": "; ".join(keep_p),
                    "copy_error": ""}
    log.warning(f"  [{row['company_name']}] copy rejected 3 times: {problem}")
    return {"copy": "", "copy_competitors": "; ".join(keep_c), "copy_partners": "; ".join(keep_p),
            "copy_error": problem}


def add_copy(row: dict, rec: dict, counts: TechCounts) -> bool:
    """Fill the copy columns, reusing rec["copy"] when the picks haven't changed. True if rec changed."""
    sig = json.dumps([COPY_VERSION, _row_picks(row, "competitor"), _row_picks(row, "partner")])
    cached = rec.get("copy")
    if cached and cached.get("sig") == sig and not cached["out"]["copy_error"]:
        row.update(cached["out"])
        return False
    try:
        out = write_copy(row, counts)
    except Exception as e:
        log.error(f"  [{row['company_name']}] copy failed: {e}")
        out = {"copy": "", "copy_competitors": "", "copy_partners": "", "copy_error": f"Error: {e}"}
    row.update(out)
    rec["copy"] = {"sig": sig, "out": out}
    return True


def process(company: dict, cache: dict, counts: TechCounts, firmable, args) -> dict:
    dom = _domain(company["website"])
    rec = cache.get(dom) if dom else None
    try:
        dirty = False
        if rec is None:
            rec = research(company, counts, firmable, args.candidates)
            dirty = True
        elif rec.get("company_type") and rec.get("v") != REC_VERSION:
            # v1 records keep their competitors; only the partner step is redone (needs a fresh scrape)
            context, _, links = get_context(company, firmable)
            research_partners(company, rec, context, links, args.candidates)
            dirty = True
        # Short on competitors: one top-up call per domain (topped_up is cached so reruns don't repeat it)
        if rec.get("company_type") and not rec.get("topped_up"):
            comps, _ = usable_picks(rec, counts, args.min_count, args.partner_max)
            if len(comps) < 2:
                top_up(company, rec, counts)
                rec["topped_up"] = True
                dirty = True
        row = build_row(company, rec, counts, args)
        if not args.no_copy and add_copy(row, rec, counts):
            dirty = True
        # Don't cache "no content" so a flaky site gets retried next run
        if dirty and dom and rec["context_source"] != "none":
            _append_cache(rec)
        return row
    except Exception as e:
        log.error(f"  [{company['company_name']}] research failed: {e}")
        rec = {"domain": dom, "reason": f"Error: {e}", "competitors": [], "matches": {}}
    return build_row(company, rec, counts, args)


def print_summary(out: pd.DataFrame, counts: TechCounts):
    print(f"  Outreach fit:  " + ", ".join(f"{k} {v}" for k, v in out["outreach_fit"].value_counts().items()))
    print(f"  Company type:  " + ", ".join(f"{k} {v}" for k, v in out["company_type"].replace("", "(no data)")
                                          .value_counts().items()))
    for kind in ("competitor", "partner"):
        tally = Counter(m for i in (1, 2, 3) for m in out[f"{kind}{i}"] if m)
        if tally:
            print(f"  Most common {kind}s:")
            for m, n in tally.most_common(10):
                print(f"    {n:>3} x {m}  (US {counts.count_in(m, US_COL):,} / APAC {counts.count_in(m, APAC_COL):,})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path)
    ap.add_argument("--counts", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--min-count", type=int, default=100,
                    help="A pick needs at least this many companies in US or APAC")
    ap.add_argument("--partner-max", type=int, default=150000,
                    help="Partners above this many companies (US or APAC) are too generic")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-copy", action="store_true", help="Skip writing the email copy column")
    args = ap.parse_args()

    counts_path = args.counts or _find_latest(list(INPUT_DIR.glob(COUNTS_GLOB)), "technology counts CSV")
    input_path = args.input or _find_latest(
        [p for p in list(INPUT_DIR.glob("*.csv")) + list(INPUT_DIR.glob("*.xlsx"))
         if not p.match(COUNTS_GLOB)], "company CSV/XLSX")
    output_path = args.output or OUTPUT_DIR / f"tech_intel_{input_path.stem}.csv"

    log.info(f"Counts: {counts_path.name}")
    counts = TechCounts(counts_path, count_col=US_COL, extra_cols=(APAC_COL,))
    log.info(f"  {len(counts.rows):,} technologies loaded")
    args.candidates = partner_candidates(counts, args.min_count, args.partner_max)
    log.info(f"  {len(args.candidates[1]):,} offered to the partner step ({', '.join(PARTNER_CATEGORIES)})")
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

    print(f"\nBatch {args.start + 1}-{end} complete -> {output_path}")
    print(f"File total: {len(out)} companies")
    print_summary(out, counts)


if __name__ == "__main__":
    main()
