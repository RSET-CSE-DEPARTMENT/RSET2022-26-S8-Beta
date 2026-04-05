from bs4 import BeautifulSoup
import unicodedata
import re

def clean_html(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Whitespace normalization
    text = re.sub(r"\s+", " ", text)

    return text.strip()
