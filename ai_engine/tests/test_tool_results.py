"""
Tests for BuyQK tool result normalization.

These tests verify:

- successful ToolResult creation
- failed ToolResult creation
- error normalization
- unexpected exception normalization
- success/failure invariants
- dictionary serialization
- convenience helpers
"""


from __future__ import annotations

from typing import Any

import pytest

from ai_engine.tools.errors import (
    ToolBackendError,
    ToolNotFoundError,
    ToolValidationError,
)

from ai_engine.tools.results import (
    ToolErrorResult,
    ToolResult,
    failure_result,
    normalize_exception,
    success_result,
)


# =========================================================
# ToolErrorResult
# =========================================================


def test_tool_error_result_accepts_valid_error() -> None:
    error = ToolErrorResult(
        code="not_found",
        message="Product was not found.",
    )

    assert error.code == "not_found"
    assert error.message == "Product was not found."
    assert error.details is None


def test_tool_error_result_preserves_details() -> None:
    details = {
        "resource": "product",
        "product_id": 42,
    }

    error = ToolErrorResult(
        code="not_found",
        message="Product was not found.",
        details=details,
    )

    assert error.details == details


def test_tool_error_result_to_dict() -> None:
    error = ToolErrorResult(
        code="not_found",
        message="Product was not found.",
        details={
            "product_id": 42,
        },
    )

    assert error.to_dict() == {
        "code": "not_found",
        "message": "Product was not found.",
        "details": {
            "product_id": 42,
        },
    }


def test_tool_error_result_rejects_empty_code() -> None:
    with pytest.raises(
        ValueError,
        match="Tool error code cannot be empty",
    ):
        ToolErrorResult(
            code="",
            message="Something failed.",
        )


def test_tool_error_result_rejects_empty_message() -> None:
    with pytest.raises(
        ValueError,
        match="Tool error message cannot be empty",
    ):
        ToolErrorResult(
            code="tool_error",
            message="",
        )


def test_tool_error_result_rejects_invalid_details() -> None:
    with pytest.raises(
        TypeError,
        match="Tool error details must be a mapping",
    ):
        ToolErrorResult(
            code="tool_error",
            message="Something failed.",
            details=[],  # type: ignore[arg-type]
        )


# =========================================================
# Successful ToolResult
# =========================================================


def test_tool_result_success() -> None:
    result = ToolResult.ok(
        tool="search_products",
        data={
            "products": [],
        },
    )

    assert result.success is True
    assert result.tool == "search_products"
    assert result.data == {
        "products": [],
    }
    assert result.error is None


def test_tool_result_success_without_data() -> None:
    result = ToolResult.ok(
        tool="clear_cart",
    )

    assert result.success is True
    assert result.tool == "clear_cart"
    assert result.data is None
    assert result.error is None


def test_tool_result_success_status_helpers() -> None:
    result = ToolResult.ok(
        tool="search_products",
        data=[],
    )

    assert result.is_success() is True
    assert result.is_failure() is False


def test_tool_result_success_to_dict() -> None:
    result = ToolResult.ok(
        tool="search_products",
        data={
            "products": [
                {
                    "id": 1,
                    "name": "Amul Milk",
                },
            ],
        },
    )

    assert result.to_dict() == {
        "success": True,
        "tool": "search_products",
        "data": {
            "products": [
                {
                    "id": 1,
                    "name": "Amul Milk",
                },
            ],
        },
        "error": None,
    }


# =========================================================
# Failed ToolResult
# =========================================================


def test_tool_result_failure() -> None:
    error = ToolErrorResult(
        code="not_found",
        message="Product was not found.",
    )

    result = ToolResult.fail(
        tool="get_product",
        error=error,
    )

    assert result.success is False
    assert result.tool == "get_product"
    assert result.data is None
    assert result.error is error


def test_tool_result_failure_status_helpers() -> None:
    result = ToolResult.fail(
        tool="get_product",
        error=ToolErrorResult(
            code="not_found",
            message="Product was not found.",
        ),
    )

    assert result.is_success() is False
    assert result.is_failure() is True


def test_tool_result_failure_to_dict() -> None:
    result = ToolResult.fail(
        tool="get_product",
        error=ToolErrorResult(
            code="not_found",
            message="Product was not found.",
            details={
                "product_id": 999,
            },
        ),
    )

    assert result.to_dict() == {
        "success": False,
        "tool": "get_product",
        "data": None,
        "error": {
            "code": "not_found",
            "message": "Product was not found.",
            "details": {
                "product_id": 999,
            },
        },
    }


# =========================================================
# Result Invariants
# =========================================================


def test_success_result_cannot_contain_error() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "A successful ToolResult cannot contain an error"
        ),
    ):
        ToolResult(
            success=True,
            tool="search_products",
            data=[],
            error=ToolErrorResult(
                code="tool_error",
                message="Something failed.",
            ),
        )


def test_failure_result_requires_error() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "A failed ToolResult must contain an error"
        ),
    ):
        ToolResult(
            success=False,
            tool="search_products",
            data=None,
            error=None,
        )


def test_failure_result_cannot_contain_data() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "A failed ToolResult cannot contain data"
        ),
    ):
        ToolResult(
            success=False,
            tool="search_products",
            data=[],
            error=ToolErrorResult(
                code="tool_error",
                message="Something failed.",
            ),
        )


def test_tool_result_rejects_empty_tool_name() -> None:
    with pytest.raises(
        ValueError,
        match="ToolResult.tool cannot be empty",
    ):
        ToolResult.ok(
            tool="",
            data=None,
        )


def test_tool_result_rejects_non_string_tool_name() -> None:
    with pytest.raises(
        TypeError,
        match="ToolResult.tool must be a string",
    ):
        ToolResult.ok(
            tool=123,  # type: ignore[arg-type]
            data=None,
        )


# =========================================================
# ToolError Normalization
# =========================================================


def test_from_error_normalizes_tool_error() -> None:
    error = ToolNotFoundError(
        "Product was not found.",
        details={
            "product_id": 42,
        },
    )

    result = ToolResult.from_error(
        tool="get_product",
        error=error,
    )

    assert result.success is False
    assert result.tool == "get_product"
    assert result.data is None

    assert result.error is not None
    assert result.error.code == "not_found"
    assert (
        result.error.message
        == "Product was not found."
    )
    assert result.error.details == {
        "product_id": 42,
    }


def test_from_validation_error() -> None:
    error = ToolValidationError(
        "Quantity must be greater than zero."
    )

    result = ToolResult.from_error(
        tool="add_to_cart",
        error=error,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "validation_error"
    assert (
        result.error.message
        == "Quantity must be greater than zero."
    )


def test_from_backend_error() -> None:
    error = ToolBackendError(
        "Backend service failed."
    )

    result = ToolResult.from_error(
        tool="search_products",
        error=error,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "backend_error"


# =========================================================
# Arbitrary Exception Normalization
# =========================================================


def test_from_exception_preserves_tool_error_structure() -> None:
    error = ToolNotFoundError(
        "Order was not found."
    )

    result = ToolResult.from_exception(
        tool="get_order",
        error=error,
    )

    assert result.success is False
    assert result.tool == "get_order"
    assert result.error is not None
    assert result.error.code == "not_found"
    assert (
        result.error.message
        == "Order was not found."
    )


def test_from_exception_hides_unexpected_exception() -> None:
    error = RuntimeError(
        "Sensitive internal database information."
    )

    result = ToolResult.from_exception(
        tool="get_order",
        error=error,
    )

    assert result.success is False
    assert result.tool == "get_order"
    assert result.data is None

    assert result.error is not None
    assert (
        result.error.code
        == "tool_execution_error"
    )

    assert (
        result.error.message
        == "Tool execution failed."
    )

    # Raw internal exception details must not leak
    # into the customer-facing normalized result.
    assert (
        result.error.details is None
    )

    assert (
        "Sensitive internal database information."
        not in result.error.message
    )


# =========================================================
# Convenience Functions
# =========================================================


def test_success_result_helper() -> None:
    result = success_result(
        tool="search_products",
        data={
            "products": [],
        },
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "search_products"
    assert result.data == {
        "products": [],
    }


def test_failure_result_helper() -> None:
    error = ToolNotFoundError(
        "Product was not found."
    )

    result = failure_result(
        tool="get_product",
        error=error,
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.tool == "get_product"
    assert result.error is not None
    assert result.error.code == "not_found"


def test_normalize_exception_helper() -> None:
    error = ToolValidationError(
        "Invalid quantity."
    )

    result = normalize_exception(
        tool="add_to_cart",
        error=error,
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.tool == "add_to_cart"

    assert result.error is not None
    assert (
        result.error.code
        == "validation_error"
    )


# =========================================================
# Generic Data Support
# =========================================================


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"value": 123},
        [1, 2, 3],
        "backend-value",
        42,
        True,
    ],
)
def test_tool_result_supports_generic_data(
    data: Any,
) -> None:
    """
    ToolResult should not impose business-specific
    restrictions on backend data.
    """

    result = ToolResult.ok(
        tool="example_tool",
        data=data,
    )

    assert result.success is True
    assert result.data == data