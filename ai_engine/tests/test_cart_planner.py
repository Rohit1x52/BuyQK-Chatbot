from __future__ import annotations

from ai_engine.nodes.planner_node import (
    _cart_capability_from_state,
    _build_cart_arguments,
    _deterministic_plan_fallback,
    _normalize_action,
)


def test_cart_action_mapping():
    cases = {
        "add_item": "add_to_cart",
        "remove_item": "remove_from_cart",
        "update_quantity": "update_cart_item",
        "clear_cart": "clear_cart",
        "show_cart": "show_cart",
        "checkout": "checkout_cart",
    }

    for cart_action, expected in cases.items():
        state = {
            "intent": "cart",
            "entities": {
                "cart_action": cart_action,
            },
        }

        assert _cart_capability_from_state(state) == expected


def test_cart_action_missing_returns_none():
    state = {
        "intent": "cart",
        "entities": {},
    }

    assert _cart_capability_from_state(state) is None


def test_non_cart_intent_does_not_become_cart():
    state = {
        "intent": "product_search",
        "entities": {
            "cart_action": "add_item",
        },
    }

    assert _cart_capability_from_state(state) is None


def test_cart_arguments_preserve_product_and_positive_quantity():
    state = {
        "entities": {
            "product_name": "Maggi",
            "quantity": 3,
            "product_id": 17,
        },
        "cart_id": 4,
    }

    args = _build_cart_arguments(state)

    assert args["product_name"] == "Maggi"
    assert args["quantity"] == 3
    assert args["product_id"] == 17
    assert args["cart_id"] == 4


def test_cart_arguments_do_not_preserve_invalid_quantity():
    state = {
        "entities": {
            "product_name": "Maggi",
            "quantity": 0,
        }
    }

    args = _build_cart_arguments(state)

    assert args["product_name"] == "Maggi"
    assert "quantity" not in args


def test_cart_arguments_do_not_invent_product_id():
    state = {
        "entities": {
            "product_name": "Maggi",
        }
    }

    args = _build_cart_arguments(state)

    assert args["product_name"] == "Maggi"
    assert "product_id" not in args


def test_normalize_action():
    assert _normalize_action("Add To Cart") == "add_to_cart"
    assert _normalize_action("ADD-TO-CART") == "add_to_cart"
    assert _normalize_action("") is None
    assert _normalize_action(None) is None


def test_deterministic_cart_fallback_for_add():
    state = {
        "intent": "cart",
        "entities": {
            "cart_action": "add_item",
            "product_name": "Maggi",
            "quantity": 2,
        },
    }

    # The current deterministic fallback must be extended to support
    # Cart before relying on this test. This assertion documents the
    # required contract.
    plan = _deterministic_plan_fallback(state)

    assert plan["action"] == "add_to_cart"
    assert plan["arguments"]["product_name"] == "Maggi"
    assert plan["arguments"]["quantity"] == 2


def test_deterministic_cart_fallback_for_show():
    state = {
        "intent": "cart",
        "entities": {
            "cart_action": "show_cart",
        },
    }

    plan = _deterministic_plan_fallback(state)

    assert plan["action"] == "show_cart"
    assert plan["arguments"] == {}