# api/app.py
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from contextlib import contextmanager

from api.db import SessionLocal
from api.models import Org, CrawledPage
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="org-dwthreat API")

# simple DB session dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# tenant middleware: resolve org name from header X-Org-Name or query param 'org'
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    org_from_header = request.headers.get("X-Org-Name")
    org_from_query = request.query_params.get("org")
    # prefer header, fallback to query param, otherwise None
    request.state.org_name = org_from_header or org_from_query
    response = await call_next(request)
    return response

@app.get("/", summary="API root")
def root():
    return {"status": "ok", "message": "org-dwthreat backend running"}

@app.get("/orgs", summary="List organizations")
def list_orgs(db=Depends(get_db)):
    rows = db.query(Org).order_by(Org.created_at.desc()).all()
    return [{"id": o.id, "name": o.name, "created_at": o.created_at.isoformat()} for o in rows]

@app.get("/org/{org_name}/pages", summary="List recent crawled pages for an org")
def pages_for_org(org_name: str, limit: int = Query(20, ge=1, le=200), db=Depends(get_db)):
    org = db.query(Org).filter(Org.name == org_name).first()
    if not org:
        raise HTTPException(status_code=404, detail="org not found")
    pages = (
        db.query(CrawledPage)
        .filter(CrawledPage.org_id == org.id)
        .order_by(CrawledPage.fetched_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "url": p.url,
            "status_code": p.status_code,
            "fetched_at": p.fetched_at.isoformat(),
            "content_snippet": (p.content_snippet[:500] if p.content_snippet else None),
        }
        for p in pages
    ]

@app.get("/pages", summary="List pages for the tenant resolved from header/query")
def pages_for_tenant(limit: int = Query(20, ge=1, le=200), db=Depends(get_db), request: Request = None):
    org_name = getattr(request.state, "org_name", None)
    if not org_name:
        raise HTTPException(
            status_code=400,
            detail="Missing org context. Set X-Org-Name header or ?org=<org_name> query parameter."
        )
    org = db.query(Org).filter(Org.name == org_name).first()
    if not org:
        raise HTTPException(status_code=404, detail="org not found")
    pages = (
        db.query(CrawledPage)
        .filter(CrawledPage.org_id == org.id)
        .order_by(CrawledPage.fetched_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "url": p.url,
            "status_code": p.status_code,
            "fetched_at": p.fetched_at.isoformat(),
            "content_snippet": (p.content_snippet[:500] if p.content_snippet else None),
        }
        for p in pages
    ]

@app.get("/org/{org_name}/page/{page_id}", summary="Get a single crawled page (org-scoped)")
def get_page(org_name: str, page_id: int, db=Depends(get_db)):
    org = db.query(Org).filter(Org.name == org_name).first()
    if not org:
        raise HTTPException(status_code=404, detail="org not found")
    page = db.query(CrawledPage).filter(CrawledPage.id == page_id, CrawledPage.org_id == org.id).first()
    if not page:
        raise HTTPException(status_code=404, detail="page not found")
    return {
        "id": page.id,
        "url": page.url,
        "status_code": page.status_code,
        "fetched_at": page.fetched_at.isoformat(),
        "content_snippet": page.content_snippet,
        # do not return full content by default; include if you trust client
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)