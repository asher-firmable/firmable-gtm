"""
Scrape the Singapore FinTech Festival 2026 exhibitor list.

Source: https://www.fintechfestival.sg/exhibitors (server-rendered HubSpot CMS page,
all exhibitors on one page as <li class="sff26-exl__c"> cards). Each card has the
name, booth, country and first focus area but no website, so each detail page
(/exhibitors?sff_website_url=<slug>) is fetched for the "Visit website" CTA and
LinkedIn link.

Output: campaigns/sea-conferences/singapore-fintech-festival-2026/output/exhibitors.csv
Columns: name, website, linkedin, country, stand, hall, category, profile_url

Run from repo root:
    PYTHONPATH=. python3 campaigns/sea-conferences/singapore-fintech-festival-2026/scrape_exhibitors.py
"""

import csv
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.fintechfestival.sg"
LIST_URL = f"{BASE}/exhibitors"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
OUT_CSV = os.path.join(OUT_DIR, "exhibitors.csv")
WORKERS = 1
DETAIL_DELAY = 1.5  # seconds between detail requests; the site returns 429 under parallel load

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def fetch(url: str, retries: int = 5) -> str:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After") or 0) or 30 * attempt
                log.warning(f"  429 rate limited ({attempt}/{retries}), sleeping {wait}s: {url}")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            log.warning(f"  fetch failed ({attempt}/{retries}) {url}: {e}")
            time.sleep(5 * attempt)
    return ""


def text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def parse_list(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for li in soup.select("li.sff26-exl__c"):
        a = li.select_one("a.sff26-exl__a")
        if not a:
            continue
        meta = li.select_one(".sff26-exl__m")
        stand = text(meta.find("b")) if meta else ""
        spans = [s for s in meta.find_all("span", recursive=False)] if meta else []
        country = ""
        if spans:
            last = spans[-1]
            if "sff26-exl__dot" not in (last.get("class") or []) and not last.find("b"):
                country = text(last)
        focus = li.select_one(".sff26-exl__f")
        category = ""
        if focus:
            more = focus.select_one(".sff26-exl__more")
            if more:
                more.extract()
            category = text(focus)
        rows.append({
            "name": text(li.select_one(".sff26-exl__n")),
            "website": "",
            "linkedin": "",
            "country": country,
            "stand": stand,
            "hall": li.get("data-hall", ""),
            "category": category,
            "profile_url": urljoin(BASE, a["href"]),
        })
    return rows


def parse_detail(row: dict) -> dict:
    if row.get("website"):
        return row  # already resolved on a previous run
    time.sleep(DETAIL_DELAY)
    html = fetch(row["profile_url"])
    if not html:
        log.error(f"  no detail page for {row['name']} ({row['profile_url']})")
        return row
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a.cta-button[href]"):
        if "visit website" in text(a).lower():
            row["website"] = a["href"].strip()
            break
    for a in soup.select("a.sff26-exhibitor-profile__ic[href]"):
        if "linkedin.com" in a["href"]:
            row["linkedin"] = a["href"].strip()
            break
    return row


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    html = fetch(LIST_URL)
    if not html:
        raise SystemExit("Could not fetch exhibitor list page")
    rows = parse_list(html)
    # Resume: reuse website/linkedin from a previous run so only missing rows are re-fetched
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, newline="", encoding="utf-8") as f:
            prev = {r["profile_url"]: r for r in csv.DictReader(f)}
        for r in rows:
            p = prev.get(r["profile_url"])
            if p and p.get("website"):
                r["website"], r["linkedin"] = p["website"], p.get("linkedin", "")
    todo = sum(1 for r in rows if not r["website"])
    log.info(f"Found {len(rows)} exhibitor cards; fetching {todo} detail pages...")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(parse_detail, rows))

    seen, deduped = set(), []
    for r in rows:
        key = (r["name"].lower(), r["website"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(deduped[0].keys()))
        w.writeheader()
        w.writerows(deduped)

    with_site = sum(1 for r in deduped if r["website"])
    log.info(f"\nSummary: {len(deduped)} exhibitors ({len(rows) - len(deduped)} duplicates dropped) | "
             f"{with_site} with website | {len(deduped) - with_site} without -> {OUT_CSV}")


if __name__ == "__main__":
    main()
