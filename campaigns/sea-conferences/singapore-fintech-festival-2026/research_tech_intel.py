"""
Tech intel research for the eligible SFF 2026 exhibitors (step 1 of the tech intel page).

For each eligible company in output/hubspot_check.csv:
  1. Context: Firecrawl homepage, else the Firmable company description.
  2. One Claude call: bucket (saas / services / na), one-line description, up to 3
     competitors and up to 3 integrations or partner platforms, each with a reason.
  3. Match pick names to the Firmable technology counts CSV (scripts/tech_matcher.TechCounts):
     exact match, else shortlist + one LLM confirm call. Unmatched names are kept for reference.
  4. Keep up to 2 competitors + 2 integrations/partners with a global count >= --min-count,
     excluding the company's own products.

Outputs (output/, gitignored):
  tech_intel_research.jsonl  one record per company (also the cache; delete a line to redo it)
  tech_list.txt              unique matched technologies, input for the Firmable MCP count step

ANZ and SG+MY counts are NOT fetched here: they need the Firmable MCP (filter_search with
tech_intelligence + hq_country), which Python can't call. See CLAUDE.md, step 2.

Run from repo root:
    PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/research_tech_intel.py --count 10
    PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/research_tech_intel.py
"""

import argparse
import csv
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

from scripts.ai import ask_claude
from scripts.firmable_api import FirmableClient
from scripts.tech_matcher import TechCounts, normalise

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
REPO = HERE.parents[2]
DEFAULT_COUNTS = REPO / "campaigns/anz/tech-intel-outbound/input/technology_companies_by_region_90d_2026-10-16-0950.csv"
CACHE = OUT / "tech_intel_research.jsonl"
TECH_LIST = OUT / "tech_list.txt"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
CONTEXT_CHARS = 6000
CACHE_VERSION = 1

RESEARCH_PROMPT = """You are preparing a battlecard for Firmable SDRs. Firmable is a B2B data platform that can count how many companies use a given technology (technographics). The SDR pitch to an exhibitor at the Singapore FinTech Festival is: "Firmable maps N companies running <technology>", where the technology is either a competitor of the exhibitor (companies already paying for this kind of product) or a technology the exhibitor integrates with or delivers (companies that are a natural fit for what they sell).

Exhibitor: {name} ({website})
Focus area listed by the event: {category}
HQ country: {country}

Website / description text:
---
{context}
---

Return JSON only:
{{
  "bucket": "saas" | "services" | "na",
  "description": "<one plain sentence, max 20 words, what they do and for whom>",
  "competitors": [{{"name": "<product>", "reason": "<max 14 words>"}}],
  "integrations": [{{"name": "<product>", "kind": "integration" | "partner", "reason": "<max 14 words>"}}]
}}

Rules:
- bucket: "saas" = sells its own software/platform/API (payments, KYC, regtech, core banking, wealthtech, crypto infra, data, AI). "services" = consultancy, systems integrator, MSP, law/accounting firm, outsourcer, bank or broker selling financial services. "na" = government, regulator, central bank, trade/investment agency, country or city pavilion, association, university, media, or an events/talent body. For "na", return empty competitors and integrations.
- competitors: up to 3 named commercial software products that compete directly with this company's main product, most direct first. Prefer well-known vendors that a website technology scanner can detect (e.g. Stripe, Adyen, Checkout.com, Jumio, Onfido, Sumsub, Fireblocks, Temenos, Mambu, Salesforce Financial Services Cloud). Never list the company itself.
- integrations: up to 3 named technologies this company integrates with, is built on, or (for services firms) implements/resells. Use kind "integration" for software vendors, "partner" for services firms delivering that platform. Prefer specific ones (card networks, payment gateways, core banking, CRMs, identity providers) over generic platforms everyone uses (AWS, Microsoft 365, Google Workspace) unless nothing else fits.
- Use exact product names. Do not invent products. If unsure, return fewer."""

CONFIRM_PROMPT = """You are matching product names to entries in a technology database.

Context: the queries are {role} of this company: {context}

For each query product below, pick the ONE candidate that is the same product from the same vendor (or that vendor's core/main product listing). If no candidate is clearly the same product, return null. Do not pick a different product that merely shares a word or an abbreviation; for short or ambiguous names, only match when the candidate's category fits the context.

{blocks}

Respond with JSON only, mapping each query exactly as written to the chosen candidate string or null:
{{"<query>": "<candidate or null>"}}"""

# Counts-CSV entries the matcher picked that are a different product with the same name, or not a
# product at all (regulators, standards). Reviewed by hand on the SFF 2026 run; extend as needed.
BAD_MATCHES = {
    "Copper CRM",        # "Copper" the crypto custodian
    "RAMP",              # Ramp Network crypto on-ramp; this entry is a media tool
    "BASE",              # Coinbase's Base chain
    "Jade",
    "Recharge",          # airtime top-up; this entry is the Shopify subscription app
    "Kiosked",
    "Samsung Printer",
    "Encompass",         # mortgage software, not Encompass KYC
    "FinCEN",            # regulator
    "ISO 20022",         # messaging standard
    "Calendly",
    "Google Analytics",
    "Apple App Store",
    "Fiddler",           # HTTP debugging proxy, not Fiddler AI (no Fiddler AI row in the counts CSV)
    "Circle",            # community platform, not Circle (USDC)
    "Elliptic",          # count includes unrelated sites; not reliably the crypto-compliance vendor
}

# Counts-CSV entries that are the wrong product, with the right entry for what the model meant.
REMAP = {
    "Swift": "SWIFTNet",  # "Swift" is the Apple programming language; the bank network is SWIFTNet
}

_cache_lock = threading.Lock()


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object in model response: {text[:200]}")
    raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw.replace("\\'", "'")))


def bare_domain(url: str) -> str:
    return re.sub(r"^(https?://)?(www\.)?", "", (url or "").strip().lower()).split("/")[0]


def firecrawl(url: str) -> str:
    if not FIRECRAWL_API_KEY:
        raise ValueError("FIRECRAWL_API_KEY is not set in .env")
    url = url if url.startswith("http") else f"https://{url}"
    r = requests.post(FIRECRAWL_SCRAPE_URL, headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
                      json={"url": url, "formats": ["markdown"], "onlyMainContent": True}, timeout=45)
    r.raise_for_status()
    return r.json().get("data", {}).get("markdown") or ""


def get_context(c: dict, fm: FirmableClient) -> tuple:
    try:
        text = firecrawl(c["website"])
        if len(text.strip()) > 200:
            return text[:CONTEXT_CHARS], "firecrawl"
    except Exception as e:
        log.warning(f"  [{c['name']}] Firecrawl failed for {c['website']}: {e}")
    try:
        info = fm.lookup_company_by_id(c["firmable_id"]) if c["firmable_id"] else fm.lookup_company(domain=c["domain"])
        desc = (info or {}).get("description") or ""
        if desc.strip():
            return desc[:CONTEXT_CHARS], "firmable"
    except Exception as e:
        log.warning(f"  [{c['name']}] Firmable lookup failed: {e}")
    return "", "none"


def match_names(names: list, counts: TechCounts, role: str, context: str) -> dict:
    result, pending = {}, {}
    for n in names:
        hit = counts.exact(n)
        if hit:
            result[n] = hit
        else:
            sl = counts.shortlist(n)
            if sl:
                pending[n] = sl
            else:
                result[n] = None
    if pending:
        blocks = "\n\n".join(
            f"Query: {q}\nCandidates:\n" + "\n".join(f"- {c} (category: {counts.rows[c]['category']})" for c in cands)
            for q, cands in pending.items())
        chosen = parse_json(ask_claude(CONFIRM_PROMPT.format(blocks=blocks, role=role, context=context or "n/a")))
        for q, cands in pending.items():
            pick = chosen.get(q)
            result[q] = pick if pick in cands else None
    return result


def is_own(tech: str, c: dict) -> bool:
    t = normalise(tech)
    sld = c["domain"].split(".")[0]
    brand = normalise(c["name"]).split(" ")[0] if normalise(c["name"]) else ""
    return bool((sld and len(sld) > 2 and sld in t.replace(" ", "")) or (brand and len(brand) > 2 and brand in t.split(" ")))


def research(c: dict, counts: TechCounts, fm: FirmableClient, min_count: int) -> dict:
    context, source = get_context(c, fm)
    rec = {"v": CACHE_VERSION, "domain": c["domain"], "name": c["name"], "context_source": source,
           "bucket": "na", "description": "", "picks": [], "unmatched": [], "error": ""}
    if not context:
        rec["error"] = "no website or Firmable text"
    data = parse_json(ask_claude(RESEARCH_PROMPT.format(
        name=c["name"], website=c["website"], category=c["category"] or "n/a",
        country=c["hq_country"] or c["country"] or "n/a", context=context or "(no text available; use what you know about this company, or return fewer picks)")))
    rec["bucket"] = data.get("bucket") if data.get("bucket") in ("saas", "services", "na") else "na"
    rec["description"] = (data.get("description") or "").strip()
    if rec["bucket"] == "na":
        return rec

    comps = [x for x in data.get("competitors", []) if x.get("name")][:3]
    ints = [x for x in data.get("integrations", []) if x.get("name")][:3]
    desc = f"{c['name']}: {rec['description']}"
    cm = match_names([x["name"] for x in comps], counts, "competitors", desc) if comps else {}
    im = match_names([x["name"] for x in ints], counts, "integration partners", desc) if ints else {}

    seen = set()

    def take(items, mapping, kind_of, limit):
        out = []
        for x in items:
            m = mapping.get(x["name"])
            m = REMAP.get(m, m)
            ok = m and m not in seen and m not in BAD_MATCHES and counts.count(m) >= min_count and not is_own(m, c)
            if not ok:
                rec["unmatched"].append(f"{x['name']} ({'not tracked' if not m else 'filtered'})")
                continue
            seen.add(m)
            out.append({"tech": m, "kind": kind_of(x), "reason": (x.get("reason") or "").strip(),
                        "global": counts.count(m), "apac": counts.count_in(m, "APAC_MATCHING"),
                        "category": counts.rows[m]["category"]})
            if len(out) == limit:
                break
        return out

    rec["picks"] = take(comps, cm, lambda x: "competitor", 2) + take(
        ints, im, lambda x: "partner" if (x.get("kind") == "partner" or rec["bucket"] == "services") else "integration", 2)
    return rec


def load_cache(counts: TechCounts = None) -> dict:
    if not CACHE.exists():
        return {}
    out = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("v") == CACHE_VERSION and not r.get("error", "").startswith("exception"):
                if counts:
                    for p in r["picks"]:
                        new = REMAP.get(p["tech"])
                        if new and new in counts.rows:
                            p.update(tech=new, **{"global": counts.count(new), "apac": counts.count_in(new, "APAC_MATCHING"),
                                                 "category": counts.rows[new]["category"]})
                bad = [p["tech"] for p in r["picks"] if p["tech"] in BAD_MATCHES]
                if bad:
                    r["picks"] = [p for p in r["picks"] if p["tech"] not in BAD_MATCHES]
                    r["unmatched"] = r.get("unmatched", []) + [f"{t} (bad match)" for t in bad]
                out[r["domain"]] = r
    return out


def append_cache(rec: dict):
    with _cache_lock, open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_eligible() -> list:
    ex = list(csv.DictReader(open(OUT / "exhibitors.csv", encoding="utf-8")))
    hs = list(csv.DictReader(open(OUT / "hubspot_check.csv", encoding="utf-8")))
    if len(ex) != len(hs):
        raise SystemExit(f"exhibitors.csv ({len(ex)}) and hubspot_check.csv ({len(hs)}) row counts differ; can't join by row")
    seen, rows = set(), []
    for e, h in zip(ex, hs):
        key = (h["company_name"], h["company_website"])
        if key in seen or h["status"] != "Eligible":
            seen.add(key)
            continue
        seen.add(key)
        rows.append({
            "name": h["company_name"], "website": e["website"] or h["company_website"],
            "domain": bare_domain(e["website"] or h["company_website"]),
            "firmable_id": h["firmable_id"], "hq_country": h["hq_country"], "country": e["country"],
            "category": e["category"],
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", type=Path, default=DEFAULT_COUNTS)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--min-count", type=int, default=100, help="Minimum GLOBAL_MATCHING for a pick")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    counts = TechCounts(args.counts, count_col="GLOBAL_MATCHING", extra_cols=("APAC_MATCHING",))
    fm = FirmableClient()
    companies = load_eligible()
    batch = companies[args.start: args.start + args.count if args.count else None]
    cache = load_cache()
    todo = [c for c in batch if c["domain"] not in cache]
    log.info(f"{len(companies)} eligible | batch {len(batch)} | {len(batch) - len(todo)} cached | researching {len(todo)}")

    def work(c):
        try:
            rec = research(c, counts, fm, args.min_count)
        except Exception as e:
            log.error(f"  [{c['name']}] research failed: {e}")
            rec = {"v": CACHE_VERSION, "domain": c["domain"], "name": c["name"], "bucket": "na",
                   "description": "", "picks": [], "unmatched": [], "error": f"exception: {e}"}
        append_cache(rec)
        log.info(f"  {c['name']}: {rec['bucket']} | " + ", ".join(f"{p['kind'][0].upper()}:{p['tech']}" for p in rec["picks"]))
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, todo))

    cache = load_cache(counts)
    # Rewrite the cache compacted (one line per domain, blocklist applied) so later steps read clean records
    with _cache_lock, open(CACHE, "w", encoding="utf-8") as f:
        for r in cache.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    techs = sorted({p["tech"] for r in cache.values() for p in r["picks"]})
    TECH_LIST.write_text("\n".join(techs) + "\n", encoding="utf-8")
    done = sum(1 for c in companies if c["domain"] in cache)
    errs = sum(1 for r in cache.values() if r.get("error"))
    log.info(f"\nDone: {done}/{len(companies)} researched | {errs} with errors/notes | {len(techs)} unique technologies -> {TECH_LIST}")


if __name__ == "__main__":
    main()
