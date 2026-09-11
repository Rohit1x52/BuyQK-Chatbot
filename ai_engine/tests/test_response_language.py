"""
Step 5 — Response Language Adaptation Tests

Verify that the Response Node can preserve/adapt to:
- English
- Hindi
- Hinglish

The tests focus on deterministic behavior so they remain stable even
when the response LLM is unavailable or rate-limited.
"""

from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState
from ai_engine.nodes.response_node import (
    _detect_response_language,
    _localized_context_fallback,
)


def assert_contains(text: str, expected: str) -> None:
    assert expected.lower() in text.lower(), (
        f"Expected {expected!r} in response {text!r}"
    )


def test_detect_english_message() -> None:
    state: GraphState = {
        "message": "I need three packets of Tata Tea.",
        "conversation_history": [],
    }

    assert _detect_response_language(state) == "english"


def test_detect_hindi_message() -> None:
    state: GraphState = {
        "message": "Mujhe Tata Tea chahiye.",
        "conversation_history": [],
    }

    assert _detect_response_language(state) == "hindi"


def test_detect_hinglish_message() -> None:
    state: GraphState = {
        "message": "Mujhe Tata Tea chahiye, please.",
        "conversation_history": [],
    }

    assert _detect_response_language(state) == "hinglish"


def test_explicit_response_language_has_priority() -> None:
    state: GraphState = {
        "message": "I need Tata Tea.",
        "response_language": "hindi",
        "conversation_history": [],
    }

    assert _detect_response_language(state) == "hindi"


def test_language_from_conversation_history_for_short_follow_up() -> None:
    state: GraphState = {
        "message": "Three",
        "conversation_history": [
            {"role": "user", "content": "Mujhe Tata Tea chahiye."},
        ],
    }

    assert _detect_response_language(state) == "hindi"


def test_english_quantity_fallback() -> None:
    state: GraphState = {
        "message": "I need Tata Tea.",
        "entities": {"product_name": "Tata Tea"},
    }

    response = _localized_context_fallback(
        state,
        "quantity",
    )

    assert_contains(response, "Tata Tea")
    assert_contains(response, "quantity")


def test_hindi_quantity_fallback() -> None:
    state: GraphState = {
        "message": "Mujhe Tata Tea chahiye.",
        "entities": {"product_name": "Tata Tea"},
    }

    response = _localized_context_fallback(
        state,
        "quantity",
    )

    assert_contains(response, "Tata Tea")
    assert any(
        word in response.lower()
        for word in ("kitne", "quantity", "packets")
    )


def test_hinglish_quantity_fallback() -> None:
    state: GraphState = {
        "message": "Mujhe Tata Tea chahiye please.",
        "entities": {"product_name": "Tata Tea"},
    }

    response = _localized_context_fallback(
        state,
        "quantity",
    )

    assert_contains(response, "Tata Tea")
    assert any(
        word in response.lower()
        for word in ("kitne", "quantity", "packets")
    )


def test_language_fallback_does_not_invent_product() -> None:
    state: GraphState = {
        "message": "I need tea.",
        "entities": {},
    }

    response = _localized_context_fallback(
        state,
        "quantity",
    )

    assert "Tata Tea" not in response
    assert "Amul Milk" not in response
