"""
Tests for the BuyQK Product Tool Registry.

These tests verify:

- Product contracts are correctly defined.
- Product tools are registered under canonical names.
- All handlers point to the correct implementations.
- Product tools are marked read-only.
- Input schemas are present.
- A fresh registry can be created independently.
- The registry can execute the registered tools.
- Duplicate registration protection remains handled by
  the generic ToolRegistry.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ai_engine.tools.contracts import ToolContract
from ai_engine.tools.product_registry import (
    CHECK_PRODUCT_AVAILABILITY_CONTRACT,
    GET_PRODUCT_CONTRACT,
    SEARCH_PRODUCTS_CONTRACT,
    create_product_registry,
    product_registry,
)
from ai_engine.tools.product_tools import (
    check_product_availability_tool,
    get_product_tool,
    search_products_tool,
)
from ai_engine.tools.registry import ToolRegistry
from ai_engine.tools.results import ToolResult


# =========================================================
# Contract Tests
# =========================================================


def test_search_products_contract_is_valid() -> None:
    contract = SEARCH_PRODUCTS_CONTRACT

    assert isinstance(
        contract,
        ToolContract,
    )

    assert contract.name == "search_products"

    assert contract.category == "product"

    assert contract.handler is search_products_tool

    assert contract.read_only is True

    assert contract.input_schema is not None

    assert contract.input_schema["type"] == "object"

    assert "query" in contract.input_schema[
        "properties"
    ]

    assert "limit" in contract.input_schema[
        "properties"
    ]

    assert contract.input_schema["required"] == [
        "query",
    ]


def test_get_product_contract_is_valid() -> None:
    contract = GET_PRODUCT_CONTRACT

    assert isinstance(
        contract,
        ToolContract,
    )

    assert contract.name == "get_product"

    assert contract.category == "product"

    assert contract.handler is get_product_tool

    assert contract.read_only is True

    assert contract.input_schema is not None

    assert contract.input_schema["type"] == "object"

    assert "product_id" in contract.input_schema[
        "properties"
    ]

    assert contract.input_schema["required"] == [
        "product_id",
    ]


def test_check_product_availability_contract_is_valid() -> None:
    contract = (
        CHECK_PRODUCT_AVAILABILITY_CONTRACT
    )

    assert isinstance(
        contract,
        ToolContract,
    )

    assert (
        contract.name
        == "check_product_availability"
    )

    assert contract.category == "product"

    assert (
        contract.handler
        is check_product_availability_tool
    )

    assert contract.read_only is True

    assert contract.input_schema is not None

    assert contract.input_schema["type"] == "object"

    assert "product_id" in contract.input_schema[
        "properties"
    ]

    assert "quantity" in contract.input_schema[
        "properties"
    ]

    assert contract.input_schema["required"] == [
        "product_id",
    ]


# =========================================================
# Registry Construction
# =========================================================


def test_create_product_registry_returns_tool_registry() -> None:
    registry = create_product_registry()

    assert isinstance(
        registry,
        ToolRegistry,
    )


def test_product_registry_contains_expected_tools() -> None:
    registry = create_product_registry()

    assert registry.list_names() == (
        "search_products",
        "get_product",
        "check_product_availability",
    )


def test_product_registry_contains_exactly_three_tools() -> None:
    registry = create_product_registry()

    assert len(
        registry.list_tools()
    ) == 3


@pytest.mark.parametrize(
    "tool_name",
    [
        "search_products",
        "get_product",
        "check_product_availability",
    ],
)
def test_product_registry_has_tool(
    tool_name: str,
) -> None:
    registry = create_product_registry()

    assert registry.has(
        tool_name
    ) is True


@pytest.mark.parametrize(
    "tool_name",
    [
        "search_products",
        "get_product",
        "check_product_availability",
    ],
)
def test_product_registry_get_returns_contract(
    tool_name: str,
) -> None:
    registry = create_product_registry()

    contract = registry.get(
        tool_name
    )

    assert isinstance(
        contract,
        ToolContract,
    )

    assert contract.name == tool_name


# =========================================================
# Handler Mapping
# =========================================================


def test_product_registry_maps_search_handler() -> None:
    registry = create_product_registry()

    contract = registry.get(
        "search_products"
    )

    assert contract.handler is search_products_tool


def test_product_registry_maps_get_handler() -> None:
    registry = create_product_registry()

    contract = registry.get(
        "get_product"
    )

    assert contract.handler is get_product_tool


def test_product_registry_maps_availability_handler() -> None:
    registry = create_product_registry()

    contract = registry.get(
        "check_product_availability"
    )

    assert (
        contract.handler
        is check_product_availability_tool
    )


# =========================================================
# Read-Only Metadata
# =========================================================


def test_all_product_tools_are_read_only() -> None:
    registry = create_product_registry()

    for contract in registry.list_tools():
        assert contract.category == "product"
        assert contract.read_only is True


# =========================================================
# Input Schema Metadata
# =========================================================


def test_all_product_tools_have_input_schema() -> None:
    registry = create_product_registry()

    for contract in registry.list_tools():
        assert contract.input_schema is not None
        assert (
            contract.input_schema["type"]
            == "object"
        )


def test_product_input_schemas_are_not_shared_mutably() -> None:
    """
    The registry contracts are immutable dataclasses.

    This test verifies that each product contract has its
    own schema object rather than accidentally sharing the
    same mutable dictionary.
    """

    schemas = [
        contract.input_schema
        for contract in (
            SEARCH_PRODUCTS_CONTRACT,
            GET_PRODUCT_CONTRACT,
            CHECK_PRODUCT_AVAILABILITY_CONTRACT,
        )
    ]

    assert len(
        {id(schema) for schema in schemas}
    ) == 3


# =========================================================
# Registry Isolation
# =========================================================


def test_create_product_registry_returns_fresh_registry() -> None:
    first = create_product_registry()
    second = create_product_registry()

    assert first is not second

    assert first.list_names() == second.list_names()


def test_registry_mutation_does_not_affect_factory() -> None:
    registry = create_product_registry()

    registry.unregister(
        "search_products"
    )

    assert registry.has(
        "search_products"
    ) is False

    fresh_registry = create_product_registry()

    assert fresh_registry.has(
        "search_products"
    ) is True


# =========================================================
# Default Registry
# =========================================================


def test_default_product_registry_is_available() -> None:
    assert isinstance(
        product_registry,
        ToolRegistry,
    )


def test_default_product_registry_contains_product_tools() -> None:
    assert product_registry.list_names() == (
        "search_products",
        "get_product",
        "check_product_availability",
    )


# =========================================================
# Execution Boundary
# =========================================================


def test_registry_executes_registered_search_tool() -> None:
    """
    Verify that execution travels through ToolRegistry and
    reaches the registered handler.
    """

    handler = Mock(
        return_value=ToolResult.ok(
            tool="search_products",
            data={
                "products": [],
                "count": 0,
                "query": "milk",
            },
        )
    )

    registry = ToolRegistry(
        tools=(
            ToolContract(
                name="search_products",
                description="Search products.",
                category="product",
                handler=handler,
                read_only=True,
            ),
        )
    )

    result = registry.execute(
        "search_products",
        db=Mock(),
        query="milk",
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "search_products"

    handler.assert_called_once_with(
        db=result.data
        if False
        else handler.call_args.kwargs["db"],
        query="milk",
    )


def test_product_registry_handlers_are_callable() -> None:
    registry = create_product_registry()

    for contract in registry.list_tools():
        assert callable(
            contract.handler
        )


# =========================================================
# Canonical Names
# =========================================================


@pytest.mark.parametrize(
    "tool_name",
    [
        "search_products",
        "get_product",
        "check_product_availability",
    ],
)
def test_product_tool_names_are_canonical(
    tool_name: str,
) -> None:
    registry = create_product_registry()

    assert registry.has(
        tool_name
    )

    assert registry.has(
        tool_name.upper()
    )


@pytest.mark.parametrize(
    "alias",
    [
        "search product",
        "product search",
        "find product",
        "tracking",
        "availability",
    ],
)
def test_product_registry_does_not_add_semantic_aliases(
    alias: str,
) -> None:
    registry = create_product_registry()

    assert registry.has(
        alias
    ) is False


# =========================================================
# Duplicate Registration
# =========================================================


def test_product_registry_rejects_duplicate_registration() -> None:
    registry = create_product_registry()

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            SEARCH_PRODUCTS_CONTRACT
        )


# =========================================================
# Unknown Tools
# =========================================================


def test_product_registry_does_not_guess_unknown_tools() -> None:
    registry = create_product_registry()

    assert registry.has(
        "find_products"
    ) is False

    with pytest.raises(
        KeyError,
        match="not registered",
    ):
        registry.get(
            "find_products"
        )


def test_product_registry_unknown_execution_returns_failure() -> None:
    registry = create_product_registry()

    result = registry.execute(
        "find_products",
        query="milk",
    )

    assert result.success is False

    assert result.tool == "find_products"

    assert result.error is not None

    assert (
        result.error.code
        == "tool_not_registered"
    )


# =========================================================
# Category Consistency
# =========================================================


def test_all_registered_product_tools_have_product_category() -> None:
    registry = create_product_registry()

    categories = {
        contract.category
        for contract in registry.list_tools()
    }

    assert categories == {
        "product",
    }
