"""
Scrape FTI Consulting experts directory — Asia Pacific, Strategic Communications.

Step 1: Extract Name, Title, Location, Profile URL from the Coveo listing cards.
Step 2: Visit each profile to extract Email and LinkedIn link.

All results are filtered to Strategic Communications so Practice Area is set
to "Strategic Communications" for every row.

Output: campaigns/anz/fti-consulting/output/fti_consulting_experts.csv

Usage:
    PYTHONPATH=. python3 campaigns/anz/fti-consulting/scrape_people.py
"""

import csv
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://www.fticonsulting.com"

LISTING_URL = (
    "https://www.fticonsulting.com/experts"
    "#sort=relevancy"
    "&numberOfResults=45"
    "&f:experts-service=[Strategic%20Communications]"
    "&f:experts-location=[Asia%20Pacific]"
)

OUTPUT_DIR  = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "fti_consulting_experts.csv"

PRACTICE_AREA   = "Strategic Communications"
PROFILE_DELAY_S = 0.75
COVEO_WAIT_MS   = 6000

FIELDNAMES = ["Name", "Practice Area", "Title", "Email", "LinkedIn link", "Location", "Profile URL"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(locator_root, selector: str, default: str = "") -> str:
    try:
        el = locator_root.locator(selector).first
        el.wait_for(timeout=3000)
        return el.inner_text().strip()
    except Exception:
        return default


def dismiss_onetrust(page) -> None:
    try:
        btn = page.locator("#onetrust-accept-btn-handler").first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        page.wait_for_timeout(1500)
        print("  OneTrust banner dismissed.")
    except PlaywrightTimeout:
        pass


# ---------------------------------------------------------------------------
# Step 1: Extract card data from the listing page
# ---------------------------------------------------------------------------

def collect_listing_data(page) -> list[dict]:
    print(f"Loading listing page...")
    page.goto(LISTING_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(COVEO_WAIT_MS)

    dismiss_onetrust(page)

    # Wait for Coveo results
    try:
        page.locator(".CoveoResult").first.wait_for(timeout=10000)
    except PlaywrightTimeout:
        print("  Warning: .CoveoResult not found after waiting.")

    cards = page.locator(".CoveoResult").all()
    print(f"Found {len(cards)} result cards.")

    rows = []
    for card in cards:
        name     = _text(card, ".expert-card__name")
        title    = _text(card, ".expert-card__contents").replace("\n", " ").strip()
        location = _text(card, ".expert-card__location")

        # Resolve relative href to full URL
        try:
            href = card.locator("a.CoveoResultLink").first.get_attribute("href") or ""
            profile_url = urljoin(BASE_URL, href) if href else ""
        except Exception:
            profile_url = ""

        if not name and not profile_url:
            continue

        rows.append({
            "Name":         name,
            "Practice Area": PRACTICE_AREA,
            "Title":        title,
            "Email":        "",
            "LinkedIn link": "",
            "Location":     location,
            "Profile URL":  profile_url,
        })

    return rows


# ---------------------------------------------------------------------------
# Step 2: Enrich each profile with email and LinkedIn
# ---------------------------------------------------------------------------

def enrich_profile(page, row: dict) -> dict:
    url = row["Profile URL"]
    if not url:
        return row

    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  [error] Could not load {url}: {e}")
        return row

    # Email — FTI puts it in a mailto: social link
    try:
        row["Email"] = page.evaluate("""
            () => {
                const a = document.querySelector("a[href^='mailto:']");
                return a ? a.href.replace('mailto:', '').trim() : '';
            }
        """)
    except Exception:
        pass

    # LinkedIn — personal /in/ profile only (skip company page links)
    try:
        row["LinkedIn link"] = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll("a[href*='linkedin.com']"));
                const personal = links.find(a => /linkedin\\.com\\/(in|pub)\\//.test(a.href));
                return personal ? personal.href.trim() : '';
            }
        """)
    except Exception:
        pass

    return row


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows -> {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
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

        # Step 1: listing page
        rows = collect_listing_data(page)

        if not rows:
            print("No results found. Check if the page structure has changed.")
            browser.close()
            return

        # Step 2: visit each profile for email + LinkedIn
        for i, row in enumerate(rows, 1):
            print(f"[{i}/{len(rows)}] {row['Profile URL']}")
            enrich_profile(page, row)
            print(f"  -> {row['Name']} | {row['Title']} | {row['Location']} | {row['Email'] or '(no email)'}")
            time.sleep(PROFILE_DELAY_S)

        browser.close()

    email_count    = sum(1 for r in rows if r["Email"])
    linkedin_count = sum(1 for r in rows if r["LinkedIn link"])
    print(f"\nSummary: {len(rows)} people | {email_count} with email | {linkedin_count} with LinkedIn")

    write_csv(rows)


if __name__ == "__main__":
    main()
