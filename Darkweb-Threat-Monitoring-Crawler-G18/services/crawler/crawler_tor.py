# services/crawler/crawler_tor.py

import sys
import os
import time
import random
from urllib.parse import urlparse
from typing import Optional, List

from services.crawler.tor_session import make_tor_session
from services.crawler.tor_control import renew_tor_circuit
from services.crawler.crawler_db import save_page_to_db
from services.crawler.tor_playwright import fetch_via_tor_playwright


# ---------------- CONFIG ----------------

PER_HOST_DELAY = 2.0
DEFAULT_TIMEOUT = 30
ONION_TIMEOUT = 60

RETRY_ATTEMPTS = 2
RETRY_BACKOFF = 2


# ---------------- HELPERS ----------------

def load_seeds(seed_path: str) -> List[str]:
    with open(seed_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def is_url(text: str) -> bool:
    p = urlparse(text)
    return p.scheme in ("http", "https") and p.netloc != ""


def is_onion(url: str) -> bool:
    host = urlparse(url).hostname
    return host is not None and host.endswith(".onion")


# ---------------- FETCH LOGIC ----------------

def fetch_via_tor_once(
    url: str,
    rotate_circuit: bool = False,
    control_port: int = 9051,
):
    """
    1. Try requests-over-Tor
    2. If it fails OR site is .onion → fallback to Playwright
    """

    timeout = ONION_TIMEOUT if is_onion(url) else DEFAULT_TIMEOUT
    session = make_tor_session()

    # Optional Tor circuit rotation
    if rotate_circuit:
        try:
            print(" Requesting new Tor circuit (NEWNYM)")
            renew_tor_circuit(control_port=control_port)
            time.sleep(1.5)
        except Exception as e:
            print("  Tor circuit rotation skipped:", e)

    # ---- requests + Tor ----
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f" Attempt {attempt} via requests+Tor → {url}")
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.status_code, r.text

        except Exception as e:
            print(f"  Attempt {attempt} failed:", e)
            if attempt < RETRY_ATTEMPTS:
                wait = RETRY_BACKOFF * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    # ---- Playwright fallback (critical) ----
    try:
        print(" Falling back to Playwright (JS-rendered Tor fetch)")
        html = fetch_via_tor_playwright(url)
        return 200, html
    except Exception as e:
        print(" Playwright fetch failed:", e)

    raise RuntimeError("All fetch attempts failed")


# ---------------- FETCH + SAVE ----------------

def fetch_and_save(
    org_name: str,
    url: str,
    query_text: Optional[str] = None,
    rotate_circuit: bool = False,
):
    host = urlparse(url).hostname or "unknown"
    print(f"\n Sleeping {PER_HOST_DELAY}s before contacting: {host}")
    time.sleep(PER_HOST_DELAY)

    try:
        status_code, html = fetch_via_tor_once(
            url=url,
            rotate_circuit=rotate_circuit,
        )
    except Exception as e:
        print(f" Fetch failed for {url}: {e}")
        return

    try:
        print(f" Saving result for {url}")
        save_page_to_db(
            org_name=org_name,
            url=url,
            query_text=query_text,
            fetched_html=html,
            status_code=status_code,
        )
    except Exception as e:
        print(" Error saving page to DB:", e)


# ---------------- MAIN ----------------

def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python -m services.crawler.crawler_tor "
            "<org_name> <url_or_seedfile> [<query_text>] [--rotate]"
        )
        sys.exit(1)

    org_name = sys.argv[1]
    target = sys.argv[2]
    query_text = (
        sys.argv[3]
        if len(sys.argv) > 3 and not sys.argv[3].startswith("--")
        else None
    )

    rotate = "--rotate" in sys.argv

    if os.path.isfile(target):
        print(f" Loading seeds from: {target}")
        urls = load_seeds(target)
        random.shuffle(urls)
        print(f" Loaded {len(urls)} seeds (randomized)")
    elif is_url(target):
        urls = [target]
        print(f" Single URL mode: {target}")
    else:
        print(f" ERROR: {target} is neither a URL nor a seed file.")
        sys.exit(1)

    print(f" Starting crawl for org: {org_name}")
    if rotate:
        print(" Tor circuit rotation enabled")

    for url in urls:
        fetch_and_save(
            org_name=org_name,
            url=url,
            query_text=query_text,
            rotate_circuit=rotate,
        )


if __name__ == "__main__":
    main()
