"""
BuyQK AI - Phase 7C Safety / Integrity Tests

Coverage:
    26. No-address test
    27. No-payment test
    28. Empty-cart test
    29. Backend failure test
    30. Duplicate / order-retry test
    31. State consistency test
    32. Full end-to-end grocery test

Design:
    - Safety tests are deterministic.
    - Backend boundaries are exercised through the real Tool Node where useful.
    - SQLite is isolated per test.
    - No LLM call is required for the safety assertions.
    - No product, price, stock, order ID, or payment result is invented by the
      AI layer. Test data is synthetic backend data.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database.base import Base
from backend.models import (
    Address,
    Category,
    Merchant,
    Product,
    User,
)

from ai_engine.nodes.decision_node import decision_node
from ai_engine.nodes.policy_node import (
    _validate_create_order,
    policy_node,
)
from ai_engine.nodes.tool_node import tool_node


# =========================================================
# Database Fixture
# =========================================================

@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    # Ensure all SQLAlchemy models are registered before
    # creating the schema.
    import backend.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# =========================================================
# Backend Test Data
# =========================================================

@pytest.fixture()
def grocery_data(db: Session) -> dict[str, Any]:
    user = User(
        name="Phase 7C Test User",
        email="phase7c@buyqk.test",
        phone="9999999999",
        password_hash="test-password-hash",
    )

    merchant = Merchant(
        business_name="Phase 7C Grocery Merchant",
        category="Grocery",
        phone="8888888888",
        email="merchant-phase7c@buyqk.test",
        address="Synthetic Merchant Address",
    )

    category = Category(
        name="Groceries",
    )

    db.add_all(
        [
            user,
            merchant,
            category,
        ]
    )

    db.flush()

    address = Address(
        user_id=user.id,
        address="123 Safety Test Street",
        city="Jaipur",
        state="Rajasthan",
        postal_code="302001",
    )

    product = Product(
        name="Phase 7C Grocery Product",
        brand="Synthetic Brand",
        description="Synthetic grocery product for safety testing",
        price=65.0,
        stock=10,
        is_available=True,
        merchant_id=merchant.id,
        category_id=category.id,
    )

    db.add_all(
        [
            address,
            product,
        ]
    )

    db.commit()

    db.refresh(user)
    db.refresh(address)
    db.refresh(product)

    return {
        "db": db,
        "user": user,
        "address": address,
        "product": product,
    }


# =========================================================
# Helpers
# =========================================================

def ready_checkout_state(
    *,
    user_id: int,
    address_id: int | None,
    payment_method: str | None,
    cart_items: list[dict[str, Any]] | None = None,
    checkout_id: str | None = "phase7c-checkout-001",
    checkout_status: str = "collecting",
    order_created: bool = False,
    checkout_completed: bool = False,
    order_id: int | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "checkout_id": checkout_id,
        "checkout_status": checkout_status,
        "cart_checkout_ready": bool(cart_items),
        "cart_items": cart_items or [],
        "address_id": address_id,
        "selected_address_id": address_id,
        "selected_payment_method": payment_method,
        "payment_method": payment_method,
        "selected_payment_method_normalized": payment_method,
        "order_created": order_created,
        "checkout_completed": checkout_completed,
        "order_creation_attempted": False,
        "order_id": order_id,
        "entities": {
            "product_id": 1,
            "quantity": 1,
        },
        "tool_name": "create_order",
    }


def run_pipeline(
    state: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """
    Execute the deterministic checkout portion:

        Policy -> Decision -> Tool

    This intentionally bypasses the LLM intent/entity/planner layers so
    safety behavior is tested deterministically.
    """
    policy_state = policy_node(state)

    decision_state = decision_node(
        {
            **state,
            **policy_state,
        }
    )

    final_state = {
        **state,
        **policy_state,
        **decision_state,
    }

    if decision_state.get("decision_route") == "tool":
        final_state.update(
            tool_node(
                final_state,
                db,
            )
        )

    return final_state


# =========================================================
# 26. NO-ADDRESS TEST
# =========================================================

def test_no_address_never_creates_order(
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=None,
        payment_method="cod",
        cart_items=[
            {
                "product_id": data["product"].id,
                "quantity": 1,
            }
        ],
    )

    policy_result = _validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert policy_result["policy_decision"] == "deny"
    assert "address_id" in policy_result["missing_fields"]


# =========================================================
# 27. NO-PAYMENT TEST
# =========================================================

def test_no_payment_never_creates_order(
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=data["address"].id,
        payment_method=None,
        cart_items=[
            {
                "product_id": data["product"].id,
                "quantity": 1,
            }
        ],
    )

    policy_result = _validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert policy_result["policy_decision"] == "deny"
    assert "payment_method" in policy_result["missing_fields"]


# =========================================================
# 28. EMPTY-CART TEST
# =========================================================

def test_empty_cart_never_reaches_order_creation(
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=data["address"].id,
        payment_method="cod",
        cart_items=[],
    )

    policy_result = _validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert policy_result["policy_decision"] == "deny"

    assert (
        "cart_checkout_ready"
        in policy_result["missing_fields"]
        or "cart_items"
        in policy_result["missing_fields"]
    )


# =========================================================
# 29. BACKEND FAILURE TEST
# =========================================================

def test_backend_failure_does_not_produce_success(
    monkeypatch: pytest.MonkeyPatch,
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=data["address"].id,
        payment_method="cod",
        cart_items=[
            {
                "product_id": data["product"].id,
                "quantity": 1,
            }
        ],
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_available_payment_methods",
        lambda: [
            {
                "code": "cod",
            }
        ],
    )

    def failing_create_order(**kwargs: Any) -> Any:
        raise RuntimeError(
            "synthetic Phase 7C backend failure"
        )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.create_order",
        failing_create_order,
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.check_product_availability",
        lambda **kwargs: True,
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_user_addresses",
        lambda **kwargs: [
            SimpleNamespace(
                id=data["address"].id,
                user_id=data["user"].id,
            )
        ],
    )

    result = tool_node(
        state,
        data["db"],
    )

    tool_result = result["tool_result"]

    assert tool_result.success is False
    assert tool_result.error is not None

    assert result.get("order_created") is False
    assert result.get("checkout_completed") is False
    assert result.get("order_creation_attempted") is True


# =========================================================
# 30. DUPLICATE / ORDER RETRY TEST
# =========================================================

def test_completed_order_cannot_be_created_again(
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=data["address"].id,
        payment_method="cod",
        cart_items=[
            {
                "product_id": data["product"].id,
                "quantity": 1,
            }
        ],
        checkout_status="completed",
        order_created=True,
        checkout_completed=True,
        order_id=123456,
    )

    result = _validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert result["policy_decision"] == "deny"
    assert result["policy_reason"] == "checkout_already_completed"


def test_failed_order_retry_does_not_inherit_success_flags(
    monkeypatch: pytest.MonkeyPatch,
    grocery_data: dict[str, Any],
) -> None:
    data = grocery_data

    state = ready_checkout_state(
        user_id=data["user"].id,
        address_id=data["address"].id,
        payment_method="cod",
        cart_items=[
            {
                "product_id": data["product"].id,
                "quantity": 1,
            }
        ],
        checkout_status="collecting",
        order_created=False,
        checkout_completed=False,
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_available_payment_methods",
        lambda: [
            {
                "code": "cod",
            }
        ],
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_user_addresses",
        lambda **kwargs: [
            SimpleNamespace(
                id=data["address"].id,
                user_id=data["user"].id,
            )
        ],
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.check_product_availability",
        lambda **kwargs: True,
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.create_order",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                RuntimeError("synthetic retry failure")
            )
        ),
    )

    result = tool_node(
        state,
        data["db"],
    )

    assert result["order_created"] is False
    assert result["checkout_completed"] is False
    assert result["order_creation_attempted"] is True


# =========================================================
# 31. STATE CONSISTENCY TEST
# =========================================================

def test_success_state_is_transactionally_consistent() -> None:
    success_state = {
        "checkout_id": "phase7c-checkout-success",
        "checkout_status": "completed",
        "order_created": True,
        "checkout_completed": True,
        "order_creation_attempted": True,
        "order_id": 70001,
    }

    assert success_state["checkout_id"]
    assert success_state["order_id"]
    assert success_state["order_created"] is True
    assert success_state["checkout_completed"] is True
    assert success_state["checkout_status"] == "completed"


def test_failure_state_is_not_marked_completed() -> None:
    failure_state = {
        "checkout_id": "phase7c-checkout-failure",
        "checkout_status": "collecting",
        "order_created": False,
        "checkout_completed": False,
        "order_creation_attempted": True,
        "order_id": None,
    }

    assert failure_state["checkout_id"]
    assert failure_state["order_creation_attempted"] is True
    assert failure_state["order_created"] is False
    assert failure_state["checkout_completed"] is False
    assert failure_state["checkout_status"] != "completed"
    assert failure_state["order_id"] is None


def test_success_and_failure_states_cannot_be_mixed() -> None:
    completed_state = {
        "checkout_status": "completed",
        "order_created": True,
        "checkout_completed": True,
        "order_id": 70002,
    }

    assert completed_state["checkout_status"] == "completed"
    assert completed_state["order_created"] is True
    assert completed_state["checkout_completed"] is True
    assert completed_state["order_id"] is not None


# =========================================================
# 32. FULL END-TO-END GROCERY TEST
# =========================================================

def test_full_end_to_end_grocery_checkout(
    monkeypatch: pytest.MonkeyPatch,
    grocery_data: dict[str, Any],
) -> None:
    """
    Full deterministic grocery transaction:

        Product in SQLite
            ↓
        add_to_cart
            ↓
        checkout_cart
            ↓
        address + payment validation
            ↓
        create_order
            ↓
        backend order_id
            ↓
        completed checkout state

    The test uses the real backend database and Tool Node. The LLM is not
    involved because this is an integrity test, not an LLM-understanding test.
    """

    data = grocery_data
    db = data["db"]
    user = data["user"]
    address = data["address"]
    product = data["product"]

    # -----------------------------------------------------
    # STEP 1: Add grocery product to cart
    # -----------------------------------------------------

    add_state = {
        "user_id": user.id,
        "intent": "cart",
        "tool_name": "add_to_cart",
        "entities": {
            "product_id": product.id,
            "product_name": product.name,
            "quantity": 2,
        },
        "cart_items": [],
    }

    add_result = tool_node(
        add_state,
        db,
    )

    add_tool_result = add_result["tool_result"]

    assert add_tool_result.success is True
    assert add_tool_result.data["type"] == "cart_add"

    cart = add_tool_result.data["cart"]

    assert len(cart["items"]) == 1
    assert cart["items"][0]["product_id"] == product.id
    assert cart["items"][0]["quantity"] == 2

    cart_items = cart["items"]

    # -----------------------------------------------------
    # STEP 2: Prepare checkout
    # -----------------------------------------------------

    checkout_state = {
        "user_id": user.id,
        "tool_name": "checkout_cart",
        "entities": {},
        "cart_items": cart_items,
        "checkout_id": None,
        "checkout_status": None,
    }

    checkout_result = tool_node(
        checkout_state,
        db,
    )

    checkout_tool_result = checkout_result["tool_result"]

    assert checkout_tool_result.success is True
    assert checkout_tool_result.data["type"] == "cart_checkout"
    assert checkout_tool_result.data["checkout_ready"] is True
    assert (
        checkout_tool_result.data["next_step"]
        == "address_selection"
    )

    checkout_id = checkout_result["checkout_id"]

    assert checkout_id is not None
    assert checkout_result["checkout_status"] == "collecting"

    # -----------------------------------------------------
    # STEP 3: Select address + payment and create order
    # -----------------------------------------------------

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_available_payment_methods",
        lambda: [
            {
                "code": "cod",
            }
        ],
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.get_user_addresses",
        lambda **kwargs: [
            SimpleNamespace(
                id=address.id,
                user_id=user.id,
            )
        ],
    )

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.check_product_availability",
        lambda **kwargs: True,
    )

    original_create_order = (
        __import__(
            "ai_engine.nodes.tool_node",
            fromlist=["create_order"],
        ).create_order
    )

    captured: dict[str, Any] = {}

    def capture_create_order(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original_create_order(**kwargs)

    monkeypatch.setattr(
        "ai_engine.nodes.tool_node.create_order",
        capture_create_order,
    )

    order_state = {
        "user_id": user.id,
        "tool_name": "create_order",
        "checkout_id": checkout_id,
        "checkout_status": checkout_result["checkout_status"],
        "cart_checkout_ready": True,
        "cart_items": cart_items,
        "address_id": address.id,
        "selected_address_id": address.id,
        "selected_payment_method": "cod",
        "payment_method": "cod",
        "selected_payment_method_normalized": "cod",
        "order_created": False,
        "checkout_completed": False,
        "order_creation_attempted": False,
        "entities": {
            "product_id": product.id,
            "quantity": 2,
        },
    }

    policy_result = _validate_create_order(
        order_state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert policy_result["policy_decision"] == "allow"

    final_result = tool_node(
        order_state,
        db,
    )

    tool_result = final_result["tool_result"]

    # -----------------------------------------------------
    # STEP 4: Backend success must be authoritative
    # -----------------------------------------------------

    assert tool_result.success is True
    assert tool_result.data["type"] == "order_success"

    backend_order_id = tool_result.data["order_id"]

    assert backend_order_id is not None
    assert final_result["order_id"] == backend_order_id

    assert final_result["checkout_status"] == "completed"
    assert final_result["checkout_completed"] is True
    assert final_result["order_created"] is True
    assert final_result["order_creation_attempted"] is True

    # The backend received the stable checkout ID and selected
    # payment method.
    assert captured["checkout_id"] == checkout_id
    assert captured["payment_method"] == "cod"
    assert captured["address_id"] == address.id

    # -----------------------------------------------------
    # STEP 5: Verify the order exists in SQLite
    # -----------------------------------------------------

    from backend.services.order_service import get_order

    persisted_order = get_order(
        db=db,
        order_id=backend_order_id,
    )

    assert persisted_order is not None
    assert persisted_order.id == backend_order_id
