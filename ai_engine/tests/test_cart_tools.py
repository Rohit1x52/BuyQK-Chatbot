"""
Tests for BuyQK Cart AI Tools.

These tests verify the AI-facing Cart tool boundary.

They intentionally do NOT duplicate the complete CartService test suite.

Responsibilities tested here:

- input validation
- input normalization
- CartService delegation
- commit_cart execution
- successful ToolResult creation
- failed ToolResult creation
- backend/service error normalization
- read-only cart retrieval
- protection against invalid IDs
- protection against invalid quantities
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_engine.tools.results import ToolResult
from ai_engine.tools import cart_tools


# =========================================================
# Test Data
# =========================================================


USER_ID = 1
PRODUCT_ID = 10
QUANTITY = 2

CART_RESPONSE = {
    "cart_id": 100,
    "status": "active",
    "items": [
        {
            "id": 1,
            "product_id": PRODUCT_ID,
            "product_name": "Amul Gold Milk",
            "quantity": QUANTITY,
            "unit_price": 65,
            "line_total": 130,
        }
    ],
    "summary": {
        "item_count": 1,
        "total_quantity": QUANTITY,
        "subtotal": 130.0,
        "total": 130.0,
    },
}


# =========================================================
# Helpers
# =========================================================


def assert_success_result(
    result: ToolResult,
    tool_name: str,
) -> None:
    """Assert the common successful ToolResult contract."""

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == tool_name
    assert result.error is None


def assert_failure_result(
    result: ToolResult,
    tool_name: str,
) -> None:
    """Assert the common failed ToolResult contract."""

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.tool == tool_name
    assert result.data is None
    assert result.error is not None


# =========================================================
# add_to_cart_tool
# =========================================================


def test_add_to_cart_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    add_to_cart_tool delegates to CartService.add_item,
    commits the transaction, and returns ToolResult.
    """

    calls: dict[str, Any] = {}

    def fake_add_item(
        *,
        db: Any,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> dict[str, Any]:

        calls["add_item"] = {
            "db": db,
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
        }

        return CART_RESPONSE

    def fake_commit_cart(
        db: Any,
    ) -> None:

        calls["commit_cart"] = db

    monkeypatch.setattr(
        cart_tools,
        "add_item",
        fake_add_item,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        fake_commit_cart,
    )

    db = object()

    result = cart_tools.add_to_cart_tool(
        db=db,
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=QUANTITY,
    )

    assert_success_result(
        result,
        "add_to_cart",
    )

    assert result.data["action"] == "add_to_cart"
    assert result.data["cart_id"] == 100
    assert result.data["items"] == CART_RESPONSE["items"]
    assert result.data["summary"] == CART_RESPONSE["summary"]

    assert calls["add_item"] == {
        "db": db,
        "user_id": USER_ID,
        "product_id": PRODUCT_ID,
        "quantity": QUANTITY,
    }

    assert calls["commit_cart"] is db


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_id", 0),
        ("user_id", -1),
        ("product_id", 0),
        ("product_id", -10),
        ("quantity", 0),
        ("quantity", -2),
    ],
)
def test_add_to_cart_tool_rejects_invalid_positive_values(
    field: str,
    value: Any,
) -> None:
    """
    IDs and quantity must be positive integers.
    """

    kwargs = {
        "db": object(),
        "user_id": USER_ID,
        "product_id": PRODUCT_ID,
        "quantity": QUANTITY,
    }

    kwargs[field] = value

    result = cart_tools.add_to_cart_tool(
        **kwargs,
    )

    assert_failure_result(
        result,
        "add_to_cart",
    )

    assert result.error.code == "validation_error"


@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "product_id",
        "quantity",
    ],
)
def test_add_to_cart_tool_rejects_bool_values(
    field: str,
) -> None:
    """
    bool must never be accepted as an integer ID/quantity.
    """

    kwargs = {
        "db": object(),
        "user_id": USER_ID,
        "product_id": PRODUCT_ID,
        "quantity": QUANTITY,
    }

    kwargs[field] = True

    result = cart_tools.add_to_cart_tool(
        **kwargs,
    )

    assert_failure_result(
        result,
        "add_to_cart",
    )

    assert result.error.code == "validation_error"


def test_add_to_cart_tool_normalizes_numeric_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Serialized planner state may contain numeric strings.

    The tool boundary converts them to integers before
    calling CartService.
    """

    captured: dict[str, Any] = {}

    def fake_add_item(
        *,
        db: Any,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> dict[str, Any]:

        captured.update(
            {
                "user_id": user_id,
                "product_id": product_id,
                "quantity": quantity,
            }
        )

        return CART_RESPONSE

    monkeypatch.setattr(
        cart_tools,
        "add_item",
        fake_add_item,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        lambda db: None,
    )

    result = cart_tools.add_to_cart_tool(
        db=object(),
        user_id="1",
        product_id="10",
        quantity="2",
    )

    assert_success_result(
        result,
        "add_to_cart",
    )

    assert captured == {
        "user_id": 1,
        "product_id": 10,
        "quantity": 2,
    }


def test_add_to_cart_tool_normalizes_product_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A known CartService exception becomes a failed ToolResult.
    """

    def fake_add_item(**kwargs: Any) -> None:
        raise cart_tools.ProductNotFoundError(
            "Product was not found."
        )

    monkeypatch.setattr(
        cart_tools,
        "add_item",
        fake_add_item,
    )

    result = cart_tools.add_to_cart_tool(
        db=object(),
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=QUANTITY,
    )

    assert_failure_result(
        result,
        "add_to_cart",
    )

    assert result.error.code == "cart_operation_failed"
    assert result.error.message == "Product was not found."


def test_add_to_cart_tool_normalizes_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Unexpected implementation errors must not leak through
    the AI tool boundary.
    """

    def fake_add_item(**kwargs: Any) -> None:
        raise RuntimeError(
            "Database exploded."
        )

    monkeypatch.setattr(
        cart_tools,
        "add_item",
        fake_add_item,
    )

    result = cart_tools.add_to_cart_tool(
        db=object(),
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=QUANTITY,
    )

    assert_failure_result(
        result,
        "add_to_cart",
    )

    assert result.error.code == "backend_error"

    assert (
        result.error.message
        == "Unable to add the product to the cart right now."
    )


# =========================================================
# remove_from_cart_tool
# =========================================================


def test_remove_from_cart_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    remove_from_cart_tool uses the product-based CartService
    removal operation.
    """

    calls: dict[str, Any] = {}

    def fake_remove_product(
        *,
        db: Any,
        user_id: int,
        product_id: int,
    ) -> dict[str, Any]:

        calls["remove_product"] = {
            "db": db,
            "user_id": user_id,
            "product_id": product_id,
        }

        return {
            **CART_RESPONSE,
            "items": [],
        }

    def fake_commit_cart(
        db: Any,
    ) -> None:

        calls["commit_cart"] = db

    monkeypatch.setattr(
        cart_tools,
        "remove_product",
        fake_remove_product,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        fake_commit_cart,
    )

    db = object()

    result = cart_tools.remove_from_cart_tool(
        db=db,
        user_id=USER_ID,
        product_id=PRODUCT_ID,
    )

    assert_success_result(
        result,
        "remove_from_cart",
    )

    assert result.data["action"] == "remove_from_cart"
    assert result.data["cart"]["items"] == []

    assert calls["remove_product"] == {
        "db": db,
        "user_id": USER_ID,
        "product_id": PRODUCT_ID,
    }

    assert calls["commit_cart"] is db


def test_remove_from_cart_tool_rejects_invalid_product_id() -> None:
    result = cart_tools.remove_from_cart_tool(
        db=object(),
        user_id=USER_ID,
        product_id=0,
    )

    assert_failure_result(
        result,
        "remove_from_cart",
    )

    assert result.error.code == "validation_error"


def test_remove_from_cart_tool_rejects_invalid_user_id() -> None:
    result = cart_tools.remove_from_cart_tool(
        db=object(),
        user_id=0,
        product_id=PRODUCT_ID,
    )

    assert_failure_result(
        result,
        "remove_from_cart",
    )

    assert result.error.code == "validation_error"


def test_remove_from_cart_tool_normalizes_missing_cart_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def fake_remove_product(**kwargs: Any) -> None:
        raise cart_tools.CartItemNotFoundError(
            "Product is not in the cart."
        )

    monkeypatch.setattr(
        cart_tools,
        "remove_product",
        fake_remove_product,
    )

    result = cart_tools.remove_from_cart_tool(
        db=object(),
        user_id=USER_ID,
        product_id=PRODUCT_ID,
    )

    assert_failure_result(
        result,
        "remove_from_cart",
    )

    assert result.error.code == "cart_operation_failed"


# =========================================================
# update_cart_item_tool
# =========================================================


def test_update_cart_item_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    update_cart_item_tool delegates to the product-based
    CartService quantity update.
    """

    calls: dict[str, Any] = {}

    def fake_update_item_quantity(
        *,
        db: Any,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> dict[str, Any]:

        calls["update_item_quantity"] = {
            "db": db,
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
        }

        return CART_RESPONSE

    def fake_commit_cart(
        db: Any,
    ) -> None:

        calls["commit_cart"] = db

    monkeypatch.setattr(
        cart_tools,
        "update_item_quantity",
        fake_update_item_quantity,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        fake_commit_cart,
    )

    db = object()

    result = cart_tools.update_cart_item_tool(
        db=db,
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=4,
    )

    assert_success_result(
        result,
        "update_cart_item",
    )

    assert result.data["action"] == "update_cart_item"

    assert calls["update_item_quantity"] == {
        "db": db,
        "user_id": USER_ID,
        "product_id": PRODUCT_ID,
        "quantity": 4,
    }

    assert calls["commit_cart"] is db


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        True,
        False,
        None,
        "",
        "abc",
    ],
)
def test_update_cart_item_tool_rejects_invalid_quantity(
    quantity: Any,
) -> None:

    result = cart_tools.update_cart_item_tool(
        db=object(),
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=quantity,
    )

    assert_failure_result(
        result,
        "update_cart_item",
    )

    assert result.error.code == "validation_error"


def test_update_cart_item_tool_normalizes_stock_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def fake_update_item_quantity(**kwargs: Any) -> None:
        raise cart_tools.InsufficientStockError(
            "Requested quantity exceeds stock."
        )

    monkeypatch.setattr(
        cart_tools,
        "update_item_quantity",
        fake_update_item_quantity,
    )

    result = cart_tools.update_cart_item_tool(
        db=object(),
        user_id=USER_ID,
        product_id=PRODUCT_ID,
        quantity=100,
    )

    assert_failure_result(
        result,
        "update_cart_item",
    )

    assert result.error.code == "cart_operation_failed"


# =========================================================
# clear_cart_tool
# =========================================================


def test_clear_cart_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    clear_cart_tool removes all items and commits.
    """

    calls: dict[str, Any] = {}

    def fake_clear_cart(
        *,
        db: Any,
        user_id: int,
    ) -> dict[str, Any]:

        calls["clear_cart"] = {
            "db": db,
            "user_id": user_id,
        }

        return {
            **CART_RESPONSE,
            "items": [],
        }

    def fake_commit_cart(
        db: Any,
    ) -> None:

        calls["commit_cart"] = db

    monkeypatch.setattr(
        cart_tools,
        "clear_cart",
        fake_clear_cart,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        fake_commit_cart,
    )

    db = object()

    result = cart_tools.clear_cart_tool(
        db=db,
        user_id=USER_ID,
    )

    assert_success_result(
        result,
        "clear_cart",
    )

    assert result.data["action"] == "clear_cart"
    assert result.data["cart"]["items"] == []

    assert calls["clear_cart"] == {
        "db": db,
        "user_id": USER_ID,
    }

    assert calls["commit_cart"] is db


def test_clear_cart_tool_rejects_invalid_user_id() -> None:

    result = cart_tools.clear_cart_tool(
        db=object(),
        user_id=0,
    )

    assert_failure_result(
        result,
        "clear_cart",
    )

    assert result.error.code == "validation_error"


# =========================================================
# get_cart_tool
# =========================================================


def test_get_cart_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    get_cart_tool is read-only.

    It must call get_cart but must NOT call commit_cart.
    """

    calls: dict[str, Any] = {
        "get_cart": 0,
        "commit_cart": 0,
    }

    def fake_get_cart(
        *,
        db: Any,
        user_id: int,
    ) -> dict[str, Any]:

        calls["get_cart"] += 1

        return CART_RESPONSE

    def fake_commit_cart(
        db: Any,
    ) -> None:

        calls["commit_cart"] += 1

    monkeypatch.setattr(
        cart_tools,
        "get_cart",
        fake_get_cart,
    )

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        fake_commit_cart,
    )

    result = cart_tools.get_cart_tool(
        db=object(),
        user_id=USER_ID,
    )

    assert_success_result(
        result,
        "get_cart",
    )

    assert result.data["action"] == "get_cart"
    assert result.data["cart_id"] == 100
    assert result.data["items"] == CART_RESPONSE["items"]
    assert result.data["summary"] == CART_RESPONSE["summary"]

    assert calls["get_cart"] == 1

    # Critical read-only guarantee.
    assert calls["commit_cart"] == 0


def test_get_cart_tool_rejects_invalid_user_id() -> None:

    result = cart_tools.get_cart_tool(
        db=object(),
        user_id=-1,
    )

    assert_failure_result(
        result,
        "get_cart",
    )

    assert result.error.code == "validation_error"


def test_get_cart_tool_normalizes_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def fake_get_cart(**kwargs: Any) -> None:
        raise RuntimeError(
            "Database connection failed."
        )

    monkeypatch.setattr(
        cart_tools,
        "get_cart",
        fake_get_cart,
    )

    result = cart_tools.get_cart_tool(
        db=object(),
        user_id=USER_ID,
    )

    assert_failure_result(
        result,
        "get_cart",
    )

    assert result.error.code == "backend_error"

    assert (
        result.error.message
        == "Unable to retrieve your cart right now."
    )


# =========================================================
# Result Shape
# =========================================================


@pytest.mark.parametrize(
    "tool_function,tool_name,args",
    [
        (
            cart_tools.add_to_cart_tool,
            "add_to_cart",
            {
                "user_id": USER_ID,
                "product_id": PRODUCT_ID,
                "quantity": 1,
            },
        ),
        (
            cart_tools.remove_from_cart_tool,
            "remove_from_cart",
            {
                "user_id": USER_ID,
                "product_id": PRODUCT_ID,
            },
        ),
        (
            cart_tools.update_cart_item_tool,
            "update_cart_item",
            {
                "user_id": USER_ID,
                "product_id": PRODUCT_ID,
                "quantity": 2,
            },
        ),
        (
            cart_tools.clear_cart_tool,
            "clear_cart",
            {
                "user_id": USER_ID,
            },
        ),
        (
            cart_tools.get_cart_tool,
            "get_cart",
            {
                "user_id": USER_ID,
            },
        ),
    ],
)
def test_all_cart_tools_are_callable(
    tool_function: Any,
    tool_name: str,
    args: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Smoke test ensuring every public Cart tool returns a
    ToolResult even when its backend is mocked.
    """

    monkeypatch.setattr(
        cart_tools,
        "commit_cart",
        lambda db: None,
    )

    if tool_name == "add_to_cart":
        monkeypatch.setattr(
            cart_tools,
            "add_item",
            lambda **kwargs: CART_RESPONSE,
        )

    elif tool_name == "remove_from_cart":
        monkeypatch.setattr(
            cart_tools,
            "remove_product",
            lambda **kwargs: CART_RESPONSE,
        )

    elif tool_name == "update_cart_item":
        monkeypatch.setattr(
            cart_tools,
            "update_item_quantity",
            lambda **kwargs: CART_RESPONSE,
        )

    elif tool_name == "clear_cart":
        monkeypatch.setattr(
            cart_tools,
            "clear_cart",
            lambda **kwargs: CART_RESPONSE,
        )

    elif tool_name == "get_cart":
        monkeypatch.setattr(
            cart_tools,
            "get_cart",
            lambda **kwargs: CART_RESPONSE,
        )

    result = tool_function(
        db=object(),
        **args,
    )

    assert_success_result(
        result,
        tool_name,
    )