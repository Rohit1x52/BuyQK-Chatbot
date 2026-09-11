"""
Tests for the BuyQK ResponseResult contract.
"""

from __future__ import annotations

import pytest

from ai_engine.response.contracts import (
    ResponseResult,
    failure_response,
    success_response,
)
from ai_engine.tools.results import (
    ToolErrorResult,
    ToolResult,
)


# =========================================================
# Fixtures
# =========================================================

def _success_tool_result() -> ToolResult:
    return ToolResult.ok(
        tool="search_products",
        data={
            "products": [
                {
                    "id": 1,
                    "name": "Tata Tea",
                    "price": 120,
                }
            ],
            "count": 1,
        },
    )


def _failure_tool_result() -> ToolResult:
    return ToolResult.fail(
        tool="search_products",
        error=ToolErrorResult(
            code="product_not_found",
            message="Product was not found.",
        ),
    )


# =========================================================
# Successful Response
# =========================================================

def test_response_result_success() -> None:
    result = ResponseResult.ok(
        message="Tata Tea is available.",
    )

    assert isinstance(
        result,
        ResponseResult,
    )

    assert result.success is True
    assert result.message == "Tata Tea is available."
    assert result.error is None
    assert result.tool_result is None


def test_response_result_success_with_tool_result() -> None:
    tool_result = _success_tool_result()

    result = ResponseResult.ok(
        message="Tata Tea is available.",
        tool_result=tool_result,
    )

    assert result.success is True
    assert result.message == "Tata Tea is available."
    assert result.tool_result is tool_result
    assert result.error is None


def test_response_result_success_with_metadata() -> None:
    result = ResponseResult.ok(
        message="Here are the available products.",
        metadata={
            "type": "product_search",
        },
    )

    assert result.success is True
    assert result.metadata == {
        "type": "product_search",
    }


# =========================================================
# Failed Response
# =========================================================

def test_response_result_failure() -> None:
    result = ResponseResult.fail(
        error="Response generation failed.",
    )

    assert isinstance(
        result,
        ResponseResult,
    )

    assert result.success is False
    assert result.message is None
    assert result.error == "Response generation failed."


def test_response_result_failure_with_fallback_message() -> None:
    result = ResponseResult.fail(
        error="LLM unavailable.",
        message="Sorry, I could not generate a response right now.",
    )

    assert result.success is False
    assert result.error == "LLM unavailable."
    assert (
        result.message
        == "Sorry, I could not generate a response right now."
    )


def test_response_result_can_preserve_failed_tool_result() -> None:
    tool_result = _failure_tool_result()

    result = ResponseResult.fail(
        error="Unable to generate natural-language response.",
        tool_result=tool_result,
    )

    assert result.success is False
    assert result.tool_result is tool_result
    assert result.tool_result.success is False


# =========================================================
# Status Helpers
# =========================================================

def test_response_result_is_success() -> None:
    result = ResponseResult.ok(
        message="Done.",
    )

    assert result.is_success() is True
    assert result.is_failure() is False


def test_response_result_is_failure() -> None:
    result = ResponseResult.fail(
        error="Failed.",
    )

    assert result.is_success() is False
    assert result.is_failure() is True


# =========================================================
# Validation
# =========================================================

def test_response_result_rejects_non_boolean_success() -> None:
    with pytest.raises(TypeError):
        ResponseResult(
            success="true",  # type: ignore[arg-type]
            message="Done.",
        )


def test_response_result_rejects_non_string_message() -> None:
    with pytest.raises(TypeError):
        ResponseResult(
            success=True,
            message=123,  # type: ignore[arg-type]
        )


def test_response_result_rejects_empty_message() -> None:
    with pytest.raises(ValueError):
        ResponseResult(
            success=True,
            message="   ",
        )


def test_response_result_success_requires_message() -> None:
    with pytest.raises(ValueError):
        ResponseResult(
            success=True,
            message=None,
        )


def test_response_result_success_cannot_have_error() -> None:
    with pytest.raises(ValueError):
        ResponseResult(
            success=True,
            message="Done.",
            error="Something failed.",
        )


def test_response_result_failure_requires_error() -> None:
    with pytest.raises(ValueError):
        ResponseResult(
            success=False,
            message="Fallback.",
            error=None,
        )


def test_response_result_rejects_empty_error() -> None:
    with pytest.raises(ValueError):
        ResponseResult(
            success=False,
            error="   ",
        )


def test_response_result_rejects_invalid_metadata() -> None:
    with pytest.raises(TypeError):
        ResponseResult(
            success=True,
            message="Done.",
            metadata=[],  # type: ignore[arg-type]
        )


def test_response_result_rejects_invalid_tool_result() -> None:
    with pytest.raises(TypeError):
        ResponseResult(
            success=True,
            message="Done.",
            tool_result={},  # type: ignore[arg-type]
        )


# =========================================================
# Serialization
# =========================================================

def test_response_result_to_dict_without_tool_result() -> None:
    result = ResponseResult.ok(
        message="Hello.",
    )

    payload = result.to_dict()

    assert payload == {
        "success": True,
        "message": "Hello.",
        "metadata": None,
        "tool_result": None,
        "error": None,
    }


def test_response_result_to_dict_with_tool_result() -> None:
    tool_result = _success_tool_result()

    result = ResponseResult.ok(
        message="Tata Tea is available.",
        metadata={
            "type": "product_search",
        },
        tool_result=tool_result,
    )

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Tata Tea is available."

    assert payload["metadata"] == {
        "type": "product_search",
    }

    assert payload["tool_result"] == {
        "success": True,
        "tool": "search_products",
        "data": {
            "products": [
                {
                    "id": 1,
                    "name": "Tata Tea",
                    "price": 120,
                }
            ],
            "count": 1,
        },
        "error": None,
    }

    assert payload["error"] is None


def test_response_result_to_dict_with_failure() -> None:
    result = ResponseResult.fail(
        error="LLM unavailable.",
        message="Sorry, I could not generate a response.",
        metadata={
            "type": "error",
        },
    )

    payload = result.to_dict()

    assert payload == {
        "success": False,
        "message": "Sorry, I could not generate a response.",
        "metadata": {
            "type": "error",
        },
        "tool_result": None,
        "error": "LLM unavailable.",
    }


# =========================================================
# Convenience Functions
# =========================================================

def test_success_response_helper() -> None:
    tool_result = _success_tool_result()

    result = success_response(
        message="Tata Tea found.",
        metadata={
            "type": "product_search",
        },
        tool_result=tool_result,
    )

    assert isinstance(
        result,
        ResponseResult,
    )

    assert result.success is True
    assert result.message == "Tata Tea found."
    assert result.metadata == {
        "type": "product_search",
    }
    assert result.tool_result is tool_result


def test_failure_response_helper() -> None:
    tool_result = _failure_tool_result()

    result = failure_response(
        error="Response generation failed.",
        message="Sorry, something went wrong.",
        tool_result=tool_result,
    )

    assert isinstance(
        result,
        ResponseResult,
    )

    assert result.success is False
    assert result.error == "Response generation failed."
    assert result.message == "Sorry, something went wrong."
    assert result.tool_result is tool_result


# =========================================================
# Immutability
# =========================================================

def test_response_result_is_immutable() -> None:
    result = ResponseResult.ok(
        message="Done.",
    )

    with pytest.raises(
        AttributeError,
    ):
        result.message = "Changed."  # type: ignore[misc]
