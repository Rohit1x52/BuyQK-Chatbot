"""
Tests for BuyQK Cart Tool Registry.

These tests verify:

- all canonical Cart tools are registered
- tool names are correct
- descriptions exist
- all tools belong to the cart category
- correct handlers are attached
- mutation/read-only metadata is correct
- input schemas are present
- registry lookup works
- registry execution reaches the correct handler
- no unintended semantic aliases exist
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_engine.tools.contracts import ToolContract

from ai_engine.tools.cart_registry import (
    ADD_TO_CART_CONTRACT,
    REMOVE_FROM_CART_CONTRACT,
    UPDATE_CART_ITEM_CONTRACT,
    CLEAR_CART_CONTRACT,
    GET_CART_CONTRACT,
    CART_TOOL_CONTRACTS,
    cart_registry,
    create_cart_registry,
)

from ai_engine.tools.cart_tools import (
    add_to_cart_tool,
    remove_from_cart_tool,
    update_cart_item_tool,
    clear_cart_tool,
    get_cart_tool,
)

from ai_engine.tools.registry import ToolRegistry
from ai_engine.tools.results import ToolResult


# =========================================================
# Expected Canonical Tool Names
# =========================================================


EXPECTED_CART_TOOLS = (
    "add_to_cart",
    "remove_from_cart",
    "update_cart_item",
    "clear_cart",
    "get_cart",
)


# =========================================================
# Registry Initialization
# =========================================================


def test_cart_registry_is_tool_registry() -> None:
    assert isinstance(
        cart_registry,
        ToolRegistry,
    )


def test_create_cart_registry_returns_new_registry() -> None:
    first = create_cart_registry()
    second = create_cart_registry()

    assert isinstance(
        first,
        ToolRegistry,
    )

    assert isinstance(
        second,
        ToolRegistry,
    )

    assert first is not second


def test_cart_registry_contains_all_expected_tools() -> None:
    assert cart_registry.list_names() == (
        EXPECTED_CART_TOOLS
    )


def test_cart_registry_contains_exactly_five_tools() -> None:
    assert len(
        cart_registry.list_tools()
    ) == 5


# =========================================================
# Contract Presence
# =========================================================


@pytest.mark.parametrize(
    "tool_name",
    EXPECTED_CART_TOOLS,
)
def test_cart_registry_has_tool(
    tool_name: str,
) -> None:

    assert cart_registry.has(
        tool_name
    )


@pytest.mark.parametrize(
    "tool_name",
    EXPECTED_CART_TOOLS,
)
def test_cart_registry_get_returns_contract(
    tool_name: str,
) -> None:

    contract = cart_registry.get(
        tool_name
    )

    assert contract.name == tool_name


# =========================================================
# Contract Metadata
# =========================================================


@pytest.mark.parametrize(
    "contract",
    CART_TOOL_CONTRACTS,
)
def test_cart_contract_has_required_metadata(
    contract: Any,
) -> None:

    assert contract.name
    assert contract.description
    assert contract.category == "cart"
    assert callable(contract.handler)


@pytest.mark.parametrize(
    "contract",
    CART_TOOL_CONTRACTS,
)
def test_cart_contract_has_input_schema(
    contract: Any,
) -> None:

    assert isinstance(
        contract.input_schema,
        dict,
    )

    assert (
        contract.input_schema["type"]
        == "object"
    )

    assert "properties" in contract.input_schema

    assert "required" in contract.input_schema


# =========================================================
# Correct Handler Mapping
# =========================================================


def test_add_to_cart_contract_uses_correct_handler() -> None:

    assert (
        ADD_TO_CART_CONTRACT.handler
        is add_to_cart_tool
    )


def test_remove_from_cart_contract_uses_correct_handler() -> None:

    assert (
        REMOVE_FROM_CART_CONTRACT.handler
        is remove_from_cart_tool
    )


def test_update_cart_item_contract_uses_correct_handler() -> None:

    assert (
        UPDATE_CART_ITEM_CONTRACT.handler
        is update_cart_item_tool
    )


def test_clear_cart_contract_uses_correct_handler() -> None:

    assert (
        CLEAR_CART_CONTRACT.handler
        is clear_cart_tool
    )


def test_get_cart_contract_uses_correct_handler() -> None:

    assert (
        GET_CART_CONTRACT.handler
        is get_cart_tool
    )


# =========================================================
# Mutability Metadata
# =========================================================


@pytest.mark.parametrize(
    "tool_name",
    [
        "add_to_cart",
        "remove_from_cart",
        "update_cart_item",
        "clear_cart",
    ],
)
def test_mutating_cart_tools_are_not_read_only(
    tool_name: str,
) -> None:

    contract = cart_registry.get(
        tool_name
    )

    assert contract.read_only is False


def test_get_cart_is_read_only() -> None:

    contract = cart_registry.get(
        "get_cart"
    )

    assert contract.read_only is True


# =========================================================
# Input Schema — add_to_cart
# =========================================================


def test_add_to_cart_schema() -> None:

    schema = (
        ADD_TO_CART_CONTRACT
        .input_schema
    )

    assert schema["properties"]["user_id"][
        "type"
    ] == "integer"

    assert schema["properties"]["product_id"][
        "type"
    ] == "integer"

    assert schema["properties"]["quantity"][
        "type"
    ] == "integer"

    assert set(
        schema["required"]
    ) == {
        "user_id",
        "product_id",
        "quantity",
    }


# =========================================================
# Input Schema — remove_from_cart
# =========================================================


def test_remove_from_cart_schema() -> None:

    schema = (
        REMOVE_FROM_CART_CONTRACT
        .input_schema
    )

    assert schema["properties"]["user_id"][
        "type"
    ] == "integer"

    assert schema["properties"]["product_id"][
        "type"
    ] == "integer"

    assert set(
        schema["required"]
    ) == {
        "user_id",
        "product_id",
    }


# =========================================================
# Input Schema — update_cart_item
# =========================================================


def test_update_cart_item_schema() -> None:

    schema = (
        UPDATE_CART_ITEM_CONTRACT
        .input_schema
    )

    assert schema["properties"]["user_id"][
        "type"
    ] == "integer"

    assert schema["properties"]["product_id"][
        "type"
    ] == "integer"

    assert schema["properties"]["quantity"][
        "type"
    ] == "integer"

    assert set(
        schema["required"]
    ) == {
        "user_id",
        "product_id",
        "quantity",
    }


# =========================================================
# Input Schema — clear_cart
# =========================================================


def test_clear_cart_schema() -> None:

    schema = (
        CLEAR_CART_CONTRACT
        .input_schema
    )

    assert schema["properties"]["user_id"][
        "type"
    ] == "integer"

    assert set(
        schema["required"]
    ) == {
        "user_id",
    }


# =========================================================
# Input Schema — get_cart
# =========================================================


def test_get_cart_schema() -> None:

    schema = (
        GET_CART_CONTRACT
        .input_schema
    )

    assert schema["properties"]["user_id"][
        "type"
    ] == "integer"

    assert set(
        schema["required"]
    ) == {
        "user_id",
    }


# =========================================================
# Registry Lookup Normalization
# =========================================================


def test_registry_lookup_normalizes_case_and_whitespace() -> None:

    assert (
        cart_registry.get(
            " ADD_TO_CART "
        )
        is ADD_TO_CART_CONTRACT
    )

    assert (
        cart_registry.get(
            "Get_Cart"
        )
        is GET_CART_CONTRACT
    )


# =========================================================
# No Semantic Alias Registration
# =========================================================


@pytest.mark.parametrize(
    "alias",
    [
        "add_cart",
        "cart_add",
        "remove_cart",
        "cart_remove",
        "update_cart_quantity",
        "update_quantity",
        "show_cart",
        "cart",
    ],
)
def test_registry_does_not_register_semantic_aliases(
    alias: str,
) -> None:

    assert not cart_registry.has(
        alias
    )


# =========================================================
# Registry Execution
# =========================================================


def test_registry_executes_add_to_cart_handler() -> None:
    expected = ToolResult.ok(
        tool="add_to_cart",
        data={
            "cart_id": 100,
        },
    )

    def fake_handler(
        **kwargs: Any,
    ) -> ToolResult:
        assert kwargs["user_id"] == 1
        assert kwargs["product_id"] == 10
        assert kwargs["quantity"] == 2
        return expected

    contract = ToolContract(
        name="add_to_cart_test",
        description="Test add-to-cart tool.",
        category="cart",
        handler=fake_handler,
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )

    registry = ToolRegistry(
        tools=[contract],
    )

    result = registry.execute(
        "add_to_cart_test",
        user_id=1,
        product_id=10,
        quantity=2,
    )

    assert result is expected

def test_registry_executes_get_cart_handler() -> None:
    expected = ToolResult.ok(
        tool="get_cart_test",
        data={
            "cart_id": 100,
            "items": [],
        },
    )

    def fake_handler(
        **kwargs: Any,
    ) -> ToolResult:
        assert kwargs["user_id"] == 1
        return expected

    contract = ToolContract(
        name="get_cart_test",
        description="Test get-cart tool.",
        category="cart",
        handler=fake_handler,
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )

    registry = ToolRegistry(
        tools=[contract],
    )

    result = registry.execute(
        "get_cart_test",
        user_id=1,
    )

    assert result is expected

# =========================================================
# Unknown Tool
# =========================================================


def test_cart_registry_rejects_unknown_tool() -> None:

    result = cart_registry.execute(
        "some_unknown_cart_tool",
        user_id=1,
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.tool == "some_unknown_cart_tool"

    assert result.error is not None

    assert (
        result.error.code
        == "tool_not_registered"
    )


# =========================================================
# Contract Collection Integrity
# =========================================================


def test_cart_tool_contracts_are_unique() -> None:

    names = [
        contract.name
        for contract in CART_TOOL_CONTRACTS
    ]

    assert len(names) == len(
        set(names)
    )


def test_cart_tool_contracts_match_registry() -> None:

    contract_names = tuple(
        contract.name
        for contract in CART_TOOL_CONTRACTS
    )

    assert (
        contract_names
        == cart_registry.list_names()
    )