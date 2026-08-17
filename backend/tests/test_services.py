# Purpose:
# End-to-end tests for the BuyQK MVP service layer.
#
# Tests:
# 1. Product service
# 2. Order service
# 3. Support service
#
# The tests use a temporary SQLite database and therefore
# do not modify the application's real database.


import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------
# Make backend/ available for imports
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------
# SQLAlchemy
# ---------------------------------------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------
# Database Base
# ---------------------------------------------------------

from backend.database.base import Base


# ---------------------------------------------------------
# Import ALL models.
#
# This is important because SQLAlchemy needs all model
# classes registered before create_all() is called.
# ---------------------------------------------------------

from backend import models


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

from backend.models.user import User
from backend.models.address import Address
from backend.models.category import Category
from backend.models.merchant import Merchant
from backend.models.product import Product


# ---------------------------------------------------------
# Services
# ---------------------------------------------------------

from services.product_service import (
    search_products,
    get_product,
    check_product_availability,
)

from services.order_service import (
    create_order,
    get_order,
    get_user_orders,
    cancel_order,
)

from services.support_service import (
    create_ticket,
    get_ticket,
    get_user_tickets,
)


# =========================================================
# Test Database
# =========================================================

def create_test_database():
    """
    Create an isolated temporary SQLite database
    for service testing.
    """

    temp_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temp_directory.name)
        / "test_services.db"
    )

    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={
            "check_same_thread": False
        },
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    # Create all tables.
    Base.metadata.create_all(
        bind=engine
    )

    return (
        temp_directory,
        engine,
        SessionLocal,
    )


# =========================================================
# Seed Test Data
# =========================================================

def seed_test_data(db):
    """
    Insert minimal data required by the service tests.
    """

    # -----------------------------------------------------
    # User
    # -----------------------------------------------------

    user = User(
        name="Test User",
        email="test@buyqk.com",
        phone="9999999999",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    address = Address(
        user_id=user.id,
        address_line_1="Test Address",
        city="Jaipur",
        state="Rajasthan",
        postal_code="302001",
    )

    db.add(address)

    # -----------------------------------------------------
    # Category
    # -----------------------------------------------------

    category = Category(
        name="Groceries",
    )

    db.add(category)
    db.flush()

    # -----------------------------------------------------
    # Merchant
    # -----------------------------------------------------

    merchant = Merchant(
        business_name="Test Merchant",
        category="Grocery",
        phone="9876543210",
        email="merchant@buyqk.test",
        address="Test Merchant Address",
    )

    db.add(merchant)
    db.flush()

    # -----------------------------------------------------
    # Products
    # -----------------------------------------------------

    milk = Product(
        name="Amul Gold Milk",
        brand="Amul",
        description="Full cream milk",
        price=65,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    bread = Product(
        name="Brown Bread",
        brand="Harvest",
        description="Fresh brown bread",
        price=45,
        stock=5,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    unavailable_product = Product(
        name="Unavailable Milk",
        brand="TestBrand",
        description="Unavailable test product",
        price=50,
        stock=0,
        is_available=False,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    db.add_all(
        [
            milk,
            bread,
            unavailable_product,
        ]
    )

    db.commit()

    return {
        "user": user,
        "address": address,
        "category": category,
        "merchant": merchant,
        "milk": milk,
        "bread": bread,
        "unavailable_product": unavailable_product,
    }


# =========================================================
# PRODUCT SERVICE TESTS
# =========================================================

def test_product_service(db, data):
    """
    Test all MVP product-service operations.
    """

    print("\n" + "=" * 60)
    print("PRODUCT SERVICE")
    print("=" * 60)

    # -----------------------------------------------------
    # search_products()
    # -----------------------------------------------------

    results = search_products(
        db=db,
        query="Amul",
    )

    assert len(results) >= 1

    assert results[0].name == (
        "Amul Gold Milk"
    )

    print(
        "✓ search_products()"
    )

    # -----------------------------------------------------
    # Case-insensitive search
    # -----------------------------------------------------

    results = search_products(
        db=db,
        query="amul",
    )

    assert len(results) >= 1

    print(
        "✓ Case-insensitive product search"
    )

    # -----------------------------------------------------
    # Empty search
    # -----------------------------------------------------

    results = search_products(
        db=db,
        query="",
    )

    assert results == []

    print(
        "✓ Empty search handled"
    )

    # -----------------------------------------------------
    # get_product()
    # -----------------------------------------------------

    product = get_product(
        db=db,
        product_id=data["milk"].id,
    )

    assert product is not None

    assert product.name == (
        "Amul Gold Milk"
    )

    print(
        "✓ get_product()"
    )

    # -----------------------------------------------------
    # Non-existing product
    # -----------------------------------------------------

    product = get_product(
        db=db,
        product_id=999999,
    )

    assert product is None

    print(
        "✓ Non-existing product handled"
    )

    # -----------------------------------------------------
    # Available product
    # -----------------------------------------------------

    available = check_product_availability(
        db=db,
        product_id=data["milk"].id,
        quantity=2,
    )

    assert available is True

    print(
        "✓ Product availability check"
    )

    # -----------------------------------------------------
    # Insufficient stock
    # -----------------------------------------------------

    available = check_product_availability(
        db=db,
        product_id=data["milk"].id,
        quantity=100,
    )

    assert available is False

    print(
        "✓ Insufficient stock handled"
    )

    # -----------------------------------------------------
    # Unavailable product
    # -----------------------------------------------------

    available = check_product_availability(
        db=db,
        product_id=(
            data["unavailable_product"].id
        ),
        quantity=1,
    )

    assert available is False

    print(
        "✓ Unavailable product handled"
    )


# =========================================================
# ORDER SERVICE TESTS
# =========================================================

def test_order_service(db, data):
    """
    Test all MVP order-service operations.
    """

    print("\n" + "=" * 60)
    print("ORDER SERVICE")
    print("=" * 60)

    user_id = data["user"].id
    address_id = data["address"].id
    milk_id = data["milk"].id

    # Store original stock.
    original_stock = data["milk"].stock

    # -----------------------------------------------------
    # Create Order
    # -----------------------------------------------------

    order = create_order(
        db=db,
        user_id=user_id,
        address_id=address_id,
        items=[
            {
                "product_id": milk_id,
                "quantity": 2,
            }
        ],
    )

    assert order.id is not None

    print(
        f"✓ create_order() → Order #{order.id}"
    )

    # -----------------------------------------------------
    # Verify total
    #
    # 2 × ₹65 = ₹130
    # -----------------------------------------------------

    assert float(order.total_amount) == 130.0

    print(
        "✓ Order total calculated correctly"
    )

    # -----------------------------------------------------
    # Verify order item
    # -----------------------------------------------------

    assert len(order.items) == 1

    order_item = order.items[0]

    assert order_item.product_id == milk_id
    assert order_item.quantity == 2
    assert float(order_item.unit_price) == 65.0

    print(
        "✓ OrderItem created correctly"
    )

    # -----------------------------------------------------
    # Verify stock was reduced
    # -----------------------------------------------------

    db.refresh(data["milk"])

    assert data["milk"].stock == (
        original_stock - 2
    )

    print(
        "✓ Product stock reduced correctly"
    )

    # -----------------------------------------------------
    # get_order()
    # -----------------------------------------------------

    retrieved_order = get_order(
        db=db,
        order_id=order.id,
    )

    assert retrieved_order is not None

    assert retrieved_order.id == order.id

    print(
        "✓ get_order()"
    )

    # -----------------------------------------------------
    # get_user_orders()
    # -----------------------------------------------------

    user_orders = get_user_orders(
        db=db,
        user_id=user_id,
    )

    assert len(user_orders) >= 1

    assert any(
        item.id == order.id
        for item in user_orders
    )

    print(
        "✓ get_user_orders()"
    )

    # -----------------------------------------------------
    # Cancel Order
    # -----------------------------------------------------

    cancelled_order = cancel_order(
        db=db,
        order_id=order.id,
        user_id=user_id,
    )

    assert cancelled_order.status == (
        "cancelled"
    )

    print(
        "✓ cancel_order()"
    )

    # -----------------------------------------------------
    # Verify stock restored
    # -----------------------------------------------------

    db.refresh(data["milk"])

    assert data["milk"].stock == (
        original_stock
    )

    print(
        "✓ Product stock restored after cancellation"
    )


# =========================================================
# SUPPORT SERVICE TESTS
# =========================================================

def test_support_service(db, data):
    """
    Test all MVP support-service operations.
    """

    print("\n" + "=" * 60)
    print("SUPPORT SERVICE")
    print("=" * 60)

    user_id = data["user"].id

    # -----------------------------------------------------
    # Create ticket without order
    # -----------------------------------------------------

    ticket = create_ticket(
        db=db,
        user_id=user_id,
        subject="Payment issue",
        description=(
            "My payment failed during checkout."
        ),
    )

    assert ticket.id is not None

    assert ticket.status == "open"

    print(
        f"✓ create_ticket() → Ticket #{ticket.id}"
    )

    # -----------------------------------------------------
    # Get ticket
    # -----------------------------------------------------

    retrieved_ticket = get_ticket(
        db=db,
        ticket_id=ticket.id,
        user_id=user_id,
    )

    assert retrieved_ticket is not None

    assert retrieved_ticket.id == ticket.id

    print(
        "✓ get_ticket()"
    )

    # -----------------------------------------------------
    # Get user tickets
    # -----------------------------------------------------

    tickets = get_user_tickets(
        db=db,
        user_id=user_id,
    )

    assert len(tickets) >= 1

    assert any(
        item.id == ticket.id
        for item in tickets
    )

    print(
        "✓ get_user_tickets()"
    )

    # -----------------------------------------------------
    # Create ticket associated with an order
    # -----------------------------------------------------

    # Create another order for this test.
    order = create_order(
        db=db,
        user_id=user_id,
        address_id=data["address"].id,
        items=[
            {
                "product_id": data["bread"].id,
                "quantity": 1,
            }
        ],
    )

    order_ticket = create_ticket(
        db=db,
        user_id=user_id,
        subject="Order issue",
        description=(
            "There is an issue with my order."
        ),
        order_id=order.id,
    )

    assert order_ticket.order_id == (
        order.id
    )

    print(
        "✓ Ticket linked to user's order"
    )

    # -----------------------------------------------------
    # Security test:
    #
    # Invalid order should not be accepted.
    # -----------------------------------------------------

    try:

        create_ticket(
            db=db,
            user_id=user_id,
            subject="Invalid order",
            description="Testing invalid order.",
            order_id=999999,
        )

        raise AssertionError(
            "Expected ValueError for invalid order."
        )

    except ValueError:

        print(
            "✓ Invalid order rejected"
        )


# =========================================================
# Main Test Runner
# =========================================================

def main():
    """
    Run the complete BuyQK service-layer test suite.
    """

    print("\n")
    print("=" * 60)
    print("BUYQK MVP SERVICE-LAYER TEST")
    print("=" * 60)

    temporary_directory = None
    engine = None
    db = None

    try:

        # -------------------------------------------------
        # Create temporary database
        # -------------------------------------------------

        (
            temporary_directory,
            engine,
            SessionLocal,
        ) = create_test_database()

        print(
            "✓ Temporary SQLite database created"
        )

        # -------------------------------------------------
        # Create database session
        # -------------------------------------------------

        db = SessionLocal()

        # -------------------------------------------------
        # Seed test data
        # -------------------------------------------------

        data = seed_test_data(
            db
        )

        print(
            "✓ Test data inserted"
        )

        # -------------------------------------------------
        # Product tests
        # -------------------------------------------------

        test_product_service(
            db,
            data,
        )

        # -------------------------------------------------
        # Order tests
        # -------------------------------------------------

        test_order_service(
            db,
            data,
        )

        # -------------------------------------------------
        # Support tests
        # -------------------------------------------------

        test_support_service(
            db,
            data,
        )

    except Exception as exc:

        print("\n" + "=" * 60)
        print("❌ SERVICE-LAYER TEST FAILED")
        print("=" * 60)

        print(
            f"\nError:\n{exc}"
        )

        raise SystemExit(1)

    finally:

        # -------------------------------------------------
        # Close database session
        # -------------------------------------------------

        if db is not None:
            db.close()

        # -------------------------------------------------
        # Dispose SQLAlchemy engine
        # -------------------------------------------------

        if engine is not None:
            engine.dispose()

        # -------------------------------------------------
        # Delete temporary database
        # -------------------------------------------------

        if temporary_directory is not None:
            temporary_directory.cleanup()

    print("\n" + "=" * 60)
    print("✅ ALL SERVICE-LAYER TESTS PASSED")
    print("=" * 60)

    print("\nService layer status:")
    print("  ✓ Product service")
    print("  ✓ Order service")
    print("  ✓ Support service")
    print("  ✓ Transaction handling")
    print("  ✓ Stock management")
    print("  ✓ Order cancellation")
    print("  ✓ Support-ticket validation")
    print()


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":
    main()