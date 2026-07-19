"""
Scrape HP Reseller Locator (AU) and enrich with LinkedIn URLs via Firmable.

Phase 1: Playwright browser automation — navigate HP locator, intercept JSON API
         responses, extract all AU partner companies.
Phase 2: Firmable enrichment — look up each company by domain to get LinkedIn URL.

Usage:
    PYTHONPATH=. python3 campaigns/anz/hp-reseller-locator/scrape_and_enrich.py
"""

import asyncio
import csv
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import base64 as _base64
import requests as _requests

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

from scripts.firmable_api import FirmableClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "hp_partners.csv"

HP_LOCATOR_URL = "https://locator.hp.com/au/en/?ml___lang=en-GB%20(1)&ml___region=SG&ml___cont=APJ"
METALOCATOR_IFRAME_URL = (
    "https://hp.metalocator.com/index.php?option=com_locator&view=directory"
    "&layout=combined_bootstrap&Itemid=19331&tmpl=component&framed=1&source=js"
    "&lang=en-GB%20%281%29&region=AU&cont=APJ&params_detected=1"
)

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

FIELDNAMES = [
    "company_name", "website", "domain", "address", "phone",
    "hp_partner_type", "linkedin_url", "linkedin_source", "firmable_id",
]

# Candidate field names for flexible parsing of HP API responses
NAME_FIELDS    = {"name", "company", "companyname", "storename", "dealername", "partnerName"}
WEBSITE_FIELDS = {"website", "url", "web", "siteurl", "homepage", "companywebsite", "websiteUrl"}
PHONE_FIELDS   = {"phone", "tel", "telephone", "phonenumber", "phoneNumber"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    netloc = urlparse(url).netloc
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def extract_field(record: dict, candidates: set) -> str:
    """Case-insensitive field lookup from a dict against a set of candidate names."""
    candidates_lower = {c.lower() for c in candidates}
    for key in record:
        if key.lower() in candidates_lower:
            val = record[key]
            if isinstance(val, str):
                return val.strip()
    return ""


def looks_like_company_list(data) -> bool:
    """True if data is a list of dicts that look like partner/company records.

    Requires at least 5 items (to rule out small config blobs) and that sample
    records have a name-like field whose values are non-trivial strings.
    """
    if not isinstance(data, list) or len(data) < 5:
        return False
    sample = data[0]
    if not isinstance(sample, dict):
        return False
    keys_lower = {k.lower() for k in sample.keys()}
    name_hit = bool({c.lower() for c in NAME_FIELDS} & keys_lower)
    if not name_hit:
        return False
    # Verify the name value looks like a real company name (>3 chars, not a short code)
    name_val = extract_field(sample, NAME_FIELDS)
    return len(name_val) > 3


def find_company_list(data):
    """Recursively search a JSON blob for a company-like array."""
    # GeoJSON FeatureCollection — HP map locators often use this format
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if features:
            records = []
            for feature in features:
                props = feature.get("properties") or {}
                if props and any(k.lower() in {c.lower() for c in NAME_FIELDS} for k in props):
                    # Embed lat/lng from geometry so address parsing can use them
                    geom = feature.get("geometry") or {}
                    coords = geom.get("coordinates", [])
                    if len(coords) == 2:
                        props = {**props, "_lng": coords[0], "_lat": coords[1]}
                    records.append(props)
            if records:
                return records

    if looks_like_company_list(data):
        return data

    if isinstance(data, dict):
        for val in data.values():
            result = find_company_list(val)
            if result:
                return result

    return None


def parse_company(record: dict) -> dict:
    """Normalise a raw MetaLocator/HP locator record into standard output columns.

    MetaLocator field names: name, link (website), phone, address, city, state,
    postalcode, country, type (partner tier), taglist (capabilities).
    """
    name = record.get("name") or extract_field(record, NAME_FIELDS)

    # MetaLocator uses "link" for website
    website = record.get("link") or extract_field(record, WEBSITE_FIELDS)
    # Ensure website has a protocol for normalize_domain to work correctly
    if website and not website.startswith("http"):
        website_with_proto = "https://" + website
    else:
        website_with_proto = website

    phone = record.get("phone") or extract_field(record, PHONE_FIELDS)

    # Build address from MetaLocator sub-fields
    addr_parts = []
    for f in ("address", "address1", "address2", "city", "state", "postalcode", "zip"):
        val = str(record.get(f, "")).strip()
        if val:
            addr_parts.append(val)
    address = ", ".join(addr_parts)

    partner_type = (
        record.get("type") or record.get("partnerType") or
        record.get("dealerType") or record.get("tier") or ""
    )

    return {
        "company_name": name,
        "website": website,
        "domain": normalize_domain(website_with_proto),
        "address": address,
        "phone": phone,
        "hp_partner_type": str(partner_type).strip() if partner_type else "",
    }


# ---------------------------------------------------------------------------
# MetaLocator direct API (primary — skips browser automation if it works)
# ---------------------------------------------------------------------------

METALOCATOR_BASE = "https://hp.metalocator.com/index.php"
# Itemid=19398 is the GPL (business reseller) locator — discovered by clicking "Business"
METALOCATOR_ITEMID = "19398"
AU_LAT, AU_LNG = -25.2744, 133.7751

def _b64(val: float) -> str:
    return _base64.b64encode(str(val).encode()).decode()


def try_metalocator_api():
    """Call the MetaLocator search_zip JSONP API directly and paginate until all records collected.

    Endpoint discovered by intercepting network traffic after clicking "Business":
      task=search_zip, layout=_jsonfast, country=Australia, national=true, Itemid=19398
    Response is wrapped in handleJSONPResults(...) — stripped before JSON parsing.
    """
    headers = {
        "User-Agent": CHROME_UA,
        "Referer": METALOCATOR_IFRAME_URL,
        "Accept": "*/*",
    }
    base_params = {
        "option": "com_locator",
        "view": "directory",
        "force_link": "1",
        "tmpl": "component",
        "task": "search_zip",
        "framed": "1",
        "format": "raw",
        "no_html": "1",
        "templ[]": "address_format",
        "layout": "_jsonfast",
        "radius": "",
        "interface_revision": "5737",
        "region": "AU",
        "lang": "en-GB (1)",
        "unifiedsearch": "",
        "user_lat": _b64(AU_LAT),
        "user_lng": _b64(AU_LNG),
        "keyword": "",
        "country": "Australia",
        "Itemid": METALOCATOR_ITEMID,
        "ml_skip_interstitial": "0",
        "preview": "0",
        "parent_table": "",
        "parent_id": "0",
        "search_type": "point",
        "national": "true",
        "callback": "handleJSONPResults",
        "filter_order": "id",
        "filter_order_Dir": "asc",
        "reset": "false",
        "nearest": "false",
        "_urlparams": '{"tagsegment":"APJ"}',
    }

    log.info("Calling MetaLocator search_zip API (JSONP)...")
    all_records = []
    limit = 500
    offset = 0

    while True:
        params = {**base_params, "limit": limit, "limitstart": offset}
        try:
            resp = _requests.get(METALOCATOR_BASE, params=params, headers=headers, timeout=30)
            log.info(f"  offset={offset:4d}  status={resp.status_code}  bytes={len(resp.text)}")
            if resp.status_code != 200:
                log.warning(f"  Unexpected status {resp.status_code} — stopping pagination")
                break
            # Strip JSONP wrapper: handleJSONPResults({...}); → {...}
            text = resp.text.strip()
            prefix = "handleJSONPResults("
            if text.startswith(prefix):
                inner = text[len(prefix):]
                last_paren = inner.rfind(")")
                text = inner[:last_paren] if last_paren != -1 else inner
            data = json.loads(text)
            batch = data.get("results", [])
            log.info(f"  Batch: {len(batch)} records")
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < limit:
                break  # Last page
            offset += limit
        except Exception as e:
            log.warning(f"  API error at offset={offset}: {e}")
            break

    if all_records:
        log.info(f"  Total: {len(all_records)} records fetched")
        return all_records
    log.warning("  Direct API returned 0 records")
    return None


# ---------------------------------------------------------------------------
# Phase 1: Playwright scrape
# ---------------------------------------------------------------------------

async def scrape_hp_locator() -> list[dict]:
    """Navigate HP locator with Playwright and extract raw partner records."""
    captured = []  # {"url": str, "data": any}

    async def on_response(response):
        try:
            url = response.url
            ct = response.headers.get("content-type", "")
            # Log all non-trivial responses (skip image/font/css/map tiles)
            skip = any(x in ct for x in ("image/", "font/", "text/css", "octet-stream"))
            skip = skip or any(x in url for x in (".png", ".jpg", ".gif", ".woff", ".ttf", "maps/vt?", "/tile?"))
            if not skip:
                log.info(f"  [{response.status}] {ct[:30]:30s}  {url[:110]}")
            if "json" in ct and response.status == 200:
                try:
                    data = await response.json()
                    captured.append({"url": url, "data": data})
                except Exception:
                    pass
        except Exception:
            pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=CHROME_UA)
        page = await context.new_page()
        page.on("response", on_response)

        # Navigate directly to the MetaLocator iframe (bypasses the HP "Where to Buy?" landing)
        log.info(f"Navigating to MetaLocator iframe directly...")
        try:
            await page.goto(METALOCATOR_IFRAME_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            log.warning(f"Page load: {e} — continuing")

        await asyncio.sleep(5)

        # Grab the page HTML to inspect the search form structure
        html_snippet = await page.evaluate("document.body.innerHTML")
        log.info(f"Page body preview: {html_snippet[:300]}")

        # Try a blank search (MetaLocator often returns all results for a blank/country search)
        search_done = False
        for input_sel in ["input[type='text']", "#search", "input[name='search']",
                          "input[placeholder*='earch']", "input[placeholder*='ocation']",
                          "input[placeholder*='ostcode']", ".ml-search-input"]:
            try:
                inp = await page.query_selector(input_sel)
                if inp and await inp.is_visible():
                    await inp.click()
                    await inp.fill("")
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    log.info(f"Blank search via: {input_sel}")
                    search_done = True
                    await asyncio.sleep(6)
                    break
            except Exception:
                pass

        if not search_done:
            for btn_sel in ["button[type='submit']", "input[type='submit']",
                            "button:has-text('Search')", "button:has-text('Find')",
                            ".ml-search-btn", "[class*='search']"]:
                try:
                    btn = await page.query_selector(btn_sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        log.info(f"Clicked: {btn_sel}")
                        search_done = True
                        await asyncio.sleep(6)
                        break
                except Exception:
                    pass

        if not search_done:
            # Trigger JS search directly via page.evaluate (MetaLocator exposes ml_search or similar)
            try:
                await page.evaluate("typeof ml_search !== 'undefined' && ml_search()")
                log.info("Triggered ml_search() via JS eval")
                await asyncio.sleep(6)
            except Exception:
                pass

        await asyncio.sleep(3)

        # Screenshot for debugging
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_path = str(OUTPUT_DIR / "page_screenshot.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        log.info(f"Screenshot → {screenshot_path}")
        log.info(f"Page: {await page.title()} | {page.url}")

        log.info(f"\nTotal JSON responses intercepted: {len(captured)}")
        await browser.close()

    # Find partner data among intercepted responses
    raw_records = []
    for item in captured:
        companies = find_company_list(item["data"])
        if companies:
            log.info(f"Partner data found at: {item['url']}")
            log.info(f"Records in this response: {len(companies)}")
            raw_records.extend(companies)

    if not raw_records:
        log.warning("\nNo partner data found in intercepted responses.")
        log.info("All captured response URLs:")
        for item in captured:
            log.info(f"  {item['url']}")
        log.info("\nTip: Open DevTools → Network → XHR/Fetch while loading the page to find the API endpoint manually.")

    return raw_records


# ---------------------------------------------------------------------------
# Phase 2: Firmable LinkedIn enrichment
# ---------------------------------------------------------------------------

def _enrich_row(row: dict, client: FirmableClient) -> dict:
    domain = row.get("domain", "")
    if not domain:
        return {**row, "linkedin_url": "", "linkedin_source": "no_domain", "firmable_id": ""}
    try:
        company = client.lookup_company(domain)
        linkedin = company.get("linkedin", "") or ""
        # Firmable sometimes returns a slug instead of a full URL — normalise
        if linkedin and not linkedin.startswith("http"):
            linkedin = f"https://www.linkedin.com/company/{linkedin}"
        firmable_id = company.get("id", "")
        source = "firmable" if linkedin else "firmable_no_linkedin"
        return {**row, "linkedin_url": linkedin, "linkedin_source": source, "firmable_id": firmable_id}
    except Exception as e:
        log.warning(f"Firmable lookup failed for {domain}: {e}")
        return {**row, "linkedin_url": "", "linkedin_source": "not_found", "firmable_id": ""}


def enrich_all(rows: list[dict]) -> list[dict]:
    client = FirmableClient()
    enriched = [None] * len(rows)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_enrich_row, row, client): i for i, row in enumerate(rows)}
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            enriched[i] = future.result()
            done += 1
            if done % 10 == 0 or done == len(rows):
                log.info(f"  Firmable: {done}/{len(rows)} done")

    return enriched


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"\nSaved {len(rows)} rows → {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async():
    log.info("=== Phase 1: Scraping HP Locator ===")

    # Try direct MetaLocator API first (faster, no browser needed)
    raw_records = try_metalocator_api()
    if not raw_records:
        log.info("Direct API did not return data — falling back to Playwright browser scrape")
        raw_records = await scrape_hp_locator()

    if not raw_records:
        log.error("No records scraped — exiting. See tips above.")
        return

    companies = [parse_company(r) for r in raw_records]

    # Deduplicate by company name (case-insensitive)
    seen: set[str] = set()
    unique = []
    for c in companies:
        key = c["company_name"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)

    log.info(f"Scraped {len(unique)} unique companies")

    log.info("\n=== Phase 2: Firmable LinkedIn Enrichment ===")
    enriched = enrich_all(unique)

    with_linkedin   = sum(1 for r in enriched if r.get("linkedin_url"))
    no_domain       = sum(1 for r in enriched if r.get("linkedin_source") == "no_domain")
    not_found       = sum(1 for r in enriched if r.get("linkedin_source") == "not_found")

    log.info(f"\nSummary:")
    log.info(f"  Total companies : {len(enriched)}")
    log.info(f"  With LinkedIn   : {with_linkedin}")
    log.info(f"  No domain       : {no_domain}")
    log.info(f"  Not in Firmable : {not_found}")

    write_csv(enriched)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
