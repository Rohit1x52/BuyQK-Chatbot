"""
BuyQK AI - Grocery Product Lifecycle Tests

Phase 6B:
    Product search -> candidate preservation -> product presentation ->
    conversational continuation.

These tests use synthetic backend-derived product payloads. They do not
hardcode real catalog/business data and do not call the real LLM.
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_engine.graph.state import GraphState
from ai_engine.nodes import tool_node as tool_node_module
from ai_engine.nodes.response_node import response_node


# =========================================================
# Test Data Helpers
# =========================================================

def make_product(
    product_id: int,
    name: str,
    *,
    price: float = 100.0,
    stock: int = 10,
) -> dict[str, Any]:
    """
    Create a synthetic backend product for isolated tests.

    The values are test fixtures only and do not represent
    real BuyQK catalog data.
    """
    return {
        "id": product_id,
        "name": name,
        "description": f"Test description for {name}",
        "brand": "Test Brand",
        "price": price,
        "stock": stock,
        "image_url": None,
        "is_available": stock > 0,
        "merchant_id": 1,
        "category_id": 1,
    }


def make_search_state(
    product_name: str = "test product",
) -> GraphState:
    """
    Create the minimum state required by the search tool path.
    """
    return {
        "message": f"Find {product_name}",
        "intent": "product_search",
        "tool_name": "search_products",
        "entities": {
            "product_name": product_name,
        },
        "missing_fields": [],
        "next_missing": None,
    }


# =========================================================
# Product Search Lifecycle
# =========================================================

def test_product_search_preserves_complete_candidate_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A multi-result backend search must preserve every returned candidate.

    The Response Node may present these candidates, but it must not reduce
    them to an invented or LLM-selected product.
    """
    candidates = [
        make_product(101, "Test Product A"),
        make_product(102, "Test Product B"),
        make_product(103, "Test Product C"),
    ]

    def fake_search_products(
        *,
        db: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        assert query == "test product"
        return candidates

    monkeypatch.setattr(
        tool_node_module,
        "search_products",
        fake_search_products,
    )

    result = tool_node_module.tool_node(
        make_search_state(),
        db=object(),
    )

    assert result["tool_name"] == "search_products"

    tool_result = result["tool_result"]

    # Public Tool Node uses the canonical ToolResult contract.
    assert tool_result is not None
    assert tool_result.success is True
    assert tool_result.tool == "search_products"

    # Product search business data lives inside ToolResult.data.
    assert isinstance(tool_result.data, dict)

    assert tool_result.data["type"] == "product_search"

    returned_products = tool_result.data["products"]

    assert isinstance(returned_products, list)
    assert len(returned_products) == len(candidates)

    # Phase 6B:
    # The complete backend-derived candidate set must also be preserved
    # directly in GraphState.
    assert result["product_search_results"] == returned_products

    # Multiple candidates must not be silently converted into one selection.
    assert result["selected_product"] is None


def test_single_product_search_sets_selected_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A search returning exactly one backend product may expose that product
    as selected_product while still preserving the complete candidate list.
    """
    candidate = make_product(
        201,
        "Test Single Product",
    )

    def fake_search_products(
        *,
        db: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        assert query == "test product"
        return [candidate]

    monkeypatch.setattr(
        tool_node_module,
        "search_products",
        fake_search_products,
    )

    result = tool_node_module.tool_node(
        make_search_state(),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result is not None
    assert tool_result.success is True
    assert tool_result.tool == "search_products"
    assert isinstance(tool_result.data, dict)

    products = tool_result.data["products"]

    assert result["product_search_results"] == products
    assert len(result["product_search_results"]) == 1

    assert result["selected_product"] == products[0]

    # The product ID comes from the backend result, not from
    # an LLM-generated value.
    assert result["selected_product"]["id"] == 201


def test_empty_product_search_preserves_empty_candidate_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An empty backend result must remain an empty result set.
    """
    def fake_search_products(
        *,
        db: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(
        tool_node_module,
        "search_products",
        fake_search_products,
    )

    result = tool_node_module.tool_node(
        make_search_state(),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result is not None
    assert tool_result.success is True
    assert tool_result.tool == "search_products"
    assert isinstance(tool_result.data, dict)

    assert tool_result.data["type"] == "product_search"
    assert tool_result.data["products"] == []

    assert result["product_search_results"] == []
    assert result["selected_product"] is None


def test_product_search_does_not_invent_product_when_name_missing() -> None:
    """
    Search must fail safely when no product query is available.

    The public Tool Node exposes the failure using the canonical
    ToolResult contract.
    """
    state: GraphState = {
        "message": "Find something",
        "intent": "product_search",
        "tool_name": "search_products",
        "entities": {},
    }

    result = tool_node_module.tool_node(
        state,
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result is not None

    assert tool_result.success is False
    assert tool_result.tool == "search_products"

    assert tool_result.error is not None

    assert (
        "Product name is required."
        in tool_result.error.message
    )


# =========================================================
# Response / Presentation Lifecycle
# =========================================================

def test_response_node_presents_backend_product_candidates() -> None:
    """
    Response Node must present the backend-returned candidates without
    resolving, scoring, or inventing a product.
    """
    products = [
        make_product(
            301,
            "Backend Product A",
        ),
        make_product(
            302,
            "Backend Product B",
        ),
    ]

    state: GraphState = {
        "message": "find test product",
        "intent": "product_search",
        "tool_name": "search_products",
        "tool_result": {
            "success": True,
            "type": "product_search",
            "products": products,
        },
        "product_search_results": products,
        "entities": {
            "product_name": "test product",
        },
        "missing_fields": [],
        "next_missing": None,
        "conversation_history": [],
    }

    result = response_node(state)

    assert "Backend Product A" in result["response"]
    assert "Backend Product B" in result["response"]

    metadata = result["metadata"]

    assert metadata["type"] == "product_results"
    assert metadata["products"] == products


# =========================================================
# Conversational Continuation
# =========================================================

def test_quantity_followup_preserves_selected_product_context() -> None:
    """
    When product context is already known and quantity is the next missing
    field, the presentation layer should ask for quantity using that context.
    """
    from ai_engine.nodes.response_node import (
        _localized_context_fallback,
    )

    state: GraphState = {
        "message": "2",
        "intent": "order_create",
        "entities": {
            "product_name": "Selected Product",
            "product_id": 401,
        },
        "product_name": "Selected Product",
        "product_id": 401,
        "quantity": None,
        "missing_fields": [
            "quantity",
        ],
        "next_missing": "quantity",
        "conversation_history": [],
    }

    response = _localized_context_fallback(
        state,
        "quantity",
    )

    assert "Selected Product" in response
    assert "quantity" in response.lower()


def test_product_search_candidates_are_not_used_as_transactional_truth() -> None:
    """
    Search candidates are discovery data.

    A candidate set alone must not imply that:
        - an order was created
        - checkout completed
        - a transaction succeeded

    The Response Node should expose product candidates through its
    presentation metadata.
    """
    products = [
        make_product(
            501,
            "Candidate Product A",
        ),
        make_product(
            502,
            "Candidate Product B",
        ),
    ]

    state: GraphState = {
        "message": "find test product",
        "intent": "product_search",
        "tool_name": "search_products",
        "tool_result": {
            "success": True,
            "type": "product_search",
            "products": products,
        },
        "product_search_results": products,
        "entities": {},
        "missing_fields": [],
        "next_missing": None,
    }

    result = response_node(state)

    # Product discovery must not imply an order.
    assert result.get("order_created") is not True

    # Product discovery must not imply completed checkout.
    assert result.get("checkout_status") != "completed"

    # The search result remains discovery/presentation data.
    metadata = result["metadata"]

    assert metadata["type"] == "product_results"
    assert metadata["products"] == products