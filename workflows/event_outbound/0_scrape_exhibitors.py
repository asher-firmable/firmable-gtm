"""
General-purpose event exhibitor scraper.

Takes any conference/event website URL, finds the exhibitors/sponsors listing,
scrapes all company entries, resolves missing LinkedIn URLs via Firecrawl search,
then looks up each company in Firmable to get their Firmable ID.

Output CSV columns: company_name, domain, linkedin_url, firmable_company_id

Usage:
    python workflows/event_outbound/scrape_exhibitors.py \
        --url "https://example-conference.com/exhibitors"

    python workflows/event_outbound/scrape_exhibitors.py \
        --url "https://example-conference.com" \
        --output data/output/my_event.csv \
        --skip-linkedin-resolve \
        --skip-firmable
"""

import argparse
import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from utils.firmable import FirmableClient

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

LINKEDIN_RE = re.compile(
    r"https?://(www\.)?linkedin\.com/company/[^\"'\s/>]+", re.IGNORECASE
)

# Keywords used to identify the exhibitors/sponsors page from a homepage
EXHIBITOR_KEYWORDS = [
    "exhibitor", "exhibitors", "sponsor", "sponsors", "sponsorship",
    "partner", "partners", "booth", "expo", "pavilion", "showcase",
]

# Path segments that indicate a non-listing page (download, registration, etc.)
_LISTING_EXCLUDE = {
    "download", "prospectus", "register", "registration", "schedule",
    "agenda", "speaker", "speakers", "exhibitor-hub", "pdf",
}

# Social domains to exclude when looking for a company's website link
SOCIAL_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com",
}

PAGE_TIMEOUT = 20000   # ms
SCROLL_PAUSE = 1500    # ms between scroll steps
PROFILE_TIMEOUT = 15000


# ---------------------------------------------------------------------------
# Phase 1: Discover exhibitor listing page
# ---------------------------------------------------------------------------

def find_exhibitor_url(page, start_url: str) -> str:
    """
    Load start_url. If it already looks like a listing, return it.
    Otherwise scan anchor tags for exhibitor/sponsor keywords and follow.
    """
    print(f"Loading: {start_url}")
    try:
        page.goto(start_url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
    except Exception:
        # networkidle can time out on heavy pages — fall back to domcontentloaded
        page.goto(start_url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    current = page.url
    path_lower = urlparse(current).path.lower()

    # Already on an exhibitor-ish page
    if any(kw in path_lower for kw in EXHIBITOR_KEYWORDS):
        print(f"  URL already looks like exhibitor page: {current}")
        return current

    # Scan all links on homepage
    content = page.content()
    soup = BeautifulSoup(content, "html.parser")
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(current))

    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        full_href = urljoin(base, href)
        # Only same-domain links
        if urlparse(full_href).netloc != urlparse(base).netloc:
            continue
        combined = (href + " " + text).lower()
        score = sum(1 for kw in EXHIBITOR_KEYWORDS if kw in combined)
        if score > 0:
            # Skip links that are clearly not a listing page (download, registration, etc.)
            path = urlparse(full_href).path.lower()
            if any(kw in path for kw in _LISTING_EXCLUDE):
                continue
            candidates.append((score, full_href))

    if not candidates:
        print("  No exhibitor link found on homepage — will scrape the page as-is.")
        return current

    candidates.sort(key=lambda x: -x[0])
    best = candidates[0][1]
    print(f"  Found exhibitor link: {best}")
    page.goto(best, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    return best


# ---------------------------------------------------------------------------
# Phase 2: Scrape all exhibitor entries
# ---------------------------------------------------------------------------

def scroll_to_load_all(page):
    """Scroll to bottom repeatedly until no new content appears.
    Also triggers lazy-loaded images by scrolling in segments."""
    # Segment scroll first to trigger intersection-observer lazy loads
    try:
        total_height = page.evaluate("document.body.scrollHeight")
        step = max(600, total_height // 10)
        for pos in range(0, total_height, step):
            page.evaluate(f"window.scrollTo(0, {pos})")
            page.wait_for_timeout(200)
    except Exception:
        pass

    prev_height = 0
    rounds = 0
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(SCROLL_PAUSE)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == prev_height or rounds > 30:
            break
        prev_height = new_height
        rounds += 1
    print(f"  Scrolled {rounds} times.")


def click_load_more(page) -> bool:
    """Click any 'load more' / 'next page' style button. Returns True if clicked."""
    LOAD_MORE_TEXTS = ["load more", "show more", "view more", "next", "›", ">"]
    for text in LOAD_MORE_TEXTS:
        try:
            btn = page.locator(
                f"button:has-text('{text}'), a:has-text('{text}')"
            ).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


TIER_LABEL_WORDS = {
    "partner", "sponsor", "exhibitor", "platinum", "gold", "silver", "bronze",
    "diamond", "headline", "presenting", "supporting", "media", "official",
    "knowledge", "demand", "branded", "global", "venue", "video", "registration",
    "experiential", "interested", "becoming", "partners", "sponsors", "exhibitors",
    "our", "2026", "2025", "2024",
    # UI element junk alt texts
    "loader", "loading", "spinner", "placeholder", "icon", "arrow", "button",
    "close", "menu", "hamburger", "search", "image", "img", "banner", "nav",
    "navigation", "toggle", "chevron",
}


EVENT_CONTEXT_WORDS = re.compile(
    r"\b(b2b|b 2 b|marketing|conference|summit|forum|expo|event|leaders|festival|"
    r"asia|apac|sydney|melbourne|brisbane|singapore|australia|logo|colour|color|"
    r"white|black|dark|light|horizontal|vertical|stacked|reversed|mono)\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _clean_alt_text(alt: str) -> str:
    """Strip event context noise from image alt text to get the company name."""
    # Cut at comma-space (e.g. "ROI DNA, hotwire at...")
    alt = re.sub(r",\s+.*", "", alt)
    # Cut at common dash/pipe separators
    alt = re.sub(r"\s+[-–|]\s+.*", "", alt)
    # Cut at " at " (e.g. "Acme at B2B Conference")
    alt = re.sub(r"\s+at\s+.*", "", alt, flags=re.IGNORECASE)
    # Remove years
    alt = YEAR_RE.sub("", alt)
    # Remove event context words one by one
    alt = EVENT_CONTEXT_WORDS.sub("", alt)
    # Collapse whitespace
    alt = re.sub(r"\s{2,}", " ", alt).strip()
    return alt


# Verbs that indicate the company name ends and a description begins
_NAME_STOP_RE = re.compile(
    r"\b(is |are |was |has |have |offers?|provides?|helps?|delivers?|enables?|"
    r"empowers?|builds?|creates?|develops?|makes?|works? )\b",
    re.IGNORECASE,
)


def _extract_name_from_description(html_soup) -> str:
    """
    Pull company name from the first sentence of description text.
    Works by finding the first <strong> or <p> text and cutting at a verb.
    E.g. "Transmission is a global B2B consultancy..." → "Transmission"
    """
    # Generic action/nav words that should never be company names
    _NAV_WORDS = {"visit", "click", "learn", "download", "read", "see", "view",
                  "explore", "discover", "find", "get", "sign", "register", "more"}

    # Try first <strong> tag in description (often contains company name + pitch)
    for strong in html_soup.find_all("strong"):
        text = strong.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        # Skip if it starts with a nav/action word (e.g. "Visit shootsta.com")
        if text.split()[0].lower() in _NAV_WORDS:
            continue
        m = _NAME_STOP_RE.search(text)
        if m:
            candidate = text[:m.start()].strip().rstrip(".,;:")
            if candidate and not _looks_like_tier_label(candidate):
                return candidate
        # If no verb found but it's short (< 5 words), it might just be the name
        words = text.split()
        if len(words) <= 4 and not _looks_like_tier_label(text):
            return text.strip()

    # Try first <p> tag
    for p in html_soup.find_all("p"):
        text = p.get_text(strip=True)
        if not text or len(text) < 3:
            continue
        m = _NAME_STOP_RE.search(text)
        if m and m.start() > 1:
            candidate = text[:m.start()].strip().rstrip(".,;:")
            if candidate and not _looks_like_tier_label(candidate) and len(candidate.split()) <= 5:
                return candidate
        break  # only check first p

    return ""


def _looks_like_tier_label(text: str) -> bool:
    """Return True if the text looks like a partnership tier label, not a company name."""
    if not text:
        return True
    words = set(re.sub(r"[^a-z\s]", "", text.lower()).split())
    # If more than half the words are tier-label words, it's probably a label
    if len(words) == 0:
        return True
    overlap = words & TIER_LABEL_WORDS
    return len(overlap) / len(words) > 0.5


def extract_company_name(el_html: str) -> str:
    """Try multiple heuristics to get a company name from a card's HTML."""
    soup = BeautifulSoup(el_html, "html.parser")

    # Priority 1: logo image alt text (most reliable — logos always have company name)
    for img in soup.find_all("img", alt=True):
        alt = _clean_alt_text(img["alt"].strip())
        if alt and len(alt) > 1 and not _looks_like_tier_label(alt):
            return alt

    # Priority 2: extract from description text (first strong/p sentence before verb)
    name = _extract_name_from_description(soup)
    if name:
        # Title-case if the name is all-lowercase (came from body text)
        if name == name.lower():
            name = name.title()
        return name

    # Priority 3: named CSS classes
    for cls in [".name", ".company-name", ".title", ".exhibitor-name",
                ".sponsor-name", ".org-name", ".card-title"]:
        t = soup.select_one(cls)
        if t:
            text = t.get_text(strip=True)
            if text and not _looks_like_tier_label(text):
                return text

    # Priority 4: heading tags — skip if they look like tier labels
    for tag in ["h2", "h3", "h4", "h5"]:
        t = soup.find(tag)
        if t:
            text = t.get_text(strip=True)
            if text and not _looks_like_tier_label(text):
                return text

    return ""


def extract_links_from_html(html: str, base_url: str) -> tuple[str, str]:
    """Return (website_url, linkedin_url) from a chunk of HTML."""
    website = ""
    linkedin = ""

    # LinkedIn via regex first (catches both href and text)
    m = LINKEDIN_RE.search(html)
    if m:
        linkedin = m.group(0).rstrip("/")

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        parsed = urlparse(href)
        netloc = parsed.netloc.lstrip("www.")
        if "linkedin.com" in netloc:
            if not linkedin and "/company/" in href:
                linkedin = href.rstrip("/")
        elif netloc and not any(s in netloc for s in SOCIAL_DOMAINS):
            if not website:
                website = href
    return website, linkedin


def find_profile_links(page, base_url: str) -> list[str]:
    """Find profile page links (e.g. 'View Profile', 'Read More') from current page."""
    PROFILE_TEXTS = ["view profile", "view details", "read more", "more info",
                     "learn more", "see more", "view exhibitor", "profile"]
    soup = BeautifulSoup(page.content(), "html.parser")
    base_netloc = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        href = a["href"]
        full = urljoin(base_url, href)
        if urlparse(full).netloc != base_netloc:
            continue
        if any(pt in text for pt in PROFILE_TEXTS):
            links.append(full)
    return list(dict.fromkeys(links))  # deduplicate, preserve order


def scrape_profile_page(page, profile_url: str) -> tuple[str, str, str]:
    """Visit a profile page; return (company_name, website, linkedin)."""
    name = website = linkedin = ""
    try:
        page.goto(profile_url, timeout=PROFILE_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        html = page.content()
        name = extract_company_name(html)
        website, linkedin = extract_links_from_html(html, profile_url)
    except Exception as e:
        print(f"  [warn] profile {profile_url}: {e}")
    return name, website, linkedin


def extract_from_page_images(html: str, base_url: str) -> list[dict]:
    """
    Scan all <img> tags on the page and pull company names from alt text.
    Each <img> must be wrapped in or near an <a> to get a website URL.
    Returns unique companies with non-trivial alt text.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_names = set()

    for img in soup.find_all("img", alt=True):
        alt = img.get("alt", "").strip()
        if not alt or len(alt) < 2:
            continue
        name = _clean_alt_text(alt)
        if not name or _looks_like_tier_label(name) or len(name) < 2:
            continue
        name_key = name.lower()
        if name_key in seen_names:
            continue

        # Look for an enclosing <a> tag (up to 3 levels) for the website
        website = ""
        node = img
        for _ in range(3):
            node = node.parent
            if node is None:
                break
            if node.name == "a" and node.get("href"):
                href = node["href"].strip()
                if href.startswith("http"):
                    parsed = urlparse(href)
                    netloc = parsed.netloc.lstrip("www.")
                    if not any(s in netloc for s in SOCIAL_DOMAINS):
                        website = href
                break

        seen_names.add(name_key)
        results.append({
            "company_name": name,
            "website_url": website,
            "linkedin_url": "",
        })

    return results


def identify_exhibitor_cards(page) -> list:
    """
    Try to identify repeating card elements that represent exhibitors.
    Returns a list of ElementHandle objects (or falls back to full-page parse).
    """
    CARD_SELECTORS = [
        ".exhibitor-card", ".exhibitor-item", ".exhibitor",
        ".sponsor-card", ".sponsor-item", ".sponsor",
        ".sponsors-section", "[class*='sponsors-section']",
        ".partner-card", ".partner-item", ".partner",
        ".company-card", ".company-item",
        ".card", ".list-group-item", ".grid-item",
        "article", "[class*='exhibitor']", "[class*='sponsor']",
        "[class*='company']", "[class*='booth']",
        # Elementor / WordPress / ACF / Dynamic Content for Elementor (DCE)
        ".dce-acf-repeater-grid .dce-post-item",
        ".dce-post-item",
        "[class*='dce-post-item']",
        ".elementor-repeater-item",
        # WordPress blocks
        ".wp-block-columns .wp-block-column",
        # Generic sponsor logo walls
        "[class*='logo-grid'] img",
        "[class*='logos-grid'] img",
        "[class*='sponsor-logo']",
        "[class*='partner-logo']",
    ]
    for sel in CARD_SELECTORS:
        try:
            count = page.locator(sel).count()
            if count >= 3:
                return page.locator(sel).all()
        except Exception:
            continue
    return []


def claude_extract_from_html(html: str) -> list[dict]:
    """
    Layer 2 fallback: send page HTML to Claude and ask it to extract
    sponsor/exhibitor company names and URLs directly.
    """
    import json
    from utils.ai import ask_claude

    # Trim to avoid exceeding token limits
    trimmed = html[:30000]
    prompt = (
        "You are parsing a conference sponsor/exhibitor page. "
        "From the HTML below, extract all company names and any website URLs you can find. "
        "Return ONLY a JSON array like: "
        '[{"company_name": "Acme Corp", "website_url": "https://acme.com"}, ...]. '
        "If you cannot find any companies, return an empty array []. "
        "Do not include any explanation outside the JSON.\n\nHTML:\n" + trimmed
    )
    try:
        response = ask_claude(prompt, model="claude-sonnet-4-6")
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            results = []
            for d in data:
                name = (d.get("company_name") or "").strip()
                if name:
                    results.append({
                        "company_name": name,
                        "website_url": (d.get("website_url") or "").strip(),
                        "linkedin_url": "",
                    })
            return results
    except Exception as e:
        print(f"  [claude html fallback error] {e}")
    return []


def claude_extract_from_screenshot(page) -> list[dict]:
    """
    Layer 3 fallback: take a full-page screenshot and ask Claude Vision
    to identify company names from logos and text.
    """
    import json
    from utils.ai import ask_claude_with_vision

    print("  Taking full-page screenshot for Claude Vision analysis...")
    try:
        image_bytes = page.screenshot(full_page=True, type="png")
        prompt = (
            "This is a screenshot of a conference sponsor/exhibitor page. "
            "List all company names you can read from logos or text on the page. "
            "Return ONLY a JSON array like: "
            '[{"company_name": "Acme Corp"}, ...]. '
            "If no companies are visible, return []. "
            "Do not include any explanation outside the JSON."
        )
        response = ask_claude_with_vision(image_bytes, prompt)
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            results = []
            for d in data:
                name = (d.get("company_name") or "").strip()
                if name:
                    results.append({
                        "company_name": name,
                        "website_url": "",
                        "linkedin_url": "",
                    })
            return results
    except Exception as e:
        print(f"  [claude vision fallback error] {e}")
    return []


def scrape_listing_page(page, listing_url: str) -> list[dict]:
    """
    Main scraping logic. Handles infinite scroll, load-more pagination,
    and click-through profile pages. Returns list of company dicts.
    """
    print("\nPhase 2: Scraping exhibitor listing...")

    # Extra wait for JS-heavy pages (Elementor/ACF/DCE content needs time to render)
    page.wait_for_timeout(3000)

    # Strategy A: Infinite scroll
    print("  Scrolling to load all content...")
    scroll_to_load_all(page)

    # Strategy B: Load more / paginate
    clicked = 0
    while click_load_more(page):
        clicked += 1
        scroll_to_load_all(page)
        if clicked > 20:
            break
    if clicked:
        print(f"  Clicked 'load more' {clicked} time(s).")

    # Final wait: let any AJAX/lazy-load triggered by scrolling settle
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        page.wait_for_timeout(3000)

    # Identify repeating card elements
    cards = identify_exhibitor_cards(page)
    exhibitors = []

    if cards:
        print(f"  Found {len(cards)} exhibitor cards.")
        for card in cards:
            try:
                html = card.inner_html()
                name = extract_company_name(html)
                website, linkedin = extract_links_from_html(html, listing_url)
                if name:
                    exhibitors.append({
                        "company_name": name,
                        "website_url": website,
                        "linkedin_url": linkedin,
                    })
            except Exception:
                continue
    else:
        # Fallback: extract company names from image alt text across the full page
        print("  No card selector matched — extracting from page images.")
        html = page.content()
        exhibitors = extract_from_page_images(html, listing_url)
        if exhibitors:
            print(f"  Found {len(exhibitors)} companies via image alt text.")
        else:
            print("  No companies found via image alt text.")

    # Check if profile click-through gives more data
    profile_links = find_profile_links(page, listing_url)
    if profile_links and (not exhibitors or not exhibitors[0].get("website_url")):
        print(f"  Found {len(profile_links)} profile links — visiting each...")
        for i, purl in enumerate(profile_links):
            print(f"    [{i+1}/{len(profile_links)}] {purl} ...", end=" ", flush=True)
            name, website, linkedin = scrape_profile_page(page, purl)
            # Try to match to existing entry by name, or add new
            matched = False
            for ex in exhibitors:
                if ex["company_name"] and name and ex["company_name"].lower() == name.lower():
                    if not ex["website_url"]:
                        ex["website_url"] = website
                    if not ex["linkedin_url"]:
                        ex["linkedin_url"] = linkedin
                    matched = True
                    break
            if not matched and name:
                exhibitors.append({
                    "company_name": name,
                    "website_url": website,
                    "linkedin_url": linkedin,
                })
            found = [x for x in ["website", "linkedin"] if locals().get(x)]
            print(", ".join([f for f in ["website", "linkedin"]
                              if (website if f == "website" else linkedin)]) or "nothing")
            time.sleep(0.3)

    # Layer 2: Claude Vision — runs if selectors/images returned nothing or suspiciously few results.
    # Vision comes before HTML analysis because logo grids are visually clear but DOM-noisy.
    if len(exhibitors) < 5:
        if exhibitors:
            print(f"  Only {len(exhibitors)} companies from DOM — likely junk. Trying Claude Vision...")
        else:
            print("  Layer 2: No results — trying Claude Vision...")
        vision_results = claude_extract_from_screenshot(page)
        if vision_results:
            exhibitors = vision_results
            print(f"  Claude Vision found {len(exhibitors)} companies.")
        else:
            # Layer 3: Claude HTML analysis as final fallback
            print("  Layer 3: Vision returned nothing — trying Claude HTML analysis...")
            html_results = claude_extract_from_html(page.content())
            if html_results:
                exhibitors = html_results
                print(f"  Claude HTML analysis found {len(exhibitors)} companies.")
            else:
                print("  All layers exhausted — no sponsors found.")

    # Deduplicate and drop rows with no usable data
    seen = set()
    unique = []
    for ex in exhibitors:
        name = ex["company_name"].strip()
        domain = extract_domain(ex.get("website_url", ""))
        # Drop rows that have neither a real company name nor a domain
        if not name and not domain:
            continue
        # Drop rows where the only "company" found is the LinkedIn platform itself
        if name.lower() in {"linkedin", "linkedin logo"} and not domain:
            continue
        key = (name or domain).lower()
        if key not in seen:
            seen.add(key)
            unique.append(ex)

    print(f"  Total unique exhibitors: {len(unique)}")
    return unique


# ---------------------------------------------------------------------------
# Phase 3: Resolve missing LinkedIn URLs via Firecrawl Search
# ---------------------------------------------------------------------------

def resolve_linkedin_via_firecrawl(company_name: str, domain: str = "", retries: int = 3) -> str:
    """Search for company's LinkedIn profile URL using Firecrawl search API. Retries on timeout.
    Uses domain as the primary search signal when available — more reliable than company name."""
    if not FIRECRAWL_API_KEY:
        return ""
    # Domain-first: e.g. 'dentsu.com site:linkedin.com/company' finds the right page
    # even when the scraped company name is noisy or a sub-brand.
    query = f'{domain} site:linkedin.com/company' if domain else f'"{company_name}" site:linkedin.com/company'
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                FIRECRAWL_SEARCH_URL,
                headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                         "Content-Type": "application/json"},
                json={"query": query, "limit": 3},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data") or data.get("results") or []
            for r in results:
                url = r.get("url", "")
                if LINKEDIN_RE.match(url) or "linkedin.com/company" in url:
                    m = LINKEDIN_RE.search(url)
                    return m.group(0).rstrip("/") if m else url
            return ""  # request succeeded but no LinkedIn result found
        except requests.exceptions.Timeout:
            if attempt < retries:
                print(f"    [timeout, retry {attempt}/{retries}]", end=" ", flush=True)
                time.sleep(3 * attempt)
            else:
                print(f"    [firecrawl timeout after {retries} attempts]", end=" ", flush=True)
        except Exception as e:
            print(f"    [firecrawl error] {company_name}: {e}", end=" ", flush=True)
            break
    return ""


def resolve_missing_linkedin(exhibitors: list[dict]) -> list[dict]:
    missing = [ex for ex in exhibitors if not ex["linkedin_url"]]
    if not missing:
        return exhibitors
    if not FIRECRAWL_API_KEY:
        print(f"\nPhase 3: Skipping LinkedIn resolution (FIRECRAWL_API_KEY not set).")
        return exhibitors

    print(f"\nPhase 3: Resolving LinkedIn for {len(missing)} companies via Firecrawl...")
    resolved = 0
    for ex in missing:
        name = ex["company_name"]
        domain = extract_domain(ex.get("website_url", ""))
        label = domain if domain else name
        print(f"  Searching: {label} ...", end=" ", flush=True)
        url = resolve_linkedin_via_firecrawl(name, domain=domain)
        if url:
            ex["linkedin_url"] = url
            resolved += 1
            print(f"found: {url}")
        else:
            print("not found")
        time.sleep(1.0)  # stay polite

    print(f"  LinkedIn resolved: {resolved}/{len(missing)}")
    return exhibitors


# ---------------------------------------------------------------------------
# Phase 4: Firmable ID lookup
# ---------------------------------------------------------------------------

# Subdomains that are informational pages, not the root company domain
_JUNK_SUBDOMAINS = {
    "www", "about", "aboutus", "info", "help", "support", "blog",
    "news", "careers", "docs", "api", "solutions", "en", "au",
    "uk", "us", "apac", "global",
}

# Two-part TLD suffixes (country-code + generic) — preserve both parts
_TWO_PART_TLDS = {".com.au", ".co.uk", ".co.nz", ".com.sg", ".net.au", ".org.au"}


def extract_domain(website_url: str) -> str:
    """Extract the root company domain, stripping informational subdomains."""
    if not website_url:
        return ""
    try:
        netloc = urlparse(website_url).netloc.split(":")[0].lower()
        parts = netloc.split(".")

        # Detect two-part TLD (e.g. .com.au) — keep last 3 parts
        suffix = "." + ".".join(parts[-2:])
        if suffix in _TWO_PART_TLDS:
            keep = parts[-3:]  # e.g. ["adapt", "com", "au"]
        else:
            keep = parts[-2:]  # e.g. ["ft", "com"]

        # Strip junk leading subdomains
        while len(parts) > len(keep) and parts[0].lower() in _JUNK_SUBDOMAINS:
            parts = parts[1:]

        return ".".join(parts) if parts else ""
    except Exception:
        return ""


def lookup_firmable_company_id(client: FirmableClient, company: dict) -> str:
    """
    Try LinkedIn URL first, then domain. Returns firmable_company_id string or ''.
    """
    linkedin = company.get("linkedin_url", "")
    domain = extract_domain(company.get("website_url", ""))

    if linkedin:
        try:
            result = client.search_by_linkedin(linkedin)
            fid = result.get("firmable_company_id") or result.get("id", "")
            if fid:
                return str(fid)
        except Exception as e:
            print(f"    [firmable linkedin error] {company['company_name']}: {e}")

    if domain:
        try:
            result = client.lookup_company(domain=domain)
            fid = result.get("firmable_company_id") or result.get("id", "")
            if fid:
                return str(fid)
        except Exception as e:
            print(f"    [firmable domain error] {company['company_name']}: {e}")

    return ""


def enrich_with_firmable(exhibitors: list[dict], skip: bool = False) -> list[dict]:
    if skip:
        for ex in exhibitors:
            ex["firmable_company_id"] = ""
        return exhibitors

    try:
        client = FirmableClient()
    except ValueError as e:
        print(f"\nPhase 4: Skipping Firmable lookup — {e}")
        for ex in exhibitors:
            ex["firmable_company_id"] = ""
        return exhibitors

    print(f"\nPhase 4: Looking up Firmable IDs for {len(exhibitors)} companies...")
    found = 0
    for i, ex in enumerate(exhibitors):
        print(f"  [{i+1}/{len(exhibitors)}] {ex['company_name']} ...", end=" ", flush=True)
        fid = lookup_firmable_company_id(client, ex)
        ex["firmable_company_id"] = fid
        if fid:
            found += 1
            print(f"ID: {fid}")
        else:
            print("not found")
        time.sleep(0.2)

    print(f"  Firmable IDs found: {found}/{len(exhibitors)}")
    return exhibitors


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(exhibitors: list[dict], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for ex in exhibitors:
        name = ex.get("company_name", "").strip()
        domain = extract_domain(ex.get("website_url", ""))
        # Strip trailing punctuation artifacts
        name = name.strip(",.;: ")
        # Fall back to domain-derived name if name is empty or still looks like noise
        if not name or _looks_like_tier_label(name):
            name = domain.split(".")[0].replace("-", " ").title() if domain else ""
        # Title-case if the name is fully lowercase (e.g. extracted from body text)
        if name and name == name.lower():
            name = name.title()
        rows.append({
            "company_name": name,
            "domain": domain,
            "linkedin_url": ex.get("linkedin_url", ""),
            "firmable_company_id": ex.get("firmable_company_id", ""),
        })
    fieldnames = ["company_name", "domain", "linkedin_url", "firmable_company_id"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows → {output_path}")
    return rows


def print_summary(exhibitors: list[dict]):
    total = len(exhibitors)
    domains = sum(1 for ex in exhibitors if extract_domain(ex.get("website_url", "")))
    linkedins = sum(1 for ex in exhibitors if ex.get("linkedin_url"))
    firmable = sum(1 for ex in exhibitors if ex.get("firmable_company_id"))
    print(f"\nSummary:")
    print(f"  Total exhibitors:    {total}")
    print(f"  Domain found:        {domains} ({domains*100//total if total else 0}%)")
    print(f"  LinkedIn found:      {linkedins} ({linkedins*100//total if total else 0}%)")
    print(f"  Firmable ID found:   {firmable} ({firmable*100//total if total else 0}%)")


# ---------------------------------------------------------------------------
# Phase 5: Send to n8n
# ---------------------------------------------------------------------------

def send_to_n8n(rows: list[dict], webhook_url: str):
    """POST all rows as a batch to the n8n webhook."""
    print(f"\nPhase 5: Sending {len(rows)} rows to n8n...")
    try:
        resp = requests.post(
            webhook_url,
            json=rows,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        print(f"  Sent successfully (HTTP {resp.status_code})")
    except Exception as e:
        print(f"  [n8n error] {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape exhibitors/sponsors from any conference website."
    )
    parser.add_argument("--url", required=True,
                        help="Conference website or exhibitors page URL")
    parser.add_argument("--output",
                        help="Output CSV path (default: data/output/exhibitors_YYYYMMDD_HHMM.csv)")
    parser.add_argument("--skip-linkedin-resolve", action="store_true",
                        help="Skip Firecrawl search for missing LinkedIn URLs")
    parser.add_argument("--skip-firmable", action="store_true",
                        help="Skip Firmable API lookup (output domain + LinkedIn only)")
    parser.add_argument("--send-to-n8n", action="store_true",
                        help="POST all rows to the n8n webhook defined in N8N_WEBHOOK_URL")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = Path(args.output) if args.output else Path(f"data/output/exhibitors_{timestamp}.csv")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Phase 1
        find_exhibitor_url(page, args.url)

        # Phase 2
        exhibitors = scrape_listing_page(page, page.url)

        browser.close()

    if not exhibitors:
        print("\nNo sponsors found at " + args.url + ".\nThe page format may not be supported.")
        return

    # Phase 3
    if not args.skip_linkedin_resolve:
        exhibitors = resolve_missing_linkedin(exhibitors)

    # Phase 4
    exhibitors = enrich_with_firmable(exhibitors, skip=args.skip_firmable)

    print_summary(exhibitors)
    final_rows = write_csv(exhibitors, output_path)

    # Phase 5: send to n8n
    if args.send_to_n8n:
        webhook_url = N8N_WEBHOOK_URL
        if not webhook_url:
            print("\n[skip] N8N_WEBHOOK_URL not set in .env — skipping send.")
        else:
            send_to_n8n(final_rows, webhook_url)


if __name__ == "__main__":
    main()
