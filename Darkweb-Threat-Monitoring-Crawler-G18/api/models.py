# api/models.py
import datetime
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey


Base = declarative_base()

class Org(Base):
    __tablename__ = "orgs"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=datetime.datetime.utcnow)

    queries = relationship("Query", back_populates="org")
    crawled_pages = relationship("CrawledPage", back_populates="org")

class Query(Base):
    __tablename__ = "queries"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    org_id = sa.Column(sa.Integer, sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = sa.Column(sa.String(255), nullable=True)
    q_text = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.String(50), default="created")
    created_at = sa.Column(sa.DateTime(timezone=True), default=datetime.datetime.utcnow)

    org = relationship("Org", back_populates="queries")
    crawled_pages = relationship("CrawledPage", back_populates="query")

class CrawledPage(Base):
    __tablename__ = "crawled_pages"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    org_id = sa.Column(sa.Integer, sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    query_id = sa.Column(sa.Integer, sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=True)
    url = sa.Column(sa.Text, nullable=False)
    status_code = sa.Column(sa.Integer, nullable=True)
    content = sa.Column(sa.Text, nullable=True)  # store cleaned/prettified HTML or text
    content_snippet = sa.Column(sa.Text, nullable=True)  # short snippet for quick listing
    fetched_at = sa.Column(sa.DateTime(timezone=True), default=datetime.datetime.utcnow)
    clean_text = Column(Text, nullable=True)

    org = relationship("Org", back_populates="crawled_pages")
    query = relationship("Query", back_populates="crawled_pages")

# append to api/models.py

class Threat(Base):
    __tablename__ = "threats"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    org_id = sa.Column(sa.Integer, sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    crawled_page_id = sa.Column(sa.Integer, sa.ForeignKey("crawled_pages.id", ondelete="CASCADE"), nullable=True)
    indicator_type = sa.Column(sa.String(100), nullable=False)   # e.g. "credential-leak", "btc-address", "email"
    indicator = sa.Column(sa.Text, nullable=False)               # matching string / pattern
    severity = sa.Column(sa.String(20), nullable=False, default="low")  # low/medium/high/critical
    evidence = sa.Column(sa.Text, nullable=True)                 # optional snippet or JSON
    created_at = sa.Column(sa.DateTime(timezone=True), default=datetime.datetime.utcnow)

    # relationships
    org = relationship("Org")
    crawled_page = relationship("CrawledPage")

