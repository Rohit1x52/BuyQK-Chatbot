"""
Step 3 — Response Node Failure Tests

Tests canonical customer-facing handling of backend/tool failures.

Supported canonical error categories:

    not_found
        → requested resource could not be found

    validation_error
        → supplied information is invalid/incomplete

    backend_error
        → generic service error without exposing internals

    conflict
        → requested operation conflicts with current state

    unauthorized
        → user is not authorized

The Response Node must:

    - never expose backend internals
    - never invent additional business information
    - use the canonical error category when available
    - preserve the canonical ToolResult in GraphState
    - provide a deterministic customer-facing response
"""

from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState
from ai_engine.nodes.response_node import (
    CANONICAL_ERROR_RESPONSES,
    _canonical_error_response,
    _extract_canonical_error_code,
    _tool_fallback,
    response_node,
)


# =========================================================
# Helpers
# =========================================================


def assert_contains(
    text: str,
    expected: str,
) -> None:
    assert isinstance(text, str), (
        f"Expected response to be str, got {type(text).__name__}"
    )

    assert expected.lower() in text.lower(), (
        f"Expected {expected!r} in response {text!r}"
    )


def assert_not_contains(
    text: str,
    unexpected: str,
) -> None:
    assert unexpected.lower() not in text.lower(), (
        f"Did not expect {unexpected!r} in response {text!r}"
    )


def make_failure_result(
    error_code: str,
    *,
    error_message: str = "INTERNAL_BACKEND_ERROR_SHOULD_NOT_BE_EXPOSED",
    tool: str = "test_tool",
    result_type: str = "test_failure",
) -> dict[str, Any]:
    """
    Create a flat presentation payload matching the shape produced
    by Response Node's ToolResult adapter.
    """

    return {
        "success": False,
        "tool": tool,
        "type": result_type,
        "error": error_message,
        "error_code": error_code,
    }


def make_state(
    tool_result: dict[str, Any],
) -> GraphState:
    """
    Build the minimum GraphState required by response_node().
    """

    return {
        "message": "Test request",
        "intent": "test",
        "tool_name": tool_result.get("tool"),
        "tool_result": tool_result,
        "entities": {},
        "missing_fields": [],
        "metadata": {},
    }


# =========================================================
# Canonical error definitions
# =========================================================


def test_all_five_canonical_error_types_are_defined() -> None:
    expected = {
        "not_found",
        "validation_error",
        "backend_error",
        "conflict",
        "unauthorized",
    }

    assert set(CANONICAL_ERROR_RESPONSES) == expected


# =========================================================
# Error-code extraction
# =========================================================


def test_extract_not_found_error_code() -> None:
    result = make_failure_result("not_found")

    assert (
        _extract_canonical_error_code(result)
        == "not_found"
    )


def test_extract_validation_error_code() -> None:
    result = make_failure_result("validation_error")

    assert (
        _extract_canonical_error_code(result)
        == "validation_error"
    )


def test_extract_backend_error_code() -> None:
    result = make_failure_result("backend_error")

    assert (
        _extract_canonical_error_code(result)
        == "backend_error"
    )


def test_extract_conflict_error_code() -> None:
    result = make_failure_result("conflict")

    assert (
        _extract_canonical_error_code(result)
        == "conflict"
    )


def test_extract_unauthorized_error_code() -> None:
    result = make_failure_result("unauthorized")

    assert (
        _extract_canonical_error_code(result)
        == "unauthorized"
    )


def test_unknown_error_code_is_not_treated_as_canonical() -> None:
    result = make_failure_result(
        "some_internal_error"
    )

    assert (
        _extract_canonical_error_code(result)
        is None
    )


def test_missing_error_code_is_not_canonical() -> None:
    result = {
        "success": False,
        "tool": "test_tool",
        "type": "test_failure",
        "error": "Something went wrong.",
    }

    assert (
        _extract_canonical_error_code(result)
        is None
    )


# =========================================================
# Canonical customer-facing responses
# =========================================================


def test_not_found_response() -> None:
    result = make_failure_result("not_found")

    response = _canonical_error_response(result)

    assert response is not None

    assert_contains(
        response,
        "couldn't find",
    )


def test_validation_error_response() -> None:
    result = make_failure_result(
        "validation_error"
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_contains(
        response,
        "invalid",
    )

    assert_contains(
        response,
        "incomplete",
    )


def test_backend_error_response() -> None:
    result = make_failure_result(
        "backend_error"
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_contains(
        response,
        "couldn't complete",
    )


def test_conflict_response() -> None:
    result = make_failure_result(
        "conflict"
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_contains(
        response,
        "conflicts",
    )


def test_unauthorized_response() -> None:
    result = make_failure_result(
        "unauthorized"
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_contains(
        response,
        "not authorized",
    )


# =========================================================
# Raw backend error must not leak
# =========================================================


def test_not_found_does_not_expose_raw_backend_error() -> None:
    internal_error = (
        "SQLAlchemy NoResultFound: "
        "SELECT * FROM products WHERE id=999"
    )

    result = make_failure_result(
        "not_found",
        error_message=internal_error,
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_not_contains(
        response,
        "SQLAlchemy",
    )

    assert_not_contains(
        response,
        "SELECT *",
    )

    assert_not_contains(
        response,
        "999",
    )


def test_backend_error_does_not_expose_exception_details() -> None:
    internal_error = (
        "psycopg2.OperationalError: "
        "connection refused on port 5432"
    )

    result = make_failure_result(
        "backend_error",
        error_message=internal_error,
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_not_contains(
        response,
        "psycopg2",
    )

    assert_not_contains(
        response,
        "OperationalError",
    )

    assert_not_contains(
        response,
        "5432",
    )


def test_validation_error_does_not_expose_internal_details() -> None:
    internal_error = (
        "Pydantic ValidationError: "
        "field checkout.address_id failed constraint"
    )

    result = make_failure_result(
        "validation_error",
        error_message=internal_error,
    )

    response = _canonical_error_response(result)

    assert response is not None

    assert_not_contains(
        response,
        "Pydantic",
    )

    assert_not_contains(
        response,
        "ValidationError",
    )

    assert_not_contains(
        response,
        "constraint",
    )


# =========================================================
# Tool fallback integration
# =========================================================


def test_tool_fallback_uses_not_found_category() -> None:
    result = make_failure_result(
        "not_found",
        tool="search_products",
        result_type="product_search",
    )

    response = _tool_fallback(result)

    assert_contains(
        response,
        "couldn't find",
    )

    assert_not_contains(
        response,
        "INTERNAL_BACKEND_ERROR",
    )


def test_tool_fallback_uses_validation_category() -> None:
    result = make_failure_result(
        "validation_error",
        tool="add_to_cart",
        result_type="cart_add",
    )

    response = _tool_fallback(result)

    assert_contains(
        response,
        "invalid",
    )

    assert_not_contains(
        response,
        "INTERNAL_BACKEND_ERROR",
    )


def test_tool_fallback_uses_backend_category() -> None:
    result = make_failure_result(
        "backend_error",
        tool="get_cart",
        result_type="cart_view",
    )

    response = _tool_fallback(result)

    assert_contains(
        response,
        "couldn't complete",
    )

    assert_not_contains(
        response,
        "INTERNAL_BACKEND_ERROR",
    )


def test_tool_fallback_uses_conflict_category() -> None:
    result = make_failure_result(
        "conflict",
        tool="add_to_cart",
        result_type="cart_add",
    )

    response = _tool_fallback(result)

    assert_contains(
        response,
        "conflicts",
    )


def test_tool_fallback_uses_unauthorized_category() -> None:
    result = make_failure_result(
        "unauthorized",
        tool="checkout_cart",
        result_type="cart_checkout",
    )

    response = _tool_fallback(result)

    assert_contains(
        response,
        "not authorized",
    )


# =========================================================
# Full Response Node integration
# =========================================================


def test_response_node_not_found_failure() -> None:
    tool_result = make_failure_result(
        "not_found",
        tool="search_products",
        result_type="product_search",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "couldn't find",
    )


def test_response_node_validation_error_failure() -> None:
    tool_result = make_failure_result(
        "validation_error",
        tool="add_to_cart",
        result_type="cart_add",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "invalid",
    )


def test_response_node_backend_error_failure() -> None:
    tool_result = make_failure_result(
        "backend_error",
        tool="get_cart",
        result_type="cart_view",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "couldn't complete",
    )


def test_response_node_conflict_failure() -> None:
    tool_result = make_failure_result(
        "conflict",
        tool="remove_from_cart",
        result_type="cart_remove",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "conflicts",
    )


def test_response_node_unauthorized_failure() -> None:
    tool_result = make_failure_result(
        "unauthorized",
        tool="checkout_cart",
        result_type="cart_checkout",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "not authorized",
    )


# =========================================================
# Response Node must not leak canonical backend error
# =========================================================


def test_response_node_does_not_expose_raw_backend_error() -> None:
    internal_error = (
        "RuntimeError: database connection failed "
        "at sqlalchemy.engine.Connection.execute"
    )

    tool_result = make_failure_result(
        "backend_error",
        error_message=internal_error,
        tool="get_cart",
        result_type="cart_view",
    )

    state = make_state(tool_result)

    result = response_node(state)

    response = result.get("response")

    assert isinstance(response, str)

    assert_contains(
        response,
        "couldn't complete",
    )

    assert_not_contains(
        response,
        "RuntimeError",
    )

    assert_not_contains(
        response,
        "sqlalchemy",
    )

    assert_not_contains(
        response,
        "Connection.execute",
    )


# =========================================================
# Canonical category must override raw error text
# =========================================================


def test_canonical_error_takes_precedence_over_raw_error() -> None:
    tool_result = {
        "success": False,
        "tool": "get_cart",
        "type": "cart_view",
        "error_code": "not_found",
        "error": (
            "Internal database exception: "
            "cart table lookup failed"
        ),
    }

    response = _tool_fallback(tool_result)

    assert_contains(
        response,
        "couldn't find",
    )

    assert_not_contains(
        response,
        "Internal database exception",
    )

    assert_not_contains(
        response,
        "cart table lookup failed",
    )


# =========================================================
# Error-code normalization
# =========================================================


def test_error_code_is_normalized_to_lowercase() -> None:
    result = make_failure_result(
        "NOT_FOUND"
    )

    assert (
        _extract_canonical_error_code(result)
        == "not_found"
    )


def test_error_code_whitespace_is_normalized() -> None:
    result = make_failure_result(
        "  conflict  "
    )

    assert (
        _extract_canonical_error_code(result)
        == "conflict"
    )


# =========================================================
# Canonical errors remain deterministic
# =========================================================


def test_canonical_error_response_does_not_depend_on_raw_message() -> None:
    result_one = make_failure_result(
        "backend_error",
        error_message="Database exploded.",
    )

    result_two = make_failure_result(
        "backend_error",
        error_message="Redis timeout.",
    )

    response_one = _canonical_error_response(
        result_one
    )

    response_two = _canonical_error_response(
        result_two
    )

    assert response_one == response_two


def test_all_canonical_categories_have_nonempty_responses() -> None:
    for error_code in CANONICAL_ERROR_RESPONSES:
        result = make_failure_result(
            error_code
        )

        response = _canonical_error_response(
            result
        )

        assert isinstance(response, str)
        assert response.strip()
