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

from sqlalchemy import inspect, text


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

# Importing the models ensures that SQLAlchemy registers
# their tables with Base.metadata before create_all().
#
# Cart and CartItem are included as part of Phase 3.
#
# Service booking models are included as part of Phase 11.
#
# Merchant/Rider document models are included as part of
# Phase 12.
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
    Restaurant,
    Menu,
    MenuItem,
    Service,
    Professional,
    ProfessionalService,
    Availability,
    Booking,
    MerchantDocument,
    RiderDocument,
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
    Check whether a SQLite table contains a column.
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
    # Ensure checkout_id index.
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


def _migrate_products_table(
    connection,
) -> None:
    """
    Perform lightweight migrations required by the current
    Product model.

    New Product fields:

        products.model_number
        products.specifications
        products.prescription_required

    Existing product records remain valid:

        model_number = NULL
        specifications = NULL
        prescription_required = 0
    """

    if not _table_exists(
        connection,
        "products",
    ):
        return

    # ---------------------------------------------------------
    # Add model_number.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "products",
        "model_number",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "products.model_number ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE products
                ADD COLUMN model_number VARCHAR(150)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "products.model_number added."
        )

    # ---------------------------------------------------------
    # Add specifications.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "products",
        "specifications",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "products.specifications ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE products
                ADD COLUMN specifications JSON
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "products.specifications added."
        )

    # ---------------------------------------------------------
    # Add prescription_required.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "products",
        "prescription_required",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "products.prescription_required ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE products
                ADD COLUMN prescription_required
                BOOLEAN NOT NULL DEFAULT 0
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "products.prescription_required added."
        )

    # ---------------------------------------------------------
    # Ensure indexes exist.
    # ---------------------------------------------------------

    index_result = connection.execute(
        text(
            'PRAGMA index_list("products")'
        )
    )

    existing_indexes = {
        row[1]
        for row in index_result.fetchall()
        if len(row) >= 2
    }

    if "ix_products_model_number" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_products_model_number ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_products_model_number
                ON products(model_number)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_products_model_number created."
        )

    if (
        "ix_products_prescription_required"
        not in existing_indexes
    ):
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_products_prescription_required ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_products_prescription_required
                ON products(prescription_required)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_products_prescription_required created."
        )


# =========================================================
# Phase 12 Merchant Schema Migration
# =========================================================


def _migrate_merchants_table(
    connection,
) -> None:
    """
    Perform lightweight migrations required by Phase 12
    Merchant onboarding.

    New Merchant fields:

        merchants.onboarding_status
        merchants.approval_status

    Existing merchant records remain valid:

        onboarding_status = 'not_started'
        approval_status = 'pending'

    The existing verification_status column is preserved.
    """

    if not _table_exists(
        connection,
        "merchants",
    ):
        return

    # ---------------------------------------------------------
    # Add onboarding_status.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "merchants",
        "onboarding_status",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "merchants.onboarding_status ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE merchants
                ADD COLUMN onboarding_status
                VARCHAR(30) NOT NULL
                DEFAULT 'not_started'
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "merchants.onboarding_status added."
        )

    # ---------------------------------------------------------
    # Add approval_status.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "merchants",
        "approval_status",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "merchants.approval_status ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE merchants
                ADD COLUMN approval_status
                VARCHAR(30) NOT NULL
                DEFAULT 'pending'
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "merchants.approval_status added."
        )

    # ---------------------------------------------------------
    # Ensure indexes exist.
    # ---------------------------------------------------------

    index_result = connection.execute(
        text(
            'PRAGMA index_list("merchants")'
        )
    )

    existing_indexes = {
        row[1]
        for row in index_result.fetchall()
        if len(row) >= 2
    }

    if "ix_merchants_onboarding_status" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_merchants_onboarding_status ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_merchants_onboarding_status
                ON merchants(onboarding_status)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_merchants_onboarding_status created."
        )

    if "ix_merchants_approval_status" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_merchants_approval_status ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_merchants_approval_status
                ON merchants(approval_status)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_merchants_approval_status created."
        )


# =========================================================
# Phase 12 Rider Schema Migration
# =========================================================


def _migrate_riders_table(
    connection,
) -> None:
    """
    Perform lightweight migrations required by Phase 12
    Rider onboarding.

    New Rider fields:

        riders.onboarding_status
        riders.approval_status

    Existing rider records remain valid:

        onboarding_status = 'not_started'
        approval_status = 'pending'

    The existing verification_status column is preserved.
    """

    if not _table_exists(
        connection,
        "riders",
    ):
        return

    # ---------------------------------------------------------
    # Add onboarding_status.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "riders",
        "onboarding_status",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "riders.onboarding_status ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE riders
                ADD COLUMN onboarding_status
                VARCHAR(30) NOT NULL
                DEFAULT 'not_started'
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "riders.onboarding_status added."
        )

    # ---------------------------------------------------------
    # Add approval_status.
    # ---------------------------------------------------------

    if not _column_exists(
        connection,
        "riders",
        "approval_status",
    ):
        print(
            "[DATABASE MIGRATION] Adding "
            "riders.approval_status ..."
        )

        connection.execute(
            text(
                """
                ALTER TABLE riders
                ADD COLUMN approval_status
                VARCHAR(30) NOT NULL
                DEFAULT 'pending'
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "riders.approval_status added."
        )

    # ---------------------------------------------------------
    # Ensure indexes exist.
    # ---------------------------------------------------------

    index_result = connection.execute(
        text(
            'PRAGMA index_list("riders")'
        )
    )

    existing_indexes = {
        row[1]
        for row in index_result.fetchall()
        if len(row) >= 2
    }

    if "ix_riders_onboarding_status" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_riders_onboarding_status ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_riders_onboarding_status
                ON riders(onboarding_status)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_riders_onboarding_status created."
        )

    if "ix_riders_approval_status" not in existing_indexes:
        print(
            "[DATABASE MIGRATION] Creating "
            "ix_riders_approval_status ..."
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_riders_approval_status
                ON riders(approval_status)
                """
            )
        )

        print(
            "[DATABASE MIGRATION] "
            "ix_riders_approval_status created."
        )


# =========================================================
# Payment Schema Migration
# =========================================================


def _payment_order_id_is_nullable(
    connection,
) -> bool:
    """
    Check whether payments.order_id is nullable.

    SQLite PRAGMA table_info returns:

        0 = cid
        1 = name
        2 = type
        3 = notnull
        4 = default
        5 = primary key
    """

    result = connection.execute(
        text(
            'PRAGMA table_info("payments")'
        )
    )

    for row in result.fetchall():
        if row[1] == "order_id":
            return not bool(row[3])

    return False


def _payment_has_exactly_one_parent_constraint(
    connection,
) -> bool:
    """
    Check whether the current payments table contains the
    generic Payment parent constraint.

    The constraint requires exactly one of:

        order_id
        booking_id

    to be populated.
    """

    result = connection.execute(
        text(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'payments'
            """
        )
    )

    row = result.first()

    if row is None or row[0] is None:
        return False

    table_sql = row[0].lower()

    return (
        "ck_payment_exactly_one_parent" in table_sql
        or (
            "order_id is not null" in table_sql
            and "booking_id is null" in table_sql
            and "order_id is null" in table_sql
            and "booking_id is not null" in table_sql
        )
    )


def _validate_existing_payment_data(
    connection,
) -> None:
    """
    Validate existing payment records before rebuilding the
    payments table.

    Legacy payments should normally have:

        order_id populated
        booking_id NULL

    If a partially migrated database already contains booking_id,
    the data must still satisfy the exactly-one-parent invariant.
    """

    if not _column_exists(
        connection,
        "payments",
        "booking_id",
    ):
        invalid_result = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM payments
                WHERE order_id IS NULL
                """
            )
        )
    else:
        invalid_result = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM payments
                WHERE
                    (order_id IS NULL AND booking_id IS NULL)
                    OR
                    (order_id IS NOT NULL AND booking_id IS NOT NULL)
                """
            )
        )

    invalid_count = int(
        invalid_result.scalar() or 0
    )

    if invalid_count:
        raise RuntimeError(
            "Cannot migrate the BuyQK payments table because "
            f"{invalid_count} existing payment record(s) violate "
            "the exactly-one-parent rule."
        )


def _migrate_payments_table(
    connection,
) -> None:
    """
    Safely migrate the legacy Payment table to support both
    Order payments and Booking payments.

    Legacy schema:

        order_id NOT NULL

    New schema:

        order_id   NULLABLE
        booking_id NULLABLE

    Exactly one of order_id / booking_id must be populated.

    SQLite cannot safely ALTER an existing NOT NULL column to
    nullable or add a table-level CHECK constraint in place.

    Therefore the migration uses the standard SQLite table
    rebuild strategy:

        1. Validate existing payment data.
        2. Rename the existing payments table.
        3. Create the new payments table.
        4. Copy all existing payment records.
        5. Recreate indexes.
        6. Drop the legacy table.

    Existing order payment records remain unchanged.
    """

    if not _table_exists(
        connection,
        "payments",
    ):
        return

    has_booking_id = _column_exists(
        connection,
        "payments",
        "booking_id",
    )

    order_id_nullable = _payment_order_id_is_nullable(
        connection
    )

    has_parent_constraint = (
        _payment_has_exactly_one_parent_constraint(
            connection
        )
    )

    if (
        has_booking_id
        and order_id_nullable
        and has_parent_constraint
    ):
        return

    print(
        "[DATABASE MIGRATION] Migrating "
        "payments table for generic Order/Booking payments ..."
    )

    _validate_existing_payment_data(
        connection
    )

    legacy_table_name = "payments_legacy"

    if _table_exists(
        connection,
        legacy_table_name,
    ):
        raise RuntimeError(
            "Cannot migrate the payments table because the "
            "temporary payments_legacy table already exists. "
            "Inspect the database before retrying."
        )

    connection.execute(
        text(
            """
            ALTER TABLE payments
            RENAME TO payments_legacy
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE TABLE payments (
                id INTEGER NOT NULL PRIMARY KEY,

                order_id INTEGER NULL,

                booking_id INTEGER NULL,

                transaction_id VARCHAR(150) NULL,

                payment_method VARCHAR(50) NOT NULL,

                payment_status VARCHAR(30) NOT NULL
                    DEFAULT 'pending',

                amount FLOAT NOT NULL,

                created_at DATETIME NOT NULL,

                updated_at DATETIME NOT NULL,

                CONSTRAINT uq_payments_order_id
                    UNIQUE (order_id),

                CONSTRAINT uq_payments_booking_id
                    UNIQUE (booking_id),

                CONSTRAINT uq_payments_transaction_id
                    UNIQUE (transaction_id),

                CONSTRAINT ck_payment_exactly_one_parent
                    CHECK (
                        (
                            order_id IS NOT NULL
                            AND booking_id IS NULL
                        )
                        OR
                        (
                            order_id IS NULL
                            AND booking_id IS NOT NULL
                        )
                    ),

                FOREIGN KEY(order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(booking_id)
                    REFERENCES bookings(id)
                    ON DELETE CASCADE
            )
            """
        )
    )

    if has_booking_id:
        connection.execute(
            text(
                """
                INSERT INTO payments (
                    id,
                    order_id,
                    booking_id,
                    transaction_id,
                    payment_method,
                    payment_status,
                    amount,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    order_id,
                    booking_id,
                    transaction_id,
                    payment_method,
                    payment_status,
                    amount,
                    created_at,
                    updated_at
                FROM payments_legacy
                """
            )
        )
    else:
        connection.execute(
            text(
                """
                INSERT INTO payments (
                    id,
                    order_id,
                    booking_id,
                    transaction_id,
                    payment_method,
                    payment_status,
                    amount,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    order_id,
                    NULL,
                    transaction_id,
                    payment_method,
                    payment_status,
                    amount,
                    created_at,
                    updated_at
                FROM payments_legacy
                """
            )
        )

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_payments_order_id
            ON payments(order_id)
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_payments_booking_id
            ON payments(booking_id)
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_payments_transaction_id
            ON payments(transaction_id)
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_payments_payment_status
            ON payments(payment_status)
            """
        )
    )

    connection.execute(
        text(
            """
            DROP TABLE payments_legacy
            """
        )
    )

    print(
        "[DATABASE MIGRATION] "
        "payments table migrated successfully."
    )


# =========================================================
# Database Initialization
# =========================================================

def _migrate_addresses_table(connection) -> None:
    """Add saved-address archival state to existing databases."""
    inspector = inspect(connection)
    if not inspector.has_table("addresses"):
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("addresses")
    }
    if "is_deleted" not in columns:
        connection.execute(
            text(
                "ALTER TABLE addresses "
                "ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"
            )
        )


def init_db() -> None:
    """
    Initialize the BuyQK database.

    The sequence is:

        1. Register models.
        2. Migrate known existing-table changes that do not
           depend on newly-created tables.
        3. Create missing tables.
        4. Migrate the existing Payment table if required.
        5. Bootstrap the product catalog.
        6. Verify completion.
    """

    print(
        "============================================================"
    )

    print(
        "[DATABASE] Initializing BuyQK database..."
    )

    # ---------------------------------------------------------
    # Existing database migrations
    #
    # Orders, products, merchants, and riders can be migrated
    # independently before new tables are created.
    # ---------------------------------------------------------

    with engine.begin() as connection:

        _migrate_orders_table(
            connection
        )

        _migrate_products_table(
            connection
        )

        _migrate_merchants_table(
            connection
        )

        _migrate_riders_table(
            connection
        )

        _migrate_addresses_table(
            connection
        )

    # ---------------------------------------------------------
    # Create missing tables.
    #
    # This must happen BEFORE the payment migration because
    # payments.booking_id references bookings.id.
    #
    # Phase 12 document tables are also created here:
    #
    #     merchant_documents
    #     rider_documents
    #
    # On an existing database:
    #     - existing tables remain unchanged
    #     - missing tables are created
    #
    # On a new database:
    #     - the complete current schema is created
    # ---------------------------------------------------------

    Base.metadata.create_all(
        bind=engine,
    )

    # ---------------------------------------------------------
    # Payment migration
    #
    # Existing SQLite databases may contain the old Payment
    # schema where order_id is NOT NULL.
    #
    # create_all() cannot modify that existing table, so the
    # table must be explicitly rebuilt.
    # ---------------------------------------------------------

    with engine.begin() as connection:

        _migrate_payments_table(
            connection
        )

    # ---------------------------------------------------------
    # Product catalog bootstrap
    # ---------------------------------------------------------

    try:
        from backend.database.sqlite import SessionLocal
        from backend.models.product import Product

        with SessionLocal() as db:

            if db.query(Product).count() == 0:

                print(
                    "[DATABASE] Product catalog is empty; "
                    "bootstrapping seed catalog..."
                )

                from backend.seed_products import seed_products

                seed_products(
                    auto_init=False
                )

    except Exception as exc:

        print(
            "[DATABASE] Product catalog bootstrap failed: "
            f"{type(exc).__name__}: {exc}"
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