import re
from datetime import date
from playwright.sync_api import BrowserContext, TimeoutError as PlaywrightTimeoutError
from scraper.base import build_search_url, get_date_range_label, polite_delay, clean_domain
from config import Config


def scrape_domain(context: BrowserContext, domain: str, org_name: str) -> dict:
    """
    Scrape the Ads Transparency Center for a single domain.

    Steps:
    1. Load the domain search page — check for ads and get count
    2. Click the first ad creative — check for "Ad funded by" disclosure

    Returns a result dict ready to be written to the output sheet.
    """
    domain = clean_domain(domain)
    base_result = {
        "domain": domain,
        "org_name": org_name,
        "ads_running": "No",
        "ad_count": 0,
        "ad_funded_by": "",
        "funding_type": "None",
        "date_range": get_date_range_label(),
        "date_checked": str(date.today()),
    }

    page = context.new_page()

    try:
        url = build_search_url(domain)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        # ----------------------------------------------------------------
        # Step 1: Check for ads
        # ----------------------------------------------------------------
        no_ads_texts = ["No ads", "no ads found", "didn't find any ads"]
        for text in no_ads_texts:
            if page.get_by_text(text, exact=False).count() > 0:
                return base_result

        # Try multiple selectors for ad cards
        ad_selectors = [
            "creative-preview",
            "[data-creative-id]",
            ".creative-card",
            "ad-creative-preview",
        ]
        ad_cards = None
        for selector in ad_selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                ad_cards = locator
                break

        if ad_cards is None or ad_cards.count() == 0:
            return base_result

        ad_count = ad_cards.count()
        base_result["ads_running"] = "Yes"
        base_result["ad_count"] = ad_count

        # ----------------------------------------------------------------
        # Step 2: Click first ad — navigate in same page, not new tab
        # ----------------------------------------------------------------
        polite_delay()

        previous_url = page.url
        ad_cards.first.click()

        # Wait for URL to change (same-page navigation)
        try:
            page.wait_for_url(
                lambda url: url != previous_url,
                timeout=15000
            )
        except PlaywrightTimeoutError:
            # URL didn't change — try waiting for a detail element instead
            page.wait_for_timeout(3000)

        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        funded_by = extract_funded_by(page)

        if funded_by:
            base_result["ad_funded_by"] = funded_by
            base_result["funding_type"] = (
                "Grant" if "grant" in funded_by.lower() else "Disclosed"
            )
        else:
            base_result["funding_type"] = "Paid"

        return base_result

    except PlaywrightTimeoutError:
        base_result["ads_running"] = "Error (timeout)"
        base_result["funding_type"] = "Error"
        return base_result

    except Exception as e:
        base_result["ads_running"] = f"Error ({str(e)[:60]})"
        base_result["funding_type"] = "Error"
        return base_result

    finally:
        page.close()


def extract_funded_by(page) -> str:
    """
    Look for the 'Ad funded by:' disclosure on an ad detail page.
    Returns the funding source string if found, empty string if absent.

    The absence of this field is meaningful — it indicates paid advertising.
    """
    # Try text-based search first — most reliable across layout changes
    funded_by_pattern = re.compile(r"Ad funded by[:\s]+(.+)", re.IGNORECASE)

    # Search in the full page text
    body_text = page.locator("body").inner_text()
    match = funded_by_pattern.search(body_text)
    if match:
        # Clean up — take only the first line of the match
        value = match.group(1).strip().split("\n")[0].strip()
        return value

    # Fallback: look for a dedicated disclosure element
    disclosure_selectors = [
        "[data-funded-by]",
        ".funded-by",
        "text=Ad funded by",
    ]
    for selector in disclosure_selectors:
        el = page.locator(selector)
        if el.count() > 0:
            text = el.first.inner_text()
            match = funded_by_pattern.search(text)
            if match:
                return match.group(1).strip()

    return ""  # Not present — indicates paid advertising
