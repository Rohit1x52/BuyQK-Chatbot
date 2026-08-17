from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ============================================================
# BuyQK Database Configuration
# ============================================================

# Project root:
#
# D:\BuyQK\buyqk-ai\
#
# This file:
#
# D:\BuyQK\buyqk-ai\backend\database\sqlite.py
#
# parents[0] -> backend/database
# parents[1] -> backend
# parents[2] -> buyqk-ai
#
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# SQLite Database Path
# ============================================================

DATABASE_PATH = PROJECT_ROOT / "buyqk.db"


# Convert Windows path safely for SQLAlchemy SQLite URL.
#
# Example:
#
# sqlite:///D:/BuyQK/buyqk-ai/buyqk.db
#
DATABASE_URL = (
    f"sqlite:///{DATABASE_PATH.as_posix()}"
)


# ============================================================
# Debug Information
# ============================================================

print("=" * 60)
print("[DATABASE] BuyQK SQLite configuration")
print(f"[DATABASE] Project root : {PROJECT_ROOT}")
print(f"[DATABASE] Database file : {DATABASE_PATH}")
print(f"[DATABASE] Database URL  : {DATABASE_URL}")
print("=" * 60)


# ============================================================
# SQLAlchemy Engine
# ============================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    echo=False,
)


# ============================================================
# Session Factory
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================================
# FastAPI Database Dependency
# ============================================================

def get_db():
    """
    Create a database session for a FastAPI request.

    The session is always closed after the request finishes.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()