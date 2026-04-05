import os
import re
import random
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- USER AGENTS ----------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
]

# ---------- DARK WEB SEARCH ENDPOINTS ----------
SEARCH_ENGINE_ENDPOINTS = [
    "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",
    "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",
    "http://darkhuntyla64h75a3re5e2l3367lqn7ltmdzpgmr6b4nbz3q2iaxrid.onion/search?q={query}",
    "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",
    "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",
    "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",
    "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",
    "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",
    "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}",
    "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}",
    "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",
    "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",
    "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}",
    "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",
]

# ---------- TOR PROXY ----------
def get_tor_proxies():
    return {
        "http": os.getenv("TOR_SOCKS", "socks5h://127.0.0.1:19050"),
        "https": os.getenv("TOR_SOCKS", "socks5h://127.0.0.1:19050"),
    }

# ---------- FETCH SINGLE SEARCH PAGE ----------
def fetch_search_results(endpoint, query):
    url = endpoint.format(query=query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    proxies = get_tor_proxies()

    print(f"→ Checking: {url}")

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=25)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for a in soup.find_all("a"):
            try:
                href = a["href"]
                title = a.get_text(strip=True)

                match = re.findall(r"https?://[^/]*\.onion(?:/.*)?", href)

                if match:
                    results.append({"title": title, "link": match[0]})
            except:
                continue

        return results

    except Exception as e:
        print("  ERROR:", e)
        return []


# ---------- PARALLEL FETCH ----------
def get_search_results(query, max_workers=5):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = [
            exe.submit(fetch_search_results, ep, query)
            for ep in SEARCH_ENGINE_ENDPOINTS
        ]
        for f in as_completed(futures):
            results.extend(f.result())

    # Deduplicate
    unique = {}
    for r in results:
        if r["link"] not in unique:
            unique[r["link"]] = r

    return list(unique.values())


# ---------- MAIN ----------
def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m tools.seed_generator <keyword>")
        return

    keyword = sys.argv[1]
    seeds_dir = Path("seeds")
    seeds_dir.mkdir(exist_ok=True)

    print(f"🔎 Generating seeds for: {keyword}")
    results = get_search_results(keyword)

    out_file = seeds_dir / f"{keyword}.txt"
    with out_file.open("w") as f:
        for r in results:
            f.write(r["link"] + "\n")

    print(f"\n Found {len(results)} onion links")
    print(f" Saved to: {out_file}")


if __name__ == "__main__":
    main()
