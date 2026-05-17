"""
Scrape BDO Australia "Our People" directory — Deal Advisory service area.

Navigates to the filtered listing page, clicks "Show more" until all results
are visible, then visits each individual profile to extract:
    full_name, title, practice_area, city, linkedin_url, bio_url

Output: campaigns/anz/bdo-deal-advisory/output/people.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/bdo-deal-advisory/scrape_people.py
"""

import csv
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LISTING_URL = "https://www.bdo.com.au/en-au/our-people?serviceArea=Deal%20Advisory"
BASE_URL     = "https://www.bdo.com.au"

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "people.csv"

PROFILE_DELAY_S   = 0.5   # polite delay between profile fetches
SHOW_MORE_TIMEOUT = 8000  # ms to wait after each "Show more" click


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(page_or_loc, selector: str, default: str = "") -> str:
    """Return stripped inner text of the first matching element, or default."""
    try:
        el = page_or_loc.locator(selector).first
        el.wait_for(timeout=2000)
        return el.inner_text().strip()
    except Exception:
        return default


def _attr(page_or_loc, selector: str, attr: str, default: str = "") -> str:
    """Return an attribute value from the first matching element, or default."""
    try:
        el = page_or_loc.locator(selector).first
        el.wait_for(timeout=2000)
        val = el.get_attribute(attr)
        return (val or "").strip()
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Step 1: Collect profile URLs from the listing page
# ---------------------------------------------------------------------------

def dismiss_cookie_dialog(page) -> None:
    """Accept the CookieBot consent dialog if present."""
    try:
        accept_btn = page.locator("button#CybotCookiebotDialogBodyButtonAccept, button.CybotCookiebotDialogBodyButton:has-text('Accept')").first
        accept_btn.wait_for(state="visible", timeout=5000)
        accept_btn.click()
        print("  Cookie dialog dismissed.")
        page.wait_for_timeout(1500)
    except PlaywrightTimeout:
        pass  # No dialog — fine


def collect_profile_urls(page) -> list[str]:
    print(f"Loading listing page: {LISTING_URL}")
    page.goto(LISTING_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    dismiss_cookie_dialog(page)

    clicks = 0
    while True:
        # Count currently visible cards
        card_count = page.locator("a[href*='/en-au/our-people/']").count()
        print(f"  Cards visible: {card_count} (after {clicks} 'Show more' clicks)")

        # BDO uses <a class="btn btn--secondary"> with text "show more"
        show_more = page.locator("a.btn--secondary:has-text('show more'), a.btn--secondary:has-text('Show more'), a:has-text('Show more'), button:has-text('Show more')").first

        try:
            show_more.wait_for(state="visible", timeout=4000)
            show_more.scroll_into_view_if_needed()
            show_more.click()
            clicks += 1
            page.wait_for_timeout(SHOW_MORE_TIMEOUT)
        except PlaywrightTimeout:
            print("  'Show more' not found or no longer visible — all results loaded.")
            break
        except Exception as e:
            print(f"  Could not click 'Show more': {e}")
            break

    # Collect all unique profile URLs
    anchors = page.locator("a[href*='/en-au/our-people/']").all()
    seen = set()
    urls = []
    for a in anchors:
        href = a.get_attribute("href") or ""
        # Exclude the listing page itself and filter to individual profiles
        if not href or href.rstrip("/") == "/en-au/our-people":
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url not in seen:
            seen.add(full_url)
            urls.append(full_url)

    print(f"Collected {len(urls)} unique profile URLs.")
    return urls


# ---------------------------------------------------------------------------
# Step 2: Extract data from each profile page
# ---------------------------------------------------------------------------

def extract_profile(page, url: str) -> dict:
    row = {
        "full_name":     "",
        "title":         "",
        "practice_area": "",
        "city":          "",
        "linkedin_url":  "",
        "bio_url":       url,
    }

    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  [error] Could not load {url}: {e}")
        return row

    # --- Full name: h1.bio__title ---
    row["full_name"] = _text(page, "h1.bio__title")

    # --- Title: .bio__subtitle (may contain <br>-separated roles) ---
    try:
        subtitle_el = page.locator(".bio__subtitle").first
        subtitle_el.wait_for(timeout=2000)
        # Replace <br> with "; " then get inner text
        raw = subtitle_el.inner_text().strip()
        row["title"] = raw.replace("\n", "; ")
    except Exception:
        pass

    # --- Practice area: first <p class="bio__text"> (services line) ---
    try:
        texts = page.locator("p.bio__text").all()
        if texts:
            row["practice_area"] = (texts[0].inner_text() or "").strip()
    except Exception:
        pass

    # --- City: contacts link href="/en-au/locations/<city>" (may be in lg:hidden div) ---
    try:
        row["city"] = page.evaluate("""
            () => {
                const a = document.querySelector("a[href*='/en-au/locations/']");
                return a ? (a.innerText || a.textContent || '').trim() : '';
            }
        """)
    except Exception:
        pass

    # --- LinkedIn: contacts link href containing linkedin.com/in/ ---
    try:
        row["linkedin_url"] = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll("a[href*='linkedin.com']"));
                const profile = links.find(a => /linkedin\\.com\\/(in|pub)\\//.test(a.href));
                return profile ? profile.href.trim() : '';
            }
        """)
    except Exception:
        pass

    return row


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

FIELDNAMES = ["full_name", "title", "practice_area", "city", "linkedin_url", "bio_url"]


def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows → {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Step 1 — collect URLs from listing page
        profile_urls = collect_profile_urls(page)

        # Step 2 — visit each profile
        for i, url in enumerate(profile_urls, 1):
            print(f"[{i}/{len(profile_urls)}] {url}")
            row = extract_profile(page, url)
            rows.append(row)
            print(f"  → {row['full_name']} | {row['title']} | {row['city']}")
            time.sleep(PROFILE_DELAY_S)

        browser.close()

    if not rows:
        print("No data scraped.")
        return

    linkedin_count = sum(1 for r in rows if r["linkedin_url"])
    city_missing   = sum(1 for r in rows if not r["city"])
    print(f"\nSummary: {len(rows)} people | {linkedin_count} with LinkedIn | {city_missing} missing city")

    write_csv(rows)


if __name__ == "__main__":
    main()
