import requests
from bs4 import BeautifulSoup

def fetch(url="https://example.com"):
    print("Fetching", url)
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text

if __name__ == "__main__":
    html = fetch()
    soup = BeautifulSoup(html, "html.parser")
    with open("services/crawler/latest_page.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    print("Saved services/crawler/latest_page.html")
