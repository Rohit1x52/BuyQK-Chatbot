"""
Step 2 — Response Node Success Tests

Tests successful presentation of:

    search_products
        → product results

    add_to_cart
        → confirmation

    remove_from_cart
        → confirmation

    get_cart
        → cart summary
"""

from __future__ import annotations

from typing import Any

from ai_engine.nodes.response_node import (
    _success_response_from_tool,
)


# =========================================================
# Helper
# =========================================================

def assert_contains(
    text: str,
    expected: str,
) -> None:
    assert (
        expected.lower() in text.lower()
    ), (
        f"Expected {expected!r} in response {text!r}"
    )


# =========================================================
# SEARCH PRODUCTS
# =========================================================

def test_search_products_success() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "search_products",
        "type": "product_search",
        "products": [
            {
                "id": 1,
                "name": "Amul Milk",
                "price": 60,
            },
            {
                "id": 2,
                "name": "Amul Taaza Milk",
                "price": 64,
            },
        ],
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "Amul Milk",
    )

    assert_contains(
        response,
        "Amul Taaza Milk",
    )


def test_search_products_empty_result() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "search_products",
        "type": "product_search",
        "products": [],
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "couldn't find",
    )


def test_search_products_does_not_invent_products() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "search_products",
        "type": "product_search",
        "products": [
            {
                "id": 1,
                "name": "Amul Milk",
            },
        ],
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "Amul Milk",
    )

    assert "Tata Tea" not in response


# =========================================================
# ADD TO CART
# =========================================================

def test_add_to_cart_success() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "add_to_cart",
        "type": "cart_add",
        "product_name": "Amul Milk",
        "quantity": 2,
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "Amul Milk",
    )

    assert_contains(
        response,
        "2",
    )

    assert_contains(
        response,
        "added to your cart",
    )


def test_add_to_cart_success_without_product_name() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "add_to_cart",
        "type": "cart_add",
        "quantity": 2,
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "added to your cart",
    )


# =========================================================
# REMOVE FROM CART
# =========================================================

def test_remove_from_cart_success() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "remove_from_cart",
        "type": "cart_remove",
        "product_name": "Amul Milk",
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "Amul Milk",
    )

    assert_contains(
        response,
        "removed from your cart",
    )


def test_remove_from_cart_success_without_product_name() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "remove_from_cart",
        "type": "cart_remove",
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "removed from your cart",
    )


# =========================================================
# GET CART
# =========================================================

def test_get_cart_with_items() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "get_cart",
        "type": "cart_view",
        "cart": {
            "cart_id": 100,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Amul Milk",
                    "quantity": 2,
                },
            ],
        },
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "current cart",
    )


def test_get_cart_empty() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "get_cart",
        "type": "cart_view",
        "cart": {
            "cart_id": 100,
            "items": [],
        },
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "cart is empty",
    )


# =========================================================
# FAILURE MUST NOT BE PRESENTED AS SUCCESS
# =========================================================

def test_failed_add_to_cart_is_not_success_response() -> None:

    tool_result: dict[str, Any] = {
        "success": False,
        "tool": "add_to_cart",
        "type": "cart_add",
        "error": "Insufficient stock.",
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "couldn't complete",
    )


def test_failed_search_is_not_success_response() -> None:

    tool_result: dict[str, Any] = {
        "success": False,
        "tool": "search_products",
        "type": "product_search",
        "error": "Product search failed.",
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "couldn't complete",
    )


# =========================================================
# UNKNOWN SUCCESSFUL TOOL
# =========================================================

def test_unknown_successful_tool_has_generic_response() -> None:

    tool_result: dict[str, Any] = {
        "success": True,
        "tool": "some_future_tool",
        "type": "future_result",
    }

    response = _success_response_from_tool(
        tool_result
    )

    assert_contains(
        response,
        "request was completed",
    )
