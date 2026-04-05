# services/crawler/tor_control.py
"""
Small helper to request NEWNYM (new Tor circuit) using stem.
Tries cookie-based auth first (recommended), then falls back to password auth.
"""

from typing import Optional
import os

def renew_tor_circuit(control_port: int = 9051, password: Optional[str] = None, cookie_path: Optional[str] = None, timeout: int = 10):
    """
    Request a NEWNYM from Tor control port.
    - control_port: port where Tor control listens (default 9051)
    - password: control password (if set). If None, try cookie auth.
    - cookie_path: path to control_auth_cookie (optional)
    Raises ImportError if stem is not installed.
    Raises Exception on failure.
    """
    try:
        from stem import Signal
        from stem.control import Controller
    except Exception as e:
        raise ImportError("stem not installed; run `pip install stem` to enable circuit rotation") from e

    controller = None

    # Try cookie auth if password not provided
    try:
        controller = Controller.from_port(port=control_port, timeout=timeout)
    except Exception as e:
        raise RuntimeError(f"Could not connect to Tor control port at localhost:{control_port}: {e}")

    try:
        if password:
            try:
                controller.authenticate(password=password)
            except Exception as e:
                raise RuntimeError("Password authentication failed for Tor control port") from e
        else:
            # try cookie file first
            try:
                # If cookie_path given, try to authenticate with cookie content
                if cookie_path and os.path.exists(cookie_path):
                    with open(cookie_path, "rb") as f:
                        cookie = f.read()
                    controller.authenticate(cookie=cookie)
                else:
                    # Try the default authenticate() which uses cookie if available
                    controller.authenticate()
            except Exception as e:
                # If cookie auth fails and password provided later, attempt password path
                raise RuntimeError("Cookie authentication to Tor control port failed") from e

        controller.signal(Signal.NEWNYM)
        # Optionally wait until newnym takes effect
    finally:
        try:
            controller.close()
        except Exception:
            pass
