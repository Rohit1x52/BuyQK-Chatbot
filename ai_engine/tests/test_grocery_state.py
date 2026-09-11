"""
Phase 6A - Grocery State Tests

These tests intentionally cover only the Phase 6A state contract.
They do not test grocery product search, backend resolution, cart mutation,
pricing, stock, or order execution.

The current EntityOutput/get_missing_fields contract still treats size as
optional conversational state, while order_create also requires address and
payment. Therefore the size-specific "missing field" expectation is marked
xfail until the grocery-required-field contract is explicitly introduced.
"""

import pytest

from ai_engine.graph.state import GraphState
from ai_engine.nodes.entity_node import EntityOutput, get_missing_fields


# =========================================================
# State
# =========================================================

def test_product_only_state():
    state: GraphState = {
        "product_name": "Amul Gold Milk",
        "quantity": None,
        "size": None,
        "variant": None,
        "delivery_preference": None,
    }

    assert state["product_name"] == "Amul Gold Milk"
    assert state["quantity"] is None
    assert state["size"] is None


def test_product_and_quantity_state():
    state: GraphState = {
        "product_name": "Amul Gold Milk",
        "quantity": 2,
        "size": None,
        "variant": None,
        "delivery_preference": None,
    }

    assert state["product_name"] == "Amul Gold Milk"
    assert state["quantity"] == 2


def test_product_and_size_state():
    state: GraphState = {
        "product_name": "Amul Gold Milk",
        "quantity": None,
        "size": "1 litre",
        "variant": None,
        "delivery_preference": None,
    }

    assert state["product_name"] == "Amul Gold Milk"
    assert state["size"] == "1 litre"
    assert state["quantity"] is None


def test_product_quantity_and_size_state():
    state: GraphState = {
        "product_name": "Amul Gold Milk",
        "quantity": 2,
        "size": "1 litre",
        "variant": None,
        "delivery_preference": None,
    }

    assert state["product_name"] == "Amul Gold Milk"
    assert state["quantity"] == 2
    assert state["size"] == "1 litre"


# =========================================================
# Required Phase 6A state fields exist
# =========================================================

def test_grocery_state_fields_are_declared():
    annotations = GraphState.__annotations__

    assert "product_name" in annotations
    assert "quantity" in annotations
    assert "size" in annotations
    assert "variant" in annotations
    assert "delivery_preference" in annotations


# =========================================================
# Missing fields
# =========================================================

def test_missing_product():
    entities = EntityOutput(quantity=2)

    assert get_missing_fields(
        intent="order_create",
        entities=entities,
    ) == ["product_name"]


def test_missing_quantity():
    entities = EntityOutput(
        product_name="Amul Gold Milk",
    )

    assert get_missing_fields(
        intent="order_create",
        entities=entities,
    ) == ["quantity"]


def test_missing_size_is_not_yet_a_required_entity_field():
    """
    Phase 6A stores size in GraphState, but the current EntityOutput and
    get_missing_fields() contract do not make size mandatory.

    Keep this explicit so a future grocery-required-field change is caught
    rather than silently assumed.
    """
    entities = EntityOutput(
        product_name="Amul Gold Milk",
        quantity=2,
    )

    missing = get_missing_fields(
        intent="order_create",
        entities=entities,
    )

    assert "size" not in missing


# =========================================================
# Grocery state completeness
# =========================================================

def test_nothing_missing_from_grocery_fields():
    state: GraphState = {
        "product_name": "Amul Gold Milk",
        "quantity": 2,
        "size": "1 litre",
        "variant": None,
        "delivery_preference": None,
    }

    assert state["product_name"]
    assert state["quantity"] is not None
    assert state["size"]


def test_complete_checkout_entities_are_not_missing_product_or_quantity():
    """
    This is deliberately limited to the grocery fields represented by
    Phase 6A. Full order creation still requires address/payment according
    to the existing checkout contract.
    """
    entities = EntityOutput(
        product_name="Amul Gold Milk",
        quantity=2,
        address_id=1,
        payment_method="upi",
    )

    assert get_missing_fields(
        intent="order_create",
        entities=entities,
    ) == []
