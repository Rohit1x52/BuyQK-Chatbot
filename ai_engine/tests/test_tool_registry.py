"""
Tests for BuyQK tool registry.

These tests verify that ToolRegistry:

- registers valid ToolContract instances
- rejects invalid registrations
- prevents duplicate tool names
- retrieves registered tools
- checks tool existence
- lists registered tools
- unregisters tools
- executes registered handlers
- wraps normal handler return values in ToolResult
- preserves an existing ToolResult
- normalizes ToolError failures
- normalizes unexpected exceptions
- rejects unknown tools
- normalizes lookup whitespace/casing only
- does not perform semantic tool aliasing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from ai_engine.tools.contracts import ToolContract
from ai_engine.tools.errors import (
    ToolNotFoundError,
    ToolValidationError,
)
from ai_engine.tools.registry import ToolRegistry
from ai_engine.tools.results import ToolResult


# =========================================================
# Test Helpers
# =========================================================


def search_handler(
    **kwargs: Any,
) -> dict[str, Any]:
    """Simple successful handler."""

    return {
        "products": [],
        "query": kwargs.get("query"),
    }


def echo_handler(
    value: Any,
) -> Any:
    """Returns the supplied value."""

    return value


def failing_validation_handler(
    **kwargs: Any,
) -> None:
    """Raises a known ToolError."""

    raise ToolValidationError(
        "Invalid tool input.",
        details={
            "field": "quantity",
        },
    )


def failing_not_found_handler(
    **kwargs: Any,
) -> None:
    """Raises a known not-found error."""

    raise ToolNotFoundError(
        "Resource was not found.",
    )


def failing_runtime_handler(
    **kwargs: Any,
) -> None:
    """Raises an unexpected exception."""

    raise RuntimeError(
        "Internal implementation failure.",
    )


# =========================================================
# Contract Helper
# =========================================================


def make_contract(
    name: str = "search_products",
    handler: Any = search_handler,
    category: str = "product",
) -> ToolContract:
    """Create a valid ToolContract for tests."""

    return ToolContract(
        name=name,
        description=f"Test tool: {name}.",
        category=category,
        handler=handler,
    )


# =========================================================
# Initialization
# =========================================================


def test_registry_starts_empty() -> None:
    registry = ToolRegistry()

    assert registry.list_tools() == ()
    assert registry.list_names() == ()


def test_registry_can_initialize_with_tools() -> None:
    first = make_contract(
        name="search_products",
    )

    second = make_contract(
        name="get_product",
    )

    registry = ToolRegistry(
        tools=[
            first,
            second,
        ],
    )

    assert registry.list_names() == (
        "search_products",
        "get_product",
    )

    assert registry.get(
        "search_products"
    ) is first

    assert registry.get(
        "get_product"
    ) is second


# =========================================================
# Registration
# =========================================================


def test_register_tool() -> None:
    registry = ToolRegistry()

    contract = make_contract()

    registered = registry.register(
        contract
    )

    assert registered is contract

    assert registry.has(
        "search_products"
    )


def test_register_rejects_non_contract() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        TypeError,
        match=(
            "Only ToolContract instances "
            "can be registered"
        ),
    ):
        registry.register(
            "search_products"  # type: ignore[arg-type]
        )


def test_register_rejects_duplicate_name() -> None:
    registry = ToolRegistry()

    first = make_contract(
        name="search_products",
    )

    second = make_contract(
        name="search_products",
    )

    registry.register(first)

    with pytest.raises(
        ValueError,
        match=(
            "Tool 'search_products' "
            "is already registered"
        ),
    ):
        registry.register(second)


# =========================================================
# Lookup
# =========================================================


def test_get_registered_tool() -> None:
    registry = ToolRegistry()

    contract = make_contract()

    registry.register(contract)

    result = registry.get(
        "search_products"
    )

    assert result is contract


def test_get_unknown_tool_raises_key_error() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        KeyError,
        match=(
            "Tool 'search_products' "
            "is not registered"
        ),
    ):
        registry.get(
            "search_products"
        )


def test_has_returns_true_for_registered_tool() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract()
    )

    assert registry.has(
        "search_products"
    ) is True


def test_has_returns_false_for_unknown_tool() -> None:
    registry = ToolRegistry()

    assert registry.has(
        "search_products"
    ) is False


# =========================================================
# Name Normalization
# =========================================================


def test_lookup_normalizes_whitespace() -> None:
    registry = ToolRegistry()

    contract = make_contract(
        name="search_products",
    )

    registry.register(contract)

    assert registry.get(
        "  search_products  "
    ) is contract


def test_lookup_normalizes_case() -> None:
    registry = ToolRegistry()

    contract = make_contract(
        name="search_products",
    )

    registry.register(contract)

    assert registry.get(
        "SEARCH_PRODUCTS"
    ) is contract


def test_lookup_normalizes_case_and_whitespace() -> None:
    registry = ToolRegistry()

    contract = make_contract(
        name="search_products",
    )

    registry.register(contract)

    assert registry.get(
        "  SEARCH_PRODUCTS  "
    ) is contract


def test_registry_does_not_perform_semantic_aliasing() -> None:
    """
    The registry must not decide that one semantic name means
    another tool.

    For example:

        tracking
            !=
        track_order

    Semantic mapping belongs to the AI planning/policy/
    decision layer.
    """

    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="track_order",
        )
    )

    assert registry.has(
        "track_order"
    ) is True

    assert registry.has(
        "tracking"
    ) is False

    with pytest.raises(
        KeyError,
        match="Tool 'tracking' is not registered",
    ):
        registry.get(
            "tracking"
        )


def test_registry_does_not_normalize_business_aliases() -> None:
    """
    Only casing and surrounding whitespace are normalized.
    """

    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="cancel_order",
        )
    )

    assert registry.has(
        "cancel_order"
    ) is True

    assert registry.has(
        "cancel"
    ) is False

    assert registry.has(
        "order_cancel"
    ) is False


# =========================================================
# Listing
# =========================================================


def test_list_tools_returns_registered_contracts() -> None:
    registry = ToolRegistry()

    first = make_contract(
        name="search_products",
    )

    second = make_contract(
        name="get_product",
    )

    registry.register(first)
    registry.register(second)

    tools = registry.list_tools()

    assert tools == (
        first,
        second,
    )


def test_list_names_returns_registered_names() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="search_products",
        )
    )

    registry.register(
        make_contract(
            name="get_product",
        )
    )

    assert registry.list_names() == (
        "search_products",
        "get_product",
    )


def test_list_tools_returns_immutable_collection() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract()
    )

    tools = registry.list_tools()

    assert isinstance(
        tools,
        tuple,
    )


def test_list_names_returns_immutable_collection() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract()
    )

    names = registry.list_names()

    assert isinstance(
        names,
        tuple,
    )


# =========================================================
# Unregistration
# =========================================================


def test_unregister_existing_tool() -> None:
    registry = ToolRegistry()

    contract = make_contract()

    registry.register(contract)

    removed = registry.unregister(
        "search_products"
    )

    assert removed is contract

    assert registry.has(
        "search_products"
    ) is False


def test_unregister_unknown_tool_raises_key_error() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        KeyError,
        match=(
            "Tool 'search_products' "
            "is not registered"
        ),
    ):
        registry.unregister(
            "search_products"
        )


# =========================================================
# Successful Execution
# =========================================================


def test_execute_registered_tool() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="search_products",
        )
    )

    result = registry.execute(
        "search_products",
        query="milk",
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "search_products"

    assert result.data == {
        "products": [],
        "query": "milk",
    }

    assert result.error is None


def test_execute_wraps_plain_handler_result() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="echo",
            handler=echo_handler,
        )
    )

    result = registry.execute(
        "echo",
        value="hello",
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "echo"
    assert result.data == "hello"
    assert result.error is None


def test_execute_supports_none_handler_result() -> None:
    def handler() -> None:
        return None

    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="clear_cart",
            handler=handler,
            category="cart",
        )
    )

    result = registry.execute(
        "clear_cart"
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "clear_cart"
    assert result.data is None
    assert result.error is None


def test_registry_executes_registered_search_tool() -> None:
    """
    Verify that ToolRegistry executes the registered handler
    with the exact arguments supplied by the caller.
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

    db = Mock()

    result = registry.execute(
        "search_products",
        db=db,
        query="milk",
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is True
    assert result.tool == "search_products"

    assert result.data == {
        "products": [],
        "count": 0,
        "query": "milk",
    }

    assert result.error is None

    handler.assert_called_once_with(
        db=db,
        query="milk",
    )


# =========================================================
# Existing ToolResult
# =========================================================


def test_execute_preserves_existing_tool_result() -> None:
    expected = ToolResult.ok(
        tool="search_products",
        data={
            "products": [],
        },
    )

    def handler() -> ToolResult[Any]:
        return expected

    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="search_products",
            handler=handler,
        )
    )

    result = registry.execute(
        "search_products"
    )

    assert result is expected


def test_execute_preserves_failed_tool_result() -> None:
    from ai_engine.tools.results import (
        ToolErrorResult,
    )

    expected = ToolResult.fail(
        tool="search_products",
        error=ToolErrorResult(
            code="not_found",
            message="No products found.",
        ),
    )

    def handler() -> ToolResult[Any]:
        return expected

    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="search_products",
            handler=handler,
        )
    )

    result = registry.execute(
        "search_products"
    )

    assert result is expected
    assert result.success is False


# =========================================================
# ToolError Handling
# =========================================================


def test_execute_normalizes_validation_error() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="add_to_cart",
            handler=failing_validation_handler,
            category="cart",
        )
    )

    result = registry.execute(
        "add_to_cart",
    )

    assert result.success is False
    assert result.tool == "add_to_cart"
    assert result.data is None

    assert result.error is not None

    assert (
        result.error.code
        == "validation_error"
    )

    assert (
        result.error.message
        == "Invalid tool input."
    )

    assert result.error.details == {
        "field": "quantity",
    }


def test_execute_normalizes_not_found_error() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="get_product",
            handler=failing_not_found_handler,
        )
    )

    result = registry.execute(
        "get_product",
    )

    assert result.success is False
    assert result.tool == "get_product"

    assert result.error is not None

    assert result.error.code == "not_found"

    assert (
        result.error.message
        == "Resource was not found."
    )


# =========================================================
# Unexpected Exception Handling
# =========================================================


def test_execute_normalizes_unexpected_exception() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="backend_operation",
            handler=failing_runtime_handler,
        )
    )

    result = registry.execute(
        "backend_operation",
    )

    assert result.success is False
    assert result.tool == "backend_operation"
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

    assert result.error.details is None


def test_execute_does_not_expose_unexpected_exception() -> None:
    registry = ToolRegistry()

    secret_message = (
        "internal database credentials"
    )

    def handler() -> None:
        raise RuntimeError(
            secret_message
        )

    registry.register(
        make_contract(
            name="unsafe_backend_operation",
            handler=handler,
        )
    )

    result = registry.execute(
        "unsafe_backend_operation"
    )

    assert result.success is False

    assert result.error is not None

    assert (
        secret_message
        not in result.error.message
    )

    assert result.error.details is None


# =========================================================
# Unknown Tool Execution
# =========================================================


def test_execute_unknown_tool_returns_failure() -> None:
    registry = ToolRegistry()

    result = registry.execute(
        "search_products"
    )

    assert isinstance(
        result,
        ToolResult,
    )

    assert result.success is False
    assert result.tool == "search_products"
    assert result.data is None

    assert result.error is not None

    assert (
        result.error.code
        == "tool_not_registered"
    )

    assert (
        result.error.message
        == (
            "Tool 'search_products' "
            "is not registered."
        )
    )

    assert result.error.details == {
        "tool": "search_products",
    }


def test_execute_unknown_tool_does_not_guess_alternative() -> None:
    registry = ToolRegistry()

    registry.register(
        make_contract(
            name="track_order",
        )
    )

    result = registry.execute(
        "tracking",
    )

    assert result.success is False
    assert result.tool == "tracking"

    assert result.error is not None

    assert (
        result.error.code
        == "tool_not_registered"
    )

    assert result.error.details == {
        "tool": "tracking",
    }


# =========================================================
# Lookup Input Validation
# =========================================================


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_get_rejects_invalid_tool_name(
    invalid_name: Any,
) -> None:
    registry = ToolRegistry()

    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        registry.get(
            invalid_name
        )


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_has_rejects_invalid_tool_name(
    invalid_name: Any,
) -> None:
    registry = ToolRegistry()

    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        registry.has(
            invalid_name
        )


# =========================================================
# Registry Isolation
# =========================================================


def test_two_registries_are_independent() -> None:
    first = ToolRegistry()
    second = ToolRegistry()

    first.register(
        make_contract(
            name="search_products",
        )
    )

    assert first.has(
        "search_products"
    ) is True

    assert second.has(
        "search_products"
    ) is False


def test_unregister_does_not_affect_other_registry() -> None:
    first = ToolRegistry()
    second = ToolRegistry()

    contract = make_contract(
        name="search_products",
    )

    first.register(contract)

    second.register(
        make_contract(
            name="search_products",
        )
    )

    first.unregister(
        "search_products"
    )

    assert first.has(
        "search_products"
    ) is False

    assert second.has(
        "search_products"
    ) is True
