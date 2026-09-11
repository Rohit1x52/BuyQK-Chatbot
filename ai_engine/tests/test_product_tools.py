"""
Tests for BuyQK Product Tools.

These tests verify the AI-facing product tool layer:

    search_products_tool
    get_product_tool
    check_product_availability_tool

The tests mock the backend service layer so that they test
tool behavior independently from the database.

The standardized ToolResult / ToolErrorResult contract is
treated as authoritative.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai_engine.tools.product_tools import (
    check_product_availability_tool,
    get_product_tool,
    search_products_tool,
)
from ai_engine.tools.results import ToolResult


# =========================================================
# Test Data
# =========================================================


def make_product(
    *,
    product_id: int = 1,
    merchant_id: int = 10,
    category_id: int = 20,
    name: str = "Amul Gold Milk",
    description: str | None = "Full cream milk.",
    brand: str | None = "Amul",
    price: float = 68.0,
    stock: int = 25,
    image_url: str | None = "https://example.com/milk.jpg",
    is_available: bool = True,
) -> SimpleNamespace:
    """
    Create a lightweight Product-like object.

    A real SQLAlchemy object is unnecessary because these are
    unit tests for the tool layer.
    """

    timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        0,
    )

    return SimpleNamespace(
        id=product_id,
        merchant_id=merchant_id,
        category_id=category_id,
        name=name,
        description=description,
        brand=brand,
        price=price,
        stock=stock,
        image_url=image_url,
        is_available=is_available,
        created_at=timestamp,
        updated_at=timestamp,
    )


# =========================================================
# Result Assertion Helpers
# =========================================================


def assert_validation_error(
    result: ToolResult,
    message: str,
    field: str | None = None,
) -> None:
    """
    Assert the standardized validation error contract.
    """

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.data is None

    assert result.error is not None
    assert result.error.code == "validation_error"
    assert result.error.message == message

    if field is None:
        assert result.error.details is None
    else:
        assert result.error.details == {
            "field": field,
        }


def assert_backend_error(
    result: ToolResult,
    message: str,
) -> None:
    """
    Assert the standardized backend error contract.
    """

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.data is None

    assert result.error is not None
    assert result.error.code == "backend_error"
    assert result.error.message == message
    assert result.error.details is None


def assert_not_found_error(
    result: ToolResult,
    message: str,
    product_id: int,
) -> None:
    """
    Assert the standardized not-found error contract.
    """

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.data is None

    assert result.error is not None
    assert result.error.code == "not_found"
    assert result.error.message == message
    assert result.error.details == {
        "product_id": product_id,
    }


# =========================================================
# search_products_tool
# =========================================================


def test_search_products_tool_returns_products(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product()

    service_mock = Mock(
        return_value=[
            product,
        ]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    db = Mock()

    result = search_products_tool(
        db=db,
        query="Amul milk",
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "search_products"
    assert result.error is None

    assert result.data is not None
    assert result.data["query"] == "Amul milk"
    assert result.data["count"] == 1

    assert result.data["products"] == [
        {
            "id": 1,
            "merchant_id": 10,
            "category_id": 20,
            "name": "Amul Gold Milk",
            "description": "Full cream milk.",
            "brand": "Amul",
            "price": 68.0,
            "stock": 25,
            "image_url": "https://example.com/milk.jpg",
            "is_available": True,
            "created_at": "2026-01-01T12:00:00",
            "updated_at": "2026-01-01T12:00:00",
        }
    ]

    service_mock.assert_called_once_with(
        db=db,
        query="Amul milk",
        limit=10,
    )


def test_search_products_tool_strips_query_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=[]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    db = Mock()

    result = search_products_tool(
        db=db,
        query="   milk   ",
    )

    assert result.success is True
    assert result.tool == "search_products"

    assert result.data is not None
    assert result.data["query"] == "milk"
    assert result.data["products"] == []
    assert result.data["count"] == 0

    service_mock.assert_called_once_with(
        db=db,
        query="milk",
        limit=10,
    )


def test_search_products_tool_rejects_non_string_query() -> None:
    result = search_products_tool(
        db=Mock(),
        query=123,  # type: ignore[arg-type]
    )

    assert_validation_error(
        result,
        "Product search query must be text.",
        "query",
    )


def test_search_products_tool_rejects_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock()

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    result = search_products_tool(
        db=Mock(),
        query="   ",
    )

    assert_validation_error(
        result,
        "Product search query is required.",
        "query",
    )

    service_mock.assert_not_called()


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        -100,
        "invalid",
        None,
        True,
        False,
    ],
)
def test_search_products_tool_rejects_invalid_limit(
    limit,
) -> None:
    result = search_products_tool(
        db=Mock(),
        query="milk",
        limit=limit,
    )

    assert_validation_error(
        result,
        "Product search limit must be a positive integer.",
        "limit",
    )


def test_search_products_tool_accepts_valid_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=[]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    db = Mock()

    result = search_products_tool(
        db=db,
        query="milk",
        limit=25,
    )

    assert result.success is True
    assert result.tool == "search_products"

    service_mock.assert_called_once_with(
        db=db,
        query="milk",
        limit=25,
    )


def test_search_products_tool_caps_large_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=[]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    db = Mock()

    result = search_products_tool(
        db=db,
        query="milk",
        limit=10000,
    )

    assert result.success is True

    service_mock.assert_called_once_with(
        db=db,
        query="milk",
        limit=100,
    )


def test_search_products_tool_handles_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        side_effect=RuntimeError(
            "Database connection failed."
        )
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    result = search_products_tool(
        db=Mock(),
        query="milk",
    )

    assert_backend_error(
        result,
        "Unable to search products right now.",
    )


def test_search_products_tool_handles_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=[]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    result = search_products_tool(
        db=Mock(),
        query="something-that-does-not-exist",
    )

    assert result.success is True
    assert result.tool == "search_products"
    assert result.error is None

    assert result.data == {
        "products": [],
        "count": 0,
        "query": "something-that-does-not-exist",
    }


# =========================================================
# get_product_tool
# =========================================================


def test_get_product_tool_returns_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        product_id=42,
    )

    service_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        service_mock,
    )

    db = Mock()

    result = get_product_tool(
        db=db,
        product_id=42,
    )

    assert result.success is True
    assert result.tool == "get_product"
    assert result.error is None

    assert result.data is not None
    assert result.data["product"]["id"] == 42
    assert (
        result.data["product"]["name"]
        == "Amul Gold Milk"
    )

    service_mock.assert_called_once_with(
        db=db,
        product_id=42,
    )


def test_get_product_tool_rejects_invalid_product_id() -> None:
    result = get_product_tool(
        db=Mock(),
        product_id=0,
    )

    assert_validation_error(
        result,
        "Product ID must be a positive integer.",
        "product_id",
    )


@pytest.mark.parametrize(
    "product_id",
    [
        -1,
        -100,
        "invalid",
        None,
        True,
        False,
    ],
)
def test_get_product_tool_rejects_invalid_ids(
    product_id,
) -> None:
    result = get_product_tool(
        db=Mock(),
        product_id=product_id,
    )

    assert_validation_error(
        result,
        "Product ID must be a positive integer.",
        "product_id",
    )


def test_get_product_tool_accepts_numeric_string_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        product_id=42,
    )

    service_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        service_mock,
    )

    db = Mock()

    result = get_product_tool(
        db=db,
        product_id="42",  # type: ignore[arg-type]
    )

    assert result.success is True

    service_mock.assert_called_once_with(
        db=db,
        product_id=42,
    )


def test_get_product_tool_handles_missing_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=None
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        service_mock,
    )

    result = get_product_tool(
        db=Mock(),
        product_id=999,
    )

    assert_not_found_error(
        result,
        "Product 999 does not exist.",
        999,
    )


def test_get_product_tool_handles_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        side_effect=RuntimeError(
            "Database failure."
        )
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        service_mock,
    )

    result = get_product_tool(
        db=Mock(),
        product_id=42,
    )

    assert_backend_error(
        result,
        "Unable to retrieve the product right now.",
    )


# =========================================================
# check_product_availability_tool
# =========================================================


def test_check_product_availability_tool_returns_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        product_id=7,
        stock=20,
    )

    availability_mock = Mock(
        return_value=True
    )

    product_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        product_mock,
    )

    db = Mock()

    result = check_product_availability_tool(
        db=db,
        product_id=7,
        quantity=3,
    )

    assert result.success is True
    assert (
        result.tool
        == "check_product_availability"
    )
    assert result.error is None

    assert result.data is not None

    assert result.data["product_id"] == 7
    assert result.data["quantity"] == 3
    assert result.data["available"] is True
    assert result.data["product"]["id"] == 7

    availability_mock.assert_called_once_with(
        db=db,
        product_id=7,
        quantity=3,
    )

    product_mock.assert_called_once_with(
        db=db,
        product_id=7,
    )


def test_check_product_availability_tool_returns_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        product_id=7,
        stock=2,
    )

    availability_mock = Mock(
        return_value=False
    )

    product_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        product_mock,
    )

    result = check_product_availability_tool(
        db=Mock(),
        product_id=7,
        quantity=5,
    )

    assert result.success is True
    assert result.tool == (
        "check_product_availability"
    )
    assert result.error is None

    assert result.data is not None
    assert result.data["available"] is False
    assert result.data["quantity"] == 5
    assert result.data["product"]["stock"] == 2


@pytest.mark.parametrize(
    "product_id",
    [
        0,
        -1,
        -50,
        "invalid",
        None,
        True,
        False,
    ],
)
def test_check_product_availability_tool_rejects_invalid_product_id(
    product_id,
) -> None:
    result = check_product_availability_tool(
        db=Mock(),
        product_id=product_id,
        quantity=1,
    )

    assert_validation_error(
        result,
        "Product ID must be a positive integer.",
        "product_id",
    )


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
        -50,
        "invalid",
        None,
        True,
        False,
    ],
)
def test_check_product_availability_tool_rejects_invalid_quantity(
    quantity,
) -> None:
    result = check_product_availability_tool(
        db=Mock(),
        product_id=1,
        quantity=quantity,
    )

    assert_validation_error(
        result,
        "Quantity must be a positive integer.",
        "quantity",
    )


def test_check_product_availability_tool_accepts_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        product_id=7,
        stock=10,
    )

    availability_mock = Mock(
        return_value=True
    )

    product_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        product_mock,
    )

    db = Mock()

    result = check_product_availability_tool(
        db=db,
        product_id="7",  # type: ignore[arg-type]
        quantity="3",  # type: ignore[arg-type]
    )

    assert result.success is True

    availability_mock.assert_called_once_with(
        db=db,
        product_id=7,
        quantity=3,
    )


def test_check_product_availability_tool_handles_service_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_mock = Mock(
        side_effect=RuntimeError(
            "Database unavailable."
        )
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    result = check_product_availability_tool(
        db=Mock(),
        product_id=7,
        quantity=2,
    )

    assert_backend_error(
        result,
        "Unable to check product availability right now.",
    )


def test_check_product_availability_tool_handles_missing_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_mock = Mock(
        return_value=False
    )

    product_mock = Mock(
        return_value=None
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        product_mock,
    )

    result = check_product_availability_tool(
        db=Mock(),
        product_id=999,
        quantity=1,
    )

    assert_not_found_error(
        result,
        "Product 999 does not exist.",
        999,
    )


def test_check_product_availability_tool_handles_product_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_mock = Mock(
        return_value=True
    )

    product_mock = Mock(
        side_effect=RuntimeError(
            "Database lookup failed."
        )
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.check_product_availability",
        availability_mock,
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        product_mock,
    )

    result = check_product_availability_tool(
        db=Mock(),
        product_id=7,
        quantity=1,
    )

    assert_backend_error(
        result,
        "Unable to retrieve product information right now.",
    )


# =========================================================
# Product Serialization
# =========================================================


def test_product_serialization_preserves_nullable_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = make_product(
        description=None,
        brand=None,
        image_url=None,
    )

    service_mock = Mock(
        return_value=product
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.get_product",
        service_mock,
    )

    result = get_product_tool(
        db=Mock(),
        product_id=1,
    )

    assert result.success is True
    assert result.data is not None

    serialized = result.data["product"]

    assert serialized["description"] is None
    assert serialized["brand"] is None
    assert serialized["image_url"] is None


# =========================================================
# Database Session Handling
# =========================================================


def test_search_products_tool_uses_supplied_db_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_mock = Mock(
        return_value=[]
    )

    monkeypatch.setattr(
        "ai_engine.tools.product_tools.search_products",
        service_mock,
    )

    db = object()

    result = search_products_tool(
        db=db,  # type: ignore[arg-type]
        query="milk",
    )

    assert result.success is True

    assert service_mock.call_args.kwargs[
        "db"
    ] is db


# =========================================================
# Public Tool API
# =========================================================


def test_product_tool_functions_are_callable() -> None:
    assert callable(
        search_products_tool
    )

    assert callable(
        get_product_tool
    )

    assert callable(
        check_product_availability_tool
    )
