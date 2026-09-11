# Purpose:
# Provides reusable FastAPI dependencies for database access.
#
# Each API request receives a SQLAlchemy database session.
# The session is automatically closed after the request finishes.


from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.database import sqlite


def get_db() -> Generator[Session, None, None]:
    """
    Provide a SQLAlchemy database session to FastAPI endpoints.

    The session is created when the request starts and
    automatically closed when the request finishes.
    """

    db = sqlite.SessionLocal()

    try:
        yield db

    finally:
        db.close()