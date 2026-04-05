# services/crawler/crawler_db.py
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os

from api.db import SessionLocal, engine
from api.models import Base, Org, Query, CrawledPage, Threat
from services.preprocessor.html_cleaner import clean_html

from services.preprocessor.hybrid_detector import analyze_page

# NOTE: do NOT call Base.metadata.create_all here (Alembic manages schema)


def fetch_html_using_session(url: str, session: requests.Session = None, timeout: int = 20):
    """Fetch using provided session (which may be Tor); returns (status_code, text)."""
    sess = session or requests
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    return r.status_code, r.text


def save_page_to_db(
    org_name: str,
    url: str,
    query_text: str = None,
    fetched_html: str = None,
    status_code: int = None,
    session: requests.Session = None,
):
    db = SessionLocal()
    try:
        # --- org ---
        org = db.query(Org).filter(Org.name == org_name).first()
        if not org:
            org = Org(name=org_name)
            db.add(org)
            db.commit()
            db.refresh(org)

        # --- query (optional) ---
        q = None
        if query_text:
            q = Query(org_id=org.id, q_text=query_text, status="created")
            db.add(q)
            db.commit()
            db.refresh(q)

        # --- fetch if needed ---
        if fetched_html is None:
            status_code, html = fetch_html_using_session(url, session=session, timeout=20)
        else:
            html = fetched_html

        if not html:
            print(f"[SKIP] Empty HTML for {url}")
            return

        # --- CLEAN TEXT (THIS IS THE KEY FIX) ---
        clean_text_value = clean_html(html)

        if not clean_text_value or len(clean_text_value) < 100:
            print(f"[SKIP] No usable text for {url}")
            return
        snippet = clean_text_value[:500]

        # --- save page ---
        cp = CrawledPage(
            org_id=org.id,
            query_id=q.id if q else None,
            url=url,
            status_code=status_code,
            content=html,                 # OK
            content_snippet=snippet,       # OK
            clean_text=clean_text_value,   # ✅ REQUIRED
            fetched_at=datetime.utcnow(),
        )

        db.add(cp)
        db.commit()
        db.refresh(cp)

        print(f"[OK] Saved CrawledPage id={cp.id}")

        # --- HYBRID DETECTOR (RULE + ML) ---
        analyze_page(
            engine=engine,
            org_id=org.id,
            page_id=cp.id,
            clean_text=clean_text_value
        )

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # usage: python -m services.crawler.crawler_db <org_name> <url> [<query_text>]
    if len(sys.argv) < 3:
        print("Usage: python -m services.crawler.crawler_db <org_name> <url> [<query_text>]")
        sys.exit(1)
    org_name = sys.argv[1]
    url = sys.argv[2]
    query_text = sys.argv[3] if len(sys.argv) > 3 else None
    save_page_to_db(org_name, url, query_text)
