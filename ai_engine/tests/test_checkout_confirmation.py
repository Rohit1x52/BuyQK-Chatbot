"""
BuyQK AI - Phase 7B Checkout Confirmation Tests

Requirement protected:

    Confirmation is allowed ONLY when:

        tool_result["success"] is True
        AND
        tool_result["type"] == "order_success"

Transactional confirmation values must come from the backend ToolResult:
    order_id
    status
    payment_method
    bill / total / currency

The Response Node must never turn a failed, missing, or unrelated ToolResult
into an order confirmation.
"""

from __future__ import annotations

from typing import Any

from ai_engine.nodes import response_node as response_node_module


FORBIDDEN_CONFIRMATION_PHRASES = (
    "order confirmed",
    "order placed",
    "payment successful",
)


def _confirmation_state(tool_result: Any) -> dict[str, Any]:
    return {
        "message": "place the order",
        "intent": "order_create",
        "tool_name": "create_order",
        "tool_result": tool_result,
        "missing_fields": [],
        "next_missing": None,
        "entities": {},
        "checkout_id": "checkout-confirmation-test",
        "checkout_status": "completed",
        "order_created": True,
        "checkout_completed": True,
    }


def _assert_no_false_confirmation(response: str) -> None:
    normalized = response.casefold()

    for phrase in FORBIDDEN_CONFIRMATION_PHRASES:
        assert phrase not in normalized


# =========================================================
# TEST 1
# Successful ToolResult -> confirmation allowed
# =========================================================

def test_successful_order_tool_result_allows_confirmation() -> None:
    tool_result = {
        "success": True,
        "type": "order_success",
        "order_id": 81234,
        "status": "created",
        "payment_method": "backend_method",
        "bill": {
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
        },
    }

    result = response_node_module.response_node(
        _confirmation_state(tool_result)
    )

    response = result["response"]

    assert "Your order has been placed." in response
    assert "#81234" in response
    assert "created" in response
    assert "backend_method" in response
    assert "Total: 235." in response
    assert "Currency: TEST." in response

    assert result["metadata"]["order_id"] == 81234


# =========================================================
# TEST 2
# Failed ToolResult -> no confirmation
# =========================================================

def test_failed_tool_result_never_confirms_order() -> None:
    tool_result = {
        "success": False,
        "type": "order_error",
        "error": "Synthetic backend order failure",
    }

    result = response_node_module.response_node(
        _confirmation_state(tool_result)
    )

    _assert_no_false_confirmation(result["response"])

    assert result.get("order_created") is not True


# =========================================================
# TEST 3
# Missing ToolResult -> no confirmation
# =========================================================

def test_missing_tool_result_never_confirms_order() -> None:
    result = response_node_module.response_node(
        _confirmation_state(None)
    )

    _assert_no_false_confirmation(result["response"])

    assert result.get("order_created") is not True


# =========================================================
# TEST 4
# success=True but wrong type -> no confirmation
# =========================================================

def test_success_without_order_success_type_never_confirms_order() -> None:
    tool_result = {
        "success": True,
        "type": "payment_selection",
        "methods": [
            {
                "code": "backend_method",
            }
        ],
    }

    result = response_node_module.response_node(
        _confirmation_state(tool_result)
    )

    _assert_no_false_confirmation(result["response"])

    assert result.get("order_created") is not True


# =========================================================
# TEST 5
# Confirmation uses backend transactional values
# =========================================================

def test_confirmation_uses_backend_values_without_recalculation() -> None:
    backend_total = 917.43
    backend_order_id = 764321
    backend_payment = "backend_authoritative_payment"
    backend_status = "backend_authoritative_status"

    tool_result = {
        "success": True,
        "type": "order_success",
        "order_id": backend_order_id,
        "status": backend_status,
        "payment_method": backend_payment,
        "bill": {
            "items": [
                {
                    "product_id": 1,
                    "quantity": 3,
                }
            ],
            "subtotal": 1000,
            "delivery_charge": 42.43,
            "discount": 125,
            "tax": 0.00,
            "total": backend_total,
            "currency": "BACKEND",
        },
    }

    result = response_node_module.response_node(
        _confirmation_state(tool_result)
    )

    response = result["response"]

    assert f"#{backend_order_id}" in response
    assert backend_status in response
    assert backend_payment in response
    assert f"Total: {backend_total}." in response
    assert "Currency: BACKEND." in response

    # A different recomputed total must never replace the backend total.
    assert "Total: 917.43." in response

    metadata = result["metadata"]

    assert metadata["order_id"] == backend_order_id
    assert metadata["status"] == backend_status
    assert metadata["payment_method"] == backend_payment
