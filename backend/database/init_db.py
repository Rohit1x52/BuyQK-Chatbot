"""
This file will:
Import the SQLAlchemy Base.
Import all 11 models through models/__init__.py.
Create all tables defined in Base.metadata.
Use our SQLite engine.
Provide a reusable init_db() function.
Allow us to verify that the complete model graph can be loaded without relationship/import errors.
"""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

from backend.database.base import Base
from backend.database.sqlite import engine

# Import all models so SQLAlchemy registers them
# with Base.metadata before creating the tables.
from backend.models import (
    User,
    Address,
    Category,
    Merchant,
    Product,
    Rider,
    Order,
    OrderItem,
    Payment,
    SupportTicket,
    ConversationHistory,
)


def init_db():
    """
    Create all database tables defined by the SQLAlchemy models.

    If a table already exists, SQLAlchemy leaves it unchanged.
    """

    Base.metadata.create_all(
        bind=engine
    )

    print("Database initialized successfully.")
    print("All BuyQK tables are ready.")


if __name__ == "__main__":
    init_db()