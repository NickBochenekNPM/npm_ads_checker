import time
import random
from playwright.sync_api import sync_playwright, Browser, BrowserContext
from config import Config, DatePreset
from urllib.parse import urlparse

def clean_domain(domain: str) -> str:
    """Strip protocol, www, and trailing slashes from a domain."""
    domain = domain.strip()
    # Add a scheme if missing so urlparse works correctly
    if "://" not in domain:
        domain = "https://" + domain
    parsed = urlparse(domain)
    hostname = parsed.hostname or domain
    # Remove www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def build_search_url(domain: str) -> str:
    """Build the Ads Transparency Center search URL for a given domain."""
    base = (
        f"https://adstransparency.google.com/"
        f"?region={Config.REGION}&domain={domain}"
    )
    if Config.DATE_PRESET.value:
        base += f"&preset-date={Config.DATE_PRESET.value}"
    return base


def get_date_range_label() -> str:
    """Human-readable label for the configured date preset."""
    labels = {
        DatePreset.ALL_TIME: "All time",
        DatePreset.LAST_7: "Last 7 days",
        DatePreset.LAST_30: "Last 30 days",
        DatePreset.LAST_90: "Last 90 days",
        DatePreset.LAST_365: "Last 365 days",
    }
    return labels.get(Config.DATE_PRESET, "All time")


def polite_delay() -> None:
    """Random delay between requests to avoid rate limiting."""
    jitter = random.uniform(0.5, 1.5)
    time.sleep(Config.REQUEST_DELAY_SECONDS + jitter)


class BrowserManager:
    """
    Manages a single shared Playwright browser instance.
    Each scrape task gets its own isolated BrowserContext.
    Use as a context manager:

        with BrowserManager() as manager:
            context = manager.new_context()
            ...
    """

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=Config.PLAYWRIGHT_HEADLESS
        )
        return self

    def __exit__(self, *args):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def new_context(self) -> BrowserContext:
        """Return a fresh isolated browser context (like a new incognito window)."""
        return self._browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
