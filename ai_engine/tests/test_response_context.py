"""
Step 4 — Context-Aware Response Tests

Tests that the Response Node uses information already known in
GraphState instead of asking the user for it again.

Conversation progression covered here:

    product_name known
        +
    quantity missing
        -> ask only for quantity

    product_name + quantity known
        +
    size missing
        -> ask only for size

    product_name + quantity + size known
        +
    no missing fields
        -> do not ask a missing-field question
"""

from __future__ import annotations

from typing import Any

from ai_engine.nodes.response_node import (
    _context_aware_missing_field_fallback,
    _context_aware_response_context,
    _context_value,
)


# =========================================================
# Helpers
# =========================================================

def assert_contains(
    text: str,
    expected: str,
) -> None:
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


# =========================================================
# _context_value
# =========================================================

def test_context_value_reads_direct_graph_state_first() -> None:
    state: dict[str, Any] = {
        "product_name": "Tata Tea",
        "entities": {
            "product_name": "Amul Milk",
        },
    }

    value = _context_value(
        state,
        "product_name",
    )

    assert value == "Tata Tea"


def test_context_value_falls_back_to_entities() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    value = _context_value(
        state,
        "product_name",
    )

    assert value == "Tata Tea"


def test_context_value_returns_none_for_unknown_field() -> None:
    state: dict[str, Any] = {
        "entities": {},
    }

    value = _context_value(
        state,
        "quantity",
    )

    assert value is None


def test_context_value_does_not_treat_empty_string_as_known() -> None:
    state: dict[str, Any] = {
        "product_name": "",
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    value = _context_value(
        state,
        "product_name",
    )

    assert value == "Tata Tea"


# =========================================================
# Product already known
# =========================================================

def test_known_product_does_not_ask_for_product_again() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "Tata Tea",
    )

    assert_contains(
        response,
        "how many",
    )

    assert_not_contains(
        response,
        "which product",
    )


def test_known_product_is_used_when_quantity_is_missing() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "missing_fields": [
            "quantity",
        ],
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "Tata Tea",
    )

    assert_contains(
        response,
        "quantity",
    )


# =========================================================
# Quantity already known
# =========================================================

def test_known_quantity_and_product_ask_only_for_size() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
        "missing_fields": [
            "size",
        ],
    }

    response = _context_aware_missing_field_fallback(
        state,
        "size",
    )

    assert_contains(
        response,
        "Tata Tea",
    )

    assert_contains(
        response,
        "size",
    )

    assert_not_contains(
        response,
        "how many",
    )

    assert_not_contains(
        response,
        "which product",
    )


def test_variant_size_is_treated_as_size_information() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "variant_size",
    )

    assert_contains(
        response,
        "size",
    )

    assert_contains(
        response,
        "Tata Tea",
    )


def test_product_size_is_treated_as_size_information() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "product_size",
    )

    assert_contains(
        response,
        "size",
    )

    assert_contains(
        response,
        "Tata Tea",
    )


# =========================================================
# Complete product context
# =========================================================

def test_complete_product_context_has_no_missing_field_question() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
        "size": "500g",
        "missing_fields": [],
    }

    context = _context_aware_response_context(
        state,
        [],
        None,
    )

    assert context["missing_fields"] == []
    assert context["next_missing"] is None

    known_fields = context["known_fields"]

    assert known_fields["product_name"] == "Tata Tea"
    assert known_fields["quantity"] == 3
    assert known_fields["size"] == "500g"


def test_context_contains_known_product_and_quantity() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
    }

    context = _context_aware_response_context(
        state,
        ["size"],
        "size",
    )

    assert context["known_fields"]["product_name"] == "Tata Tea"
    assert context["known_fields"]["quantity"] == 3
    assert context["missing_fields"] == ["size"]
    assert context["next_missing"] == "size"


def test_context_preserves_entities() -> None:
    entities = {
        "product_name": "Tata Tea",
        "brand": "Tata",
    }

    state: dict[str, Any] = {
        "entities": entities,
    }

    context = _context_aware_response_context(
        state,
        ["quantity"],
        "quantity",
    )

    assert context["entities"] == entities


def test_context_preserves_current_message() -> None:
    state: dict[str, Any] = {
        "message": "I need three packets",
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    context = _context_aware_response_context(
        state,
        ["size"],
        "size",
    )

    assert context["current_message"] == "I need three packets"


# =========================================================
# Missing-field ordering
# =========================================================

def test_quantity_is_asked_when_quantity_is_next_missing() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "missing_fields": [
            "quantity",
            "size",
        ],
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "how many",
    )

    assert_contains(
        response,
        "Tata Tea",
    )

    assert_not_contains(
        response,
        "size",
    )


def test_size_is_asked_when_size_is_next_missing() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
        "missing_fields": [
            "size",
        ],
    }

    response = _context_aware_missing_field_fallback(
        state,
        "size",
    )

    assert_contains(
        response,
        "which size",
    )

    assert_not_contains(
        response,
        "how many",
    )


# =========================================================
# Other canonical fields
# =========================================================

def test_address_selection_response_is_context_safe() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "address_selection",
    )

    assert_contains(
        response,
        "delivery address",
    )


def test_payment_method_response_is_context_safe() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "payment_method",
    )

    assert_contains(
        response,
        "payment method",
    )


# =========================================================
# No product known
# =========================================================

def test_quantity_question_without_product_does_not_invent_product() -> None:
    state: dict[str, Any] = {
        "entities": {},
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "how many",
    )

    assert_not_contains(
        response,
        "Tata Tea",
    )

    assert_not_contains(
        response,
        "Amul",
    )


def test_size_question_without_product_does_not_invent_product() -> None:
    state: dict[str, Any] = {
        "entities": {},
    }

    response = _context_aware_missing_field_fallback(
        state,
        "size",
    )

    assert_contains(
        response,
        "which size",
    )

    assert_not_contains(
        response,
        "Tata Tea",
    )

    assert_not_contains(
        response,
        "Amul",
    )


# =========================================================
# Malformed / defensive state
# =========================================================

def test_context_handles_missing_entities() -> None:
    state: dict[str, Any] = {}

    context = _context_aware_response_context(
        state,
        ["product_name"],
        "product_name",
    )

    assert context["known_fields"] == {}
    assert context["entities"] == {}
    assert context["missing_fields"] == [
        "product_name",
    ]


def test_context_handles_non_dict_entities() -> None:
    state: dict[str, Any] = {
        "entities": "invalid",
    }

    context = _context_aware_response_context(
        state,
        ["product_name"],
        "product_name",
    )

    assert context["entities"] == {}
    assert context["known_fields"] == {}


def test_empty_product_name_is_not_presented_as_known() -> None:
    state: dict[str, Any] = {
        "entities": {
            "product_name": "   ",
        },
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "how many",
    )

    assert_not_contains(
        response,
        "   ",
    )


# =========================================================
# Direct GraphState fields
# =========================================================

def test_direct_product_name_is_used_even_without_entities() -> None:
    state: dict[str, Any] = {
        "product_name": "Tata Tea",
        "entities": {},
    }

    response = _context_aware_missing_field_fallback(
        state,
        "quantity",
    )

    assert_contains(
        response,
        "Tata Tea",
    )

    assert_contains(
        response,
        "how many",
    )


def test_direct_quantity_is_exposed_in_context() -> None:
    state: dict[str, Any] = {
        "product_name": "Tata Tea",
        "quantity": 3,
        "entities": {},
    }

    context = _context_aware_response_context(
        state,
        ["size"],
        "size",
    )

    assert context["known_fields"]["product_name"] == "Tata Tea"
    assert context["known_fields"]["quantity"] == 3


# =========================================================
# Context must not override graph sequencing
# =========================================================

def test_next_missing_controls_question_not_known_field_order() -> None:
    state: dict[str, Any] = {
        "product_name": "Tata Tea",
        "quantity": 3,
        "size": "500g",
        "entities": {},
    }

    response = _context_aware_missing_field_fallback(
        state,
        "payment_method",
    )

    assert_contains(
        response,
        "payment method",
    )

    assert_not_contains(
        response,
        "how many",
    )

    assert_not_contains(
        response,
        "which size",
    )


# =========================================================
# Full progression
# =========================================================

def test_conversation_progression_product_to_quantity_to_size() -> None:
    # Turn 1:
    # Product is known; quantity is missing.
    state_turn_1: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "missing_fields": ["quantity"],
    }

    response_1 = _context_aware_missing_field_fallback(
        state_turn_1,
        "quantity",
    )

    assert_contains(response_1, "Tata Tea")
    assert_contains(response_1, "how many")
    assert_not_contains(response_1, "which product")

    # Turn 2:
    # Product and quantity are known; size is missing.
    state_turn_2: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
        "missing_fields": ["size"],
    }

    response_2 = _context_aware_missing_field_fallback(
        state_turn_2,
        "size",
    )

    assert_contains(response_2, "Tata Tea")
    assert_contains(response_2, "size")
    assert_not_contains(response_2, "which product")
    assert_not_contains(response_2, "how many")

    # Turn 3:
    # Product, quantity and size are known.
    state_turn_3: dict[str, Any] = {
        "entities": {
            "product_name": "Tata Tea",
        },
        "quantity": 3,
        "size": "500g",
        "missing_fields": [],
    }

    context_3 = _context_aware_response_context(
        state_turn_3,
        [],
        None,
    )

    assert context_3["missing_fields"] == []
    assert context_3["next_missing"] is None
    assert context_3["known_fields"]["product_name"] == "Tata Tea"
    assert context_3["known_fields"]["quantity"] == 3
    assert context_3["known_fields"]["size"] == "500g"
