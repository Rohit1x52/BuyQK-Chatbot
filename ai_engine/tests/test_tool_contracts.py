"""
Tests for BuyQK tool contracts.

These tests verify that ToolContract:

- accepts valid tool definitions
- preserves supplied metadata
- requires a valid tool name
- requires a valid description
- requires a valid category
- requires a callable handler
- validates read_only
- validates input_schema
- remains immutable after creation
"""


from __future__ import annotations

from typing import Any

import pytest

from ai_engine.tools.contracts import (
    ToolContract,
)


# =========================================================
# Test Helpers
# =========================================================

def sample_handler(
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Minimal callable used by contract tests.
    """

    return kwargs


# =========================================================
# Valid Contract
# =========================================================

def test_tool_contract_accepts_valid_definition() -> None:
    """
    A valid ToolContract should be created successfully.
    """

    contract = ToolContract(
        name="search_products",
        description="Search available products.",
        category="product",
        handler=sample_handler,
    )

    assert contract.name == "search_products"
    assert (
        contract.description
        == "Search available products."
    )
    assert contract.category == "product"
    assert contract.handler is sample_handler
    assert contract.read_only is True
    assert contract.input_schema is None


def test_tool_contract_preserves_input_schema() -> None:
    """
    input_schema should be preserved without being modified.
    """

    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
            },
        },
        "required": [
            "query",
        ],
    }

    contract = ToolContract(
        name="search_products",
        description="Search available products.",
        category="product",
        handler=sample_handler,
        input_schema=schema,
    )

    assert contract.input_schema == schema


def test_tool_contract_supports_mutating_tools() -> None:
    """
    read_only=False should be accepted for state-changing
    backend operations.
    """

    contract = ToolContract(
        name="add_to_cart",
        description="Add a product to the cart.",
        category="cart",
        handler=sample_handler,
        read_only=False,
    )

    assert contract.read_only is False


# =========================================================
# Name Validation
# =========================================================

def test_tool_contract_rejects_empty_name() -> None:
    """
    Tool names cannot be empty.
    """

    with pytest.raises(
        ValueError,
        match="Tool name cannot be empty",
    ):
        ToolContract(
            name="",
            description="Search products.",
            category="product",
            handler=sample_handler,
        )


def test_tool_contract_rejects_whitespace_name() -> None:
    """
    Tool names containing only whitespace are invalid.
    """

    with pytest.raises(
        ValueError,
        match="Tool name cannot be empty",
    ):
        ToolContract(
            name="   ",
            description="Search products.",
            category="product",
            handler=sample_handler,
        )


def test_tool_contract_rejects_non_string_name() -> None:
    """
    Tool names must be strings.
    """

    with pytest.raises(
        TypeError,
        match="Tool name must be a string",
    ):
        ToolContract(
            name=123,  # type: ignore[arg-type]
            description="Search products.",
            category="product",
            handler=sample_handler,
        )


def test_tool_contract_rejects_name_with_outer_whitespace() -> None:
    """
    The contract requires canonical tool names.

    Whitespace normalization belongs to the caller/registry,
    not the contract itself.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Tool name cannot contain leading or trailing "
            "whitespace"
        ),
    ):
        ToolContract(
            name=" search_products ",
            description="Search products.",
            category="product",
            handler=sample_handler,
        )


# =========================================================
# Description Validation
# =========================================================

def test_tool_contract_rejects_non_string_description() -> None:
    """
    Description must be a string.
    """

    with pytest.raises(
        TypeError,
        match="Tool description must be a string",
    ):
        ToolContract(
            name="search_products",
            description=123,  # type: ignore[arg-type]
            category="product",
            handler=sample_handler,
        )


def test_tool_contract_rejects_empty_description() -> None:
    """
    Description cannot be empty.
    """

    with pytest.raises(
        ValueError,
        match="Tool description cannot be empty",
    ):
        ToolContract(
            name="search_products",
            description="",
            category="product",
            handler=sample_handler,
        )


def test_tool_contract_rejects_whitespace_description() -> None:
    """
    Description containing only whitespace is invalid.
    """

    with pytest.raises(
        ValueError,
        match="Tool description cannot be empty",
    ):
        ToolContract(
            name="search_products",
            description="   ",
            category="product",
            handler=sample_handler,
        )


# =========================================================
# Category Validation
# =========================================================

def test_tool_contract_rejects_non_string_category() -> None:
    """
    Category must be a string.
    """

    with pytest.raises(
        TypeError,
        match="Tool category must be a string",
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category=123,  # type: ignore[arg-type]
            handler=sample_handler,
        )


def test_tool_contract_rejects_empty_category() -> None:
    """
    Category cannot be empty.
    """

    with pytest.raises(
        ValueError,
        match="Tool category cannot be empty",
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category="",
            handler=sample_handler,
        )


def test_tool_contract_rejects_whitespace_category() -> None:
    """
    Category containing only whitespace is invalid.
    """

    with pytest.raises(
        ValueError,
        match="Tool category cannot be empty",
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category="   ",
            handler=sample_handler,
        )


# =========================================================
# Handler Validation
# =========================================================

def test_tool_contract_rejects_non_callable_handler() -> None:
    """
    Every tool must provide an executable handler.
    """

    with pytest.raises(
        TypeError,
        match="Tool handler must be callable",
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category="product",
            handler="not_callable",  # type: ignore[arg-type]
        )


def test_tool_contract_accepts_callable_object() -> None:
    """
    Callable objects are valid handlers.
    """

    class Handler:
        def __call__(
            self,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return kwargs

    handler = Handler()

    contract = ToolContract(
        name="search_products",
        description="Search products.",
        category="product",
        handler=handler,
    )

    assert contract.handler is handler
    assert callable(contract.handler)


# =========================================================
# read_only Validation
# =========================================================

def test_tool_contract_rejects_non_boolean_read_only() -> None:
    """
    read_only must explicitly be a boolean.
    """

    with pytest.raises(
        TypeError,
        match="read_only must be a boolean",
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category="product",
            handler=sample_handler,
            read_only="true",  # type: ignore[arg-type]
        )


# =========================================================
# Input Schema Validation
# =========================================================

def test_tool_contract_accepts_mapping_input_schema() -> None:
    """
    A mapping can be supplied as input_schema.
    """

    schema = {
        "type": "object",
        "properties": {},
    }

    contract = ToolContract(
        name="search_products",
        description="Search products.",
        category="product",
        handler=sample_handler,
        input_schema=schema,
    )

    assert contract.input_schema == schema


def test_tool_contract_accepts_none_input_schema() -> None:
    """
    input_schema is optional.
    """

    contract = ToolContract(
        name="search_products",
        description="Search products.",
        category="product",
        handler=sample_handler,
        input_schema=None,
    )

    assert contract.input_schema is None


def test_tool_contract_rejects_invalid_input_schema() -> None:
    """
    input_schema must be mapping-like when supplied.
    """

    with pytest.raises(
        TypeError,
        match=(
            "input_schema must be a mapping or None"
        ),
    ):
        ToolContract(
            name="search_products",
            description="Search products.",
            category="product",
            handler=sample_handler,
            input_schema=[],  # type: ignore[arg-type]
        )


# =========================================================
# Immutability
# =========================================================

def test_tool_contract_is_immutable() -> None:
    """
    ToolContract should be immutable after creation.

    This prevents registered tool metadata from being changed
    accidentally after registration.
    """

    contract = ToolContract(
        name="search_products",
        description="Search products.",
        category="product",
        handler=sample_handler,
    )

    with pytest.raises(
        AttributeError,
    ):
        contract.name = "another_tool"  # type: ignore[misc]


# =========================================================
# Handler Execution
# =========================================================

def test_contract_handler_remains_callable() -> None:
    """
    The contract stores the actual handler without wrapping
    or changing it.
    """

    contract = ToolContract(
        name="search_products",
        description="Search products.",
        category="product",
        handler=sample_handler,
    )

    result = contract.handler(
        query="milk",
    )

    assert result == {
        "query": "milk",
    }