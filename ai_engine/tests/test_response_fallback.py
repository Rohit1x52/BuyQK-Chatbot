"""
Step 6 — Response LLM Fallback Tests

Verify:

    Response LLM
        success -> generated response

        failure
          -> deterministic response

The tests mock the Response Node LLM so they do not depend on Groq
availability, network state, or rate limits.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from ai_engine.graph.state import GraphState
from ai_engine.nodes import response_node as response_module
from ai_engine.nodes.response_node import (
    _generate_llm_response,
    _generate_tool_response,
)


class FakeLLM:
    def __init__(self, response: object = "Generated response.") -> None:
        self.response = response
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        return self.response


class FailingLLM:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        raise self.error


class EmptyLLM:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        return ""


def test_llm_success_returns_generated_response() -> None:
    fake_llm = FakeLLM("Your response was generated successfully.")

    state: GraphState = {
        "message": "Hello",
        "intent": "general",
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_llm_response(state)

    assert response == "Your response was generated successfully."
    assert fake_llm.calls == 1


def test_llm_failure_uses_deterministic_general_fallback() -> None:
    fake_llm = FailingLLM(
        RuntimeError("429 rate limit exceeded")
    )

    state: GraphState = {
        "message": "Hello",
        "intent": "general",
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_llm_response(state)

    assert response
    assert "BuyQK AI" in response
    assert fake_llm.calls == 1


def test_empty_llm_response_uses_deterministic_fallback() -> None:
    fake_llm = EmptyLLM()

    state: GraphState = {
        "message": "Hello",
        "intent": "general",
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_llm_response(state)

    assert response
    assert "BuyQK AI" in response
    assert fake_llm.calls == 1


def test_tool_response_llm_success_is_used() -> None:
    fake_llm = FakeLLM(
        "Two packets of Amul Milk were added to your cart."
    )

    state: GraphState = {
        "message": "Add two Amul Milk",
        "intent": "cart",
        "tool_name": "add_to_cart",
        "tool_result": {
            "success": True,
            "tool": "add_to_cart",
            "type": "cart_add",
            "product_name": "Amul Milk",
            "quantity": 2,
        },
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_tool_response(state)

    assert response == (
        "Two packets of Amul Milk were added to your cart."
    )
    assert fake_llm.calls == 1


def test_tool_response_llm_failure_uses_deterministic_fallback() -> None:
    fake_llm = FailingLLM(
        RuntimeError("429 rate limit exceeded")
    )

    state: GraphState = {
        "message": "Add two Amul Milk",
        "intent": "cart",
        "tool_name": "add_to_cart",
        "tool_result": {
            "success": True,
            "tool": "add_to_cart",
            "type": "cart_add",
            "product_name": "Amul Milk",
            "quantity": 2,
        },
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_tool_response(state)

    assert response
    assert "Amul Milk" in response
    assert "added to your cart" in response
    assert fake_llm.calls == 1


def test_tool_response_failure_preserves_canonical_error_handling() -> None:
    fake_llm = FailingLLM(
        RuntimeError("429 rate limit exceeded")
    )

    state: GraphState = {
        "message": "Find missing product",
        "intent": "product_search",
        "tool_name": "search_products",
        "tool_result": {
            "success": False,
            "tool": "search_products",
            "type": "product_search",
            "error_code": "not_found",
            "error": "Internal backend details must not leak.",
        },
        "entities": {},
        "conversation_history": [],
    }

    with patch.object(response_module, "llm", fake_llm):
        response = _generate_tool_response(state)

    assert response == (
        "I couldn't find the requested resource."
    )
    assert "Internal backend details" not in response
    assert fake_llm.calls == 1
