# Purpose:
# Tests the BuyQK AI Engine together with the backend
# service layer and SQLite database.
#
# Flow:
#
# User Message
#      ↓
# LangGraph
#      ↓
# Intent
#      ↓
# Entities
#      ↓
# Decision
#      ↓
# Tool Node
#      ↓
# Backend Service
#      ↓
# SQLite
#      ↓
# Tool Result
#      ↓
# Response
#
# Run from project root:
#
#     python -m ai_engine.tests.test_integration
#
# Or:
#
#     pytest ai_engine/tests/test_integration.py -v


import os
import sys
import tempfile


# =========================================================
# Project Path
# =========================================================
#
# This allows the test to work when executed directly
# from the project root.
# =========================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../..",
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )


# =========================================================
# SQLAlchemy
# =========================================================

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker


# =========================================================
# Backend imports
# =========================================================

from backend.database.base import Base

from backend.models import (
    User,
    Address,
    Merchant,
    Category,
    Product,
    Order,
)


# =========================================================
# AI imports
# =========================================================

from ai_engine.graph.runner import (
    run_chat,
)


# =========================================================
# Test Database
# =========================================================

def create_test_database():
    """
    Create a temporary SQLite database for integration tests.

    The database exists only for the duration of the test.
    """

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".db",
        delete=False,
    )

    temp_file.close()

    database_url = (
        f"sqlite:///{temp_file.name}"
    )

    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
        },
    )

    # Create all model tables.
    Base.metadata.create_all(
        bind=engine
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    db = SessionLocal()

    return (
        db,
        engine,
        temp_file.name,
    )


# =========================================================
# Seed Test Data
# =========================================================

def seed_test_data(db):
    """
    Insert the minimum data required to test the
    AI → Service → SQLite workflow.
    """

    # -----------------------------------------------------
    # User
    # -----------------------------------------------------

    user = User(
        # Adjust these fields if your User model has
        # different required columns.
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
        address_line_1="123 Test Street",
        city="Jaipur",
        state="Rajasthan",
        postal_code="302001",
    )

    db.add(address)

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

    # -----------------------------------------------------
    # Category
    # -----------------------------------------------------

    category = Category(
        name="Dairy",
    )

    db.add(category)

    db.flush()

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    product = Product(
        name="Amul Milk",
        brand="Amul",
        price=65.0,
        stock=20,
        merchant_id=merchant.id,
        category_id=category.id,
    )

    db.add(product)

    db.commit()

    db.refresh(user)
    db.refresh(address)
    db.refresh(product)

    return {
        "user": user,
        "address": address,
        "product": product,
    }


# =========================================================
# Test Helpers
# =========================================================

def print_test(
    test_number: int,
    name: str,
):
    print()
    print("=" * 60)
    print(
        f"TEST {test_number}: {name}"
    )
    print("=" * 60)


def assert_true(
    condition: bool,
    message: str,
):
    if not condition:
        raise AssertionError(
            message
        )


def assert_equal(
    actual,
    expected,
    message: str,
):
    if actual != expected:
        raise AssertionError(
            f"{message}\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )


# =========================================================
# TEST 1
# AI → Product Service → SQLite
# =========================================================

def test_product_search(
    db,
    user,
):
    print_test(
        1,
        "AI → Product Service → SQLite",
    )

    result = run_chat(
        message="Find Amul milk",
        session_id="integration-session-001",
        user_id=user.id,
        db=db,
    )

    # -----------------------------------------------------
    # Intent
    # -----------------------------------------------------

    assert_equal(
        result.get("intent"),
        "product_search",
        "Incorrect intent.",
    )

    # -----------------------------------------------------
    # Entity
    # -----------------------------------------------------

    entities = result.get(
        "entities",
        {},
    )

    assert_true(
        "product_name" in entities,
        "Product name was not extracted.",
    )

    # -----------------------------------------------------
    # Tool
    # -----------------------------------------------------

    assert_equal(
        result.get("tool_name"),
        "search_products",
        "Incorrect tool selected.",
    )

    # -----------------------------------------------------
    # Tool result
    # -----------------------------------------------------

    tool_result = result.get(
        "tool_result"
    )

    assert_true(
        tool_result is not None,
        "Tool result is missing.",
    )

    assert_true(
        tool_result.get("success") is True,
        f"Product search failed: {tool_result}",
    )

    products = tool_result.get(
        "products",
        [],
    )

    assert_true(
        len(products) > 0,
        "No products returned from SQLite.",
    )

    # -----------------------------------------------------
    # Verify actual product
    # -----------------------------------------------------

    product = products[0]

    assert_equal(
        product.name,
        "Amul Milk",
        "Incorrect product returned.",
    )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    response = result.get(
        "response",
        "",
    )

    assert_true(
        "Amul Milk" in response,
        "Product name missing from AI response.",
    )

    print(
        "✓ Intent: product_search"
    )

    print(
        "✓ Entity: Amul Milk"
    )

    print(
        "✓ Tool: search_products"
    )

    print(
        "✓ SQLite product found"
    )

    print(
        f"✓ AI response: {response}"
    )


# =========================================================
# TEST 2
# Missing Information
# =========================================================

def test_missing_information(
    db,
    user,
):
    print_test(
        2,
        "AI → Missing Information",
    )

    result = run_chat(
        message="I want Amul milk",
        session_id="integration-session-002",
        user_id=user.id,
        db=db,
    )

    assert_equal(
        result.get("intent"),
        "order_create",
        "Incorrect intent.",
    )

    missing_fields = result.get(
        "missing_fields",
        [],
    )

    assert_true(
        "quantity" in missing_fields,
        "Quantity should be missing.",
    )

    # -----------------------------------------------------
    # No order should be created.
    # -----------------------------------------------------

    assert_equal(
        result.get("tool_name"),
        None,
        "Tool should not execute when information "
        "is missing.",
    )

    response = result.get(
        "response",
        "",
    )

    assert_true(
        len(response) > 0,
        "Clarification response is empty.",
    )

    print(
        "✓ Intent: order_create"
    )

    print(
        "✓ Quantity detected as missing"
    )

    print(
        "✓ No database operation executed"
    )

    print(
        f"✓ AI response: {response}"
    )


# =========================================================
# TEST 3
# Order Tracking
# =========================================================

def test_order_tracking(
    db,
    user,
    address,
    product,
):
    print_test(
        3,
        "AI → Order Service → SQLite",
    )

    # -----------------------------------------------------
    # Create an order directly for test setup.
    #
    # This is setup data, not the behavior being tested.
    # -----------------------------------------------------

    from backend.services.order_service import (
        create_order,
    )

    order = create_order(
        db=db,
        user_id=user.id,
        address_id=address.id,
        items=[
            {
                "product_id": product.id,
                "quantity": 2,
            }
        ],
    )

    db.commit()

    # -----------------------------------------------------
    # Ask AI to track the order.
    # -----------------------------------------------------

    result = run_chat(
        message=f"Where is order {order.id}?",
        session_id="integration-session-003",
        user_id=user.id,
        db=db,
    )

    assert_equal(
        result.get("intent"),
        "order_tracking",
        "Incorrect tracking intent.",
    )

    assert_equal(
        result.get("tool_name"),
        "track_order",
        "Incorrect tracking tool.",
    )

    tool_result = result.get(
        "tool_result"
    )

    assert_true(
        tool_result is not None,
        "Tracking result is missing.",
    )

    assert_true(
        tool_result.get("success") is True,
        f"Order tracking failed: {tool_result}",
    )

    assert_equal(
        tool_result.get("order_id"),
        order.id,
        "Incorrect order returned.",
    )

    response = result.get(
        "response",
        "",
    )

    assert_true(
        str(order.id) in response,
        "Order ID missing from response.",
    )

    print(
        f"✓ Order created for test: #{order.id}"
    )

    print(
        "✓ Intent: order_tracking"
    )

    print(
        "✓ Tool: track_order"
    )

    print(
        "✓ Order retrieved from SQLite"
    )

    print(
        f"✓ AI response: {response}"
    )


# =========================================================
# TEST 4
# Full Integration State
# =========================================================

def test_final_state(
    db,
    user,
):
    print_test(
        4,
        "Final Graph State",
    )

    result = run_chat(
        message="Find Amul milk",
        session_id="integration-session-004",
        user_id=user.id,
        db=db,
    )

    required_fields = [
        "message",
        "session_id",
        "user_id",
        "intent",
        "entities",
        "missing_fields",
        "tool_name",
        "tool_result",
        "response",
        "metadata",
    ]

    for field in required_fields:

        assert_true(
            field in result,
            f"Graph state is missing '{field}'.",
        )

        print(
            f"✓ {field}"
        )


# =========================================================
# Main Test Runner
# =========================================================

def main():

    print()
    print("=" * 60)
    print(
        "BUYQK MVP AI + BACKEND INTEGRATION TEST"
    )
    print("=" * 60)

    db = None
    engine = None
    database_file = None

    passed = 0
    total = 4

    try:

        # -------------------------------------------------
        # Create temporary database
        # -------------------------------------------------

        (
            db,
            engine,
            database_file,
        ) = create_test_database()

        print(
            "✓ Temporary SQLite database created"
        )

        # -------------------------------------------------
        # Seed data
        # -------------------------------------------------

        data = seed_test_data(
            db
        )

        user = data["user"]
        address = data["address"]
        product = data["product"]

        print(
            "✓ Test data seeded"
        )

        # -------------------------------------------------
        # Run tests
        # -------------------------------------------------

        test_product_search(
            db,
            user,
        )

        passed += 1

        test_missing_information(
            db,
            user,
        )

        passed += 1

        test_order_tracking(
            db,
            user,
            address,
            product,
        )

        passed += 1

        test_final_state(
            db,
            user,
        )

        passed += 1

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        print()
        print("=" * 60)
        print(
            "✅ ALL AI + BACKEND INTEGRATION TESTS PASSED"
        )
        print("=" * 60)

        print()
        print(
            f"Passed: {passed}/{total}"
        )

        print()
        print(
            "Integration status:"
        )

        print(
            "  ✓ LangGraph"
        )

        print(
            "  ✓ Tool Node"
        )

        print(
            "  ✓ Product Service"
        )

        print(
            "  ✓ Order Service"
        )

        print(
            "  ✓ SQLite"
        )

        print(
            "  ✓ AI response generation"
        )

    except Exception as exc:

        print()
        print("=" * 60)
        print(
            "❌ AI + BACKEND INTEGRATION TEST FAILED"
        )
        print("=" * 60)

        print()
        print(
            f"Error:\n{exc}"
        )

        raise

    finally:

        # -------------------------------------------------
        # Close database
        # -------------------------------------------------

        if db is not None:
            db.close()

        if engine is not None:
            engine.dispose()

        # -------------------------------------------------
        # Remove temporary database
        # -------------------------------------------------

        if (
            database_file
            and os.path.exists(database_file)
        ):

            os.remove(
                database_file
            )

            print()
            print(
                "✓ Temporary database removed"
            )


if __name__ == "__main__":
    main()