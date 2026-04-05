# (paste the detectors content from step 1B here)
# services/preprocessor/detectors.py
import re
from typing import Dict, List

# Simple high-precision regexes for initial detectors
RE_EMAIL_PASS = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}:[^\s:]{6,})\b")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_BTC = re.compile(r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
RE_ETH = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
RE_CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
RE_SQLI = re.compile(r"(union select|drop table|--\s|;--|or 1=1)", re.I)

def detect_indicators(text: str) -> Dict[str, List[str]]:
    """
    Returns dictionary mapping indicator_type -> list of indicators found.
    Keep detectors conservative to avoid false positives.
    """
    if not text:
        return {}

    found = {}

    # email:pass-like patterns (high confidence)
    creds = RE_EMAIL_PASS.findall(text)
    if creds:
        found["credential-leak"] = creds

    # email addresses
    emails = list(set(RE_EMAIL.findall(text)))
    if emails:
        found["email"] = emails

    # bitcoin addresses
    btcs = RE_BTC.findall(text)
    if btcs:
        found["btc-address"] = btcs

    # ethereum addresses
    eths = RE_ETH.findall(text)
    if eths:
        found["eth-address"] = eths

    # credit-card-like sequences — flag as medium confidence
    cards = RE_CREDIT_CARD.findall(text)
    if cards:
        found["credit-card-like"] = cards

    # simple SQLi-like giveaways
    sqli = RE_SQLI.findall(text)
    if sqli:
        found["sqli-signature"] = sqli

    return found

def score_indicator(indicator_type: str, indicator_value: str) -> str:
    if indicator_type == "credential-leak":
        # must contain @ to be real credentials
        if "@" in indicator_value:
            return "high"
        return "low"
    if indicator_type in ("btc-address", "eth-address"):
        return "medium"
    if indicator_type in ("credit-card-like", "sqli-signature"):
        return "medium"
    if indicator_type == "email":
        return "low"
    return "low"

