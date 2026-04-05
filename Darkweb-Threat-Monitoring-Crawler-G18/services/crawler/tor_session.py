
# services/crawler/tor_session.py
"""
Tor-enabled requests session helper.

- Uses socks5h://127.0.0.1:9050 by default (the dperson/torproxy container above).
- Adds retries + sensible headers and a small convenience function to renew circuits using stem (optional).
"""

from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_SOCKS = "socks5h://127.0.0.1:19050"

def make_tor_session(socks_proxy: str = DEFAULT_SOCKS, timeout: int = 30) -> requests.Session:
    s = requests.Session()
    s.proxies.update({"http": socks_proxy, "https": socks_proxy})
    # retries for transient errors
    retries = Retry(total=3, backoff_factor=1, status_forcelist=(502, 503, 504))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "org-dwthreat-bot/0.1 (+https://your-org.example)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    # store default timeout on session for convenience (not used by requests directly)
    s.request_timeout = timeout
    return s

# Optional: stem helpers (best-effort — only active if 'stem' installed and control port configured)
def renew_tor_circuit(control_port: int = 9051, password: Optional[str] = None):
    """
    Try to request a new Tor circuit using stem. This will only work if a Tor control port
    is available and you configured authentication. It's optional — function will
    raise ImportError if stem is not installed.
    """
    try:
        from stem import Signal
        from stem.control import Controller
    except Exception as e:
        raise ImportError("stem not available; install 'stem' to use renew_tor_circuit") from e

    # default assumes control port is reachable at localhost:9051
    with Controller.from_port(port=control_port) as controller:
        if password:
            controller.authenticate(password=password)
        else:
            try:
                controller.authenticate()
            except Exception:
                # if control port requires auth and password not set, this will fail
                pass
        controller.signal(Signal.NEWNYM)
