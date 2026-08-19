"""
BuyQK Database Initialization

This module:

- Imports the SQLAlchemy Base.
- Imports all BuyQK models through models/__init__.py.
- Registers every model with Base.metadata.
- Creates all missing database tables.
- Uses the configured SQLite engine.
- Provides a reusable init_db() function.

Important:
    create_all() creates missing tables but does NOT migrate
    existing tables or modify their existing schema.
"""

from __future__ import annotations

import sys
from pathlib import Path


# =========================================================
# Standalone Execution Support
# =========================================================

if __package__ in {None, ""}:
    backend_root = Path(__file__).resolve().parents[1]

    if str(backend_root) not in sys.path:
        sys.path.insert(
            0,
            str(backend_root),
        )


# =========================================================
# Database
# =========================================================

from backend.database.base import Base
from backend.database.sqlite import engine


# =========================================================
# Model Registration
# =========================================================
#
# Importing the models ensures that SQLAlchemy registers
# their tables with Base.metadata before create_all().
#
# Cart and CartItem are included as part of Phase 3.
# =========================================================

from backend.models import (
    User,
    Address,
    Category,
    Merchant,
    Product,

    Cart,
    CartItem,

    Rider,
    Order,
    OrderItem,
    Payment,
    SupportTicket,
    ConversationHistory,
)


# =========================================================
# Database Initialization
# =========================================================

def init_db() -> None:
    """
    Create all missing database tables defined by the
    registered SQLAlchemy models.

    Existing tables are not modified.

    For existing databases, schema migrations must be
    handled separately.
    """

    Base.metadata.create_all(
        bind=engine,
    )

    print(
        "Database initialized successfully."
    )

    print(
        "All BuyQK tables are ready."
    )


# =========================================================
# Standalone Execution
# =========================================================

if __name__ == "__main__":
    init_db()