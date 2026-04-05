import os
import csv

from api.db import SessionLocal
from api.models import CrawledPage

OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "darkweb_pages_frozen.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

db = SessionLocal()
pages = db.query(CrawledPage).all()

print(f"[INFO] Found {len(pages)} pages in DB")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "page_id",
        "org_id",
        "url",
        "clean_text"
    ])

    for p in pages:
        writer.writerow([
            p.id,
            p.org_id,
            p.url,
            p.clean_text
        ])

print(f"[SUCCESS] Dataset exported to: {OUTPUT_FILE}")
