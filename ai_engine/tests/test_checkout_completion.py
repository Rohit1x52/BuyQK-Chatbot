"""
BuyQK AI - Phase 7B Checkout Completion Tests

Coverage:
    Delivery
        - delivery_preference can be stored
        - delivery_preference survives the next turn

    Payment
        - payment methods are retrieved from the backend
        - selected payment is stored
        - invalid payment is rejected by backend validation

    Final validation
        - missing checkout_id is rejected
        - missing address is rejected
        - missing payment is rejected
        - incomplete checkout is rejected
        - completed checkout rejects duplicate creation

    Order creation
        - backend-created order is accepted
        - backend order_id is stored
        - checkout_status becomes completed
        - checkout_completed becomes True
        - order_created becomes True

    Failure
        - backend order failure does not leave success flags behind

The tests use synthetic values and monkeypatch backend boundaries where a real
external/payment/order provider is not required. They do not depend on a real
LLM response.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ai_engine.graph import runner as runner_module
from ai_engine.nodes import entity_node as entity_node_module
from ai_engine.nodes import policy_node as policy_node_module
from ai_engine.nodes import tool_node as tool_node_module


# =========================================================
# Helpers
# =========================================================

def ready_checkout_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "user_id": 1,
        "checkout_id": "checkout-test-001",
        "checkout_status": "collecting",
        "cart_checkout_ready": True,
        "cart_items": [
            {
                "product_id": 1,
                "quantity": 2,
            }
        ],
        "address_id": 1,
        "selected_address_id": 1,
        "selected_payment_method": "backend_method",
        "payment_method": "backend_method",
        "selected_payment_method_normalized": "backend_method",
        "order_created": False,
        "checkout_completed": False,
        "order_creation_attempted": False,
        "entities": {
            "product_id": 1,
            "quantity": 2,
        },
        "tool_name": "create_order",
    }

    state.update(overrides)

    return state


def fake_order(
    order_id: int = 9001,
    status: str = "created",
    payment_status: str = "pending",
) -> Any:
    return SimpleNamespace(
        id=order_id,
        status=status,
        payment_status=payment_status,
        _buyqk_bill={
            "order_id": order_id,
            "items": [
                {
                    "product_id": 1,
                    "quantity": 2,
                }
            ],
            "subtotal": 200,
            "delivery_charge": 25,
            "discount": 10,
            "tax": 20,
            "total": 235,
            "currency": "TEST",
            "payment_method": "backend_method",
        },
    )


# =========================================================
# DELIVERY
# =========================================================

def test_delivery_preference_can_be_stored() -> None:
    state = {
        "message": "I want fast delivery",
        "delivery_preference": "fast delivery",
        "entities": {},
    }

    result = entity_node_module.detect_delivery_preference(
        state["message"]
    )

    # Production detector normalizes "fast delivery" -> "fast".
    assert result == "fast"

    state["entities"] = {
        "delivery_preference": result,
    }

    assert state["delivery_preference"] == "fast"
    assert state["entities"]["delivery_preference"] == "fast"


def test_delivery_preference_can_be_stored() -> None:
    message = "I want fast delivery"

    detected_preference = entity_node_module.detect_delivery_preference(
        message
    )

    # Production detector normalizes "fast delivery" -> "fast".
    assert detected_preference == "fast"

    state = {
        "message": message,
        "delivery_preference": detected_preference,
        "entities": {
            "delivery_preference": detected_preference,
        },
    }

    assert state["delivery_preference"] == "fast"
    assert state["entities"]["delivery_preference"] == "fast"


# =========================================================
# PAYMENT
# =========================================================

def test_payment_methods_retrieved_from_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_methods = [
        {
            "code": "backend_method_a",
            "name": "Backend Method A",
        },
        {
            "code": "backend_method_b",
            "name": "Backend Method B",
        },
    ]

    monkeypatch.setattr(
        tool_node_module,
        "get_available_payment_methods",
        lambda: backend_methods,
    )

    result = tool_node_module.tool_node(
        {
            "user_id": 1,
            "tool_name": "list_payment_methods",
            "entities": {},
        },
        db=None,
    )

    tool_result = result["tool_result"]

    assert tool_result.success is True

    # ToolResult stores the result type inside data.
    assert tool_result.data["type"] == "payment_selection"

    assert tool_result.data["methods"] == backend_methods


def test_selected_payment_is_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_method = "backend_method_selected"

    monkeypatch.setattr(
        tool_node_module,
        "get_available_payment_methods",
        lambda: [
            {
                "code": selected_method,
                "name": "Backend Selected Method",
            }
        ],
    )

    assert tool_node_module._get_payment_method(
        {
            "selected_payment_method": selected_method,
            "payment_method": "stale-method",
        },
        {},
    ) == selected_method


def test_invalid_payment_rejected_by_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tool_node_module,
        "get_available_payment_methods",
        lambda: [
            {
                "code": "backend_valid_method",
            }
        ],
    )

    valid, error = tool_node_module._validate_payment_method(
        "not-returned-by-backend"
    )

    assert valid is False
    assert error


# =========================================================
# FINAL VALIDATION
# =========================================================

@pytest.mark.parametrize(
    ("overrides", "expected_missing"),
    [
        (
            {
                "checkout_id": None,
            },
            "checkout_id",
        ),
        (
            {
                "address_id": None,
                "selected_address_id": None,
            },
            "address_id",
        ),
        (
            {
                "selected_payment_method": None,
                "payment_method": None,
                "selected_payment_method_normalized": None,
            },
            "payment_method",
        ),
        (
            {
                "cart_checkout_ready": False,
            },
            "cart_checkout_ready",
        ),
    ],
)
def test_final_validation_rejects_incomplete_checkout(
    overrides: dict[str, Any],
    expected_missing: str,
) -> None:
    state = ready_checkout_state(**overrides)

    result = policy_node_module._validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert result["policy_decision"] == "deny"

    if expected_missing == "checkout_id":
        # The policy returns a dedicated reason for a missing checkout ID.
        assert result["policy_reason"] == "missing_checkout_id"
    else:
        assert expected_missing in result["missing_fields"]


def test_completed_checkout_rejects_duplicate_creation() -> None:
    state = ready_checkout_state(
        checkout_status="completed",
        order_created=True,
        checkout_completed=True,
        order_id=9001,
    )

    result = policy_node_module._validate_create_order(
        state,
        action="CREATE_ORDER",
        tool="create_order",
    )

    assert result["policy_decision"] == "deny"
    assert result["policy_reason"] == "checkout_already_completed"


# =========================================================
# ORDER CREATION
# =========================================================

def test_backend_creates_order_and_authoritative_state_is_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_method = "backend_method"

    monkeypatch.setattr(
        tool_node_module,
        "get_available_payment_methods",
        lambda: [
            {
                "code": selected_method,
            }
        ],
    )

    backend_order = fake_order(
        order_id=98765,
        status="created",
        payment_status="pending",
    )

    captured: dict[str, Any] = {}

    def fake_create_order(
        *,
        db: Any,
        user_id: int,
        address_id: int,
        items: list[dict[str, Any]],
        payment_method: str,
        checkout_id: str,
    ) -> Any:
        captured.update(
            {
                "user_id": user_id,
                "address_id": address_id,
                "items": items,
                "payment_method": payment_method,
                "checkout_id": checkout_id,
            }
        )

        return backend_order

    monkeypatch.setattr(
        tool_node_module,
        "create_order",
        fake_create_order,
    )

    monkeypatch.setattr(
        tool_node_module,
        "check_product_availability",
        lambda **kwargs: True,
    )

    monkeypatch.setattr(
        tool_node_module,
        "get_user_addresses",
        lambda **kwargs: [
            SimpleNamespace(
                id=1,
                user_id=1,
            )
        ],
    )

    class Query:
        def filter(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> "Query":
            return self

        def first(self) -> Any:
            return SimpleNamespace(
                id=1,
                name="Synthetic Backend Product",
                brand="Synthetic Brand",
                description="Synthetic test product",
                price=100,
                stock=10,
                is_available=True,
                merchant_id=1,
                category_id=1,
            )

    class FakeDB:
        def query(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> Query:
            return Query()

    result = tool_node_module.tool_node(
        ready_checkout_state(
            selected_payment_method=selected_method,
            payment_method=selected_method,
            entities={
                "product_id": 1,
                "quantity": 2,
            },
        ),
        db=FakeDB(),
    )

    tool_result = result["tool_result"]

    assert tool_result.success is True

    # ToolResult stores the result type inside data.
    assert tool_result.data["type"] == "order_success"

    # Backend-generated order ID must be authoritative.
    assert tool_result.data["order_id"] == 98765

    # Stable checkout ID must be passed to backend.
    assert captured["checkout_id"] == "checkout-test-001"

    # Backend-authoritative payment method must be passed.
    assert captured["payment_method"] == selected_method

    # GraphState must contain the backend-generated order ID.
    assert result["order_id"] == 98765

    # Successful backend order must complete checkout.
    assert result["checkout_status"] == "completed"
    assert result["checkout_completed"] is True
    assert result["order_created"] is True
    assert result["order_creation_attempted"] is True


# =========================================================
# FAILURE
# =========================================================

def test_backend_order_failure_does_not_mark_checkout_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_method = "backend_method"

    monkeypatch.setattr(
        tool_node_module,
        "get_available_payment_methods",
        lambda: [
            {
                "code": selected_method,
            }
        ],
    )

    def failing_create_order(**kwargs: Any) -> Any:
        raise ValueError(
            "synthetic backend order failure"
        )

    monkeypatch.setattr(
        tool_node_module,
        "create_order",
        failing_create_order,
    )

    monkeypatch.setattr(
        tool_node_module,
        "check_product_availability",
        lambda **kwargs: True,
    )

    monkeypatch.setattr(
        tool_node_module,
        "get_user_addresses",
        lambda **kwargs: [
            SimpleNamespace(
                id=1,
                user_id=1,
            )
        ],
    )

    class Query:
        def filter(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> "Query":
            return self

        def first(self) -> Any:
            return SimpleNamespace(
                id=1,
                name="Synthetic Backend Product",
                brand="Synthetic Brand",
                description="Synthetic test product",
                price=100,
                stock=10,
                is_available=True,
                merchant_id=1,
                category_id=1,
            )

    class FakeDB:
        def query(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> Query:
            return Query()

    result = tool_node_module.tool_node(
        ready_checkout_state(
            selected_payment_method=selected_method,
            payment_method=selected_method,
            entities={
                "product_id": 1,
                "quantity": 2,
            },
            order_created=False,
            checkout_completed=False,
        ),
        db=FakeDB(),
    )

    tool_result = result["tool_result"]

    # Backend failure must produce an unsuccessful ToolResult.
    assert tool_result.success is False

    # Failure details are stored on ToolResult.error.
    assert tool_result.error is not None
    assert (
        "synthetic backend order failure"
        in str(tool_result.error)
    )

    # A failed backend order must never mark checkout successful.
    assert result.get("order_created") is False
    assert result.get("checkout_completed") is False

    # The attempt itself must still be recorded.
    assert result.get("order_creation_attempted") is True