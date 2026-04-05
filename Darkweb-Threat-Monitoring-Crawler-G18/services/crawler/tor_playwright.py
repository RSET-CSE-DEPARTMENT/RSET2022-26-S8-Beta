# services/crawler/tor_playwright.py
from playwright.sync_api import sync_playwright
import time

TOR_SOCKS = "socks5://127.0.0.1:9050"

def fetch_via_tor_playwright(url: str, timeout: int = 45000) -> str:
    """
    Fetch fully rendered HTML using Playwright over Tor
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": TOR_SOCKS}
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        )

        page = context.new_page()
        page.goto(url, timeout=timeout, wait_until="networkidle")
        time.sleep(2)  # allow JS to settle

        html = page.content()

        browser.close()
        return html
