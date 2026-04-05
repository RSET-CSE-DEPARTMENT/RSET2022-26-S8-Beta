# api/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv
load_dotenv()  # loads .env

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in environment (.env)")

# echo=True prints SQL to console (helpful for debugging) — set False later
engine = create_engine(DATABASE_URL, echo=False, future=True)

# Use sessionmaker for getting DB sessions
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
