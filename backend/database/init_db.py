"""
BuyQK Database Initialization

This module:

- Imports the SQLAlchemy Base.
- Imports all BuyQK models through models/__init__.py.
- Registers every model with Base.metadata.
- Creates missing database tables.
- Performs required lightweight SQLite MVP migrations.
- Uses the configured SQLite engine.
- Provides a reusable init_db() function.

IMPORTANT:

SQLAlchemy's create_all() creates missing tables but does NOT
modify existing tables.

Therefore this module performs small explicit migrations for
schema changes required by the current BuyQK MVP.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text


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
# SQLite Helpers
# =========================================================


def _table_exists(
    connection,
    table_name: str,
) -> bool:
    """
    Check whether a SQLite table exists.
    """

    result = connection.execute(
        text(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = :table_name
            """
        ),
        {
            "table_name": table_name,
        },
    )

    return result.first() is not None


def _column_exists(
    connection,
    table_name: str,
    column_name: str,
) -> bool:
    """
    Check whether a column exists in a SQLite table.
    """

    result = connection.execute(
        text(
            f'PRAGMA table_info("{table_name}")'
        )
    )

    columns = result.fetchall()

    for column in columns:
        # SQLite PRAGMA table_info:
        #
        # 0 = cid
        # 1 = name
        # 2 = type
        # 3 = notnull
        # 4 = default
        # 5 = primary key

        if column[1] == column_name:
            return True

    return False


def _has_unique_user_checkout_index(
    connection,
) -> bool:
    """
    Determine whether orders already has a UNIQUE index
    covering:

        user_id + checkout_id

    SQLite may represent a UniqueConstraint as an automatically
    generated sqlite_autoindex_* index, so checking only the
    index name is not sufficient.
    """

    index_result = connection.execute(
        text(
            'PRAGMA index_list("orders")'
        )
    )

    indexes = index_result.fetchall()

    for index in indexes:
        # SQLite PRAGMA index_list:
        #
        # 0 = sequence
        # 1 = index name
        # 2 = unique
        #
        if len(index) < 3:
            continue

        index_name = index[1]
        is_unique = bool(index[2])

        if not is_unique:
            continue

        columns_result = connection.execute(
            text(
                f'PRAGMA index_info("{index_name}")'
            )
        )

        index_columns = columns_result.fetchall()

        column_names = [
            row[2]
            for row in index_columns
            if len(row) >= 3
        ]

        if column_names == [
            "user_id",
            "checkout_id",
        ]:
            return True

    return False


def _check_duplicate_checkout_ids(
    connection,
) -> None:
    """
    Check for duplicate non-null checkout IDs before creating
    the unique user+checkout index.

    If duplicates already exist, fail with a useful error instead
    of producing an obscure SQLite UNIQUE constraint error.
    """

    result = connection.execute(
        text(
            """
            SELECT
                user_id,
                checkout_id,
                COUNT(*) AS duplicate_count
            FROM orders
            WHERE checkout_id IS NOT NULL
            GROUP BY
                user_id,
                checkout_id
            HAVING COUNT(*) > 1
            """
        )
    )

    duplicates = result.fetchall()

    if not duplicates:
        return

    formatted = []

    for row in duplicates:
        formatted.append(
            (
                f"user_id={row[0]}, "
                f"checkout_id={row[1]!r}, "
                f"count={row[2]}"
            )
        )

    details = "; ".join(formatted)

    raise RuntimeError(
        "Cannot create the BuyQK checkout idempotency constraint "
        "because duplicate checkout records already exist: "
        f"{details}"
    )


# =========================================================
# MVP Schema Migration
# =========================================================


def _migrate_orders_table(
    connection,
) -> None:
    """
    Perform lightweight migrations required by the current
    Order model.

    Current migration:

        orders.checkout_id

    The original MVP database may have been created before
    checkout_id existed.

    SQLite ALTER TABLE supports adding this nullable column
    without rebuilding the entire table.
    """

    # ---------------------------------------------------------
    # Nothing to migrate if the orders table does not exist.
    #
    # create_all() will create the complete current schema later.
    # ---------------------------------------------------------

    if not _table_exists(
        connection,
        "orders",
    ):
        return

    # ---------------------------------------------------------
    # Add checkout_id if missing.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "orders",
        "checkout_id",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "orders.checkout_id ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE orders
                ADD COLUMN checkout_id VARCHAR(255)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "orders.checkout_id added."
        )

    # ---------------------------------------------------------
    # Ensure an index exists for checkout_id.
    #
    # The model specifies index=True.
    # ---------------------------------------------------------

    index_result = connection.execute(
        text(
            'PRAGMA index_list("orders")'
        )
    )

    existing_indexes = {
        row[1]
        for row in index_result.fetchall()
        if len(row) >= 2
    }

    if "ix_orders_checkout_id" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_orders_checkout_id ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_orders_checkout_id
                ON orders(checkout_id)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_orders_checkout_id created."
        )

    # ---------------------------------------------------------
    # Ensure idempotency constraint.
    #
    # One user + one checkout_id = one order.
    #
    # NULL checkout_id values are allowed for legacy orders.
    # SQLite permits multiple NULL values in a UNIQUE index.
    # ---------------------------------------------------------

    if not _has_unique_user_checkout_index(
        connection
    ):
        _check_duplicate_checkout_ids(
            connection
        )

        print(
            "[DATABASE MIGRATION] Creating "
            "unique user + checkout constraint ..."
        )

        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                uq_orders_user_checkout
                ON orders(user_id, checkout_id)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "Unique checkout constraint created."
        )


# =========================================================
# Database Initialization
# =========================================================


def init_db() -> None:
    """
    Initialize the BuyQK database.

    The sequence is:

        1. Register models.
        2. Migrate known existing-table changes.
        3. Create missing tables.
        4. Verify completion.
    """

    print(
        "============================================================"
    )

    print(
        "[DATABASE] Initializing BuyQK database..."
    )

    # ---------------------------------------------------------
    # Existing database migrations
    # ---------------------------------------------------------

    with engine.begin() as connection:

        _migrate_orders_table(
            connection
        )

    # ---------------------------------------------------------
    # Create missing tables
    # ---------------------------------------------------------

    Base.metadata.create_all(
        bind=engine,
    )

    print(
        "[DATABASE] Database initialized successfully."
    )

    print(
        "[DATABASE] All BuyQK tables are ready."
    )

    print(
        "============================================================"
    )


# =========================================================
# Standalone Execution
# =========================================================

if __name__ == "__main__":
    init_db()