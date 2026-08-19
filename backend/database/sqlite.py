# =========================================================
# BuyQK - SQLite Database Configuration
# =========================================================

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


# =========================================================
# Project Root
# =========================================================
#
# Project:
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
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


# =========================================================
# Database File
# =========================================================

DATABASE_PATH = (
    PROJECT_ROOT / "buyqk.db"
)


# =========================================================
# SQLite URL
# =========================================================
#
# Using as_posix() makes the URL work correctly on Windows:
#
# sqlite:///D:/BuyQK/buyqk-ai/buyqk.db
#
# =========================================================

DATABASE_URL = (
    f"sqlite:///{DATABASE_PATH.as_posix()}"
)


# =========================================================
# Debug Information
# =========================================================

print("=" * 60)
print("[DATABASE] BuyQK SQLite configuration")
print(
    f"[DATABASE] Project root : "
    f"{PROJECT_ROOT}"
)
print(
    f"[DATABASE] Database file : "
    f"{DATABASE_PATH}"
)
print(
    f"[DATABASE] Database URL  : "
    f"{DATABASE_URL}"
)
print("=" * 60)


# =========================================================
# SQLite Connection Configuration
# =========================================================

@event.listens_for(
    Engine,
    "connect",
)
def _configure_sqlite(
    dbapi_connection,
    connection_record,
):
    """
    Configure every SQLite connection.

    Foreign-key enforcement is important because BuyQK uses
    relationships such as:

        orders → users
        orders → addresses
        orders → riders
        order_items → orders
        order_items → products
        payments → orders

    WAL improves read/write concurrency for the MVP,
    particularly when the frontend and AI workflow access
    SQLite around the same time.
    """

    cursor = dbapi_connection.cursor()

    try:
        # ---------------------------------------------
        # Enforce foreign keys
        # ---------------------------------------------

        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )

        # ---------------------------------------------
        # Improve SQLite read/write concurrency
        # ---------------------------------------------

        cursor.execute(
            "PRAGMA journal_mode=WAL"
        )

        # ---------------------------------------------
        # Wait briefly for another transaction instead
        # of immediately failing with "database is locked".
        # ---------------------------------------------

        cursor.execute(
            "PRAGMA busy_timeout=5000"
        )

    finally:
        cursor.close()


# =========================================================
# SQLAlchemy Engine
# =========================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    echo=False,
)


# =========================================================
# Session Factory
# =========================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# =========================================================
# FastAPI Database Dependency
# =========================================================

def get_db():
    """
    Create one SQLAlchemy session for a FastAPI request.

    The session is always closed after the request finishes.

    Transaction ownership remains with the service layer.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()