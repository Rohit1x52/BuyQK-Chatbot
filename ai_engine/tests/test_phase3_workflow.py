"""
BuyQK AI - Phase 3 Workflow Manager Tests

These tests isolate the Phase 3 workflow/follow-up layer.

They do NOT call the real LLM and do NOT touch:
- CartService
- OrderService
- database
- backend APIs

Run from the project root:

    python -m pytest ai_engine/tests/test_phase3_workflow.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from ai_engine.nodes import workflow_node as workflow_module
from ai_engine.nodes import followup_node as followup_module


# ============================================================
# Fake LLM
# ============================================================

@dataclass
class FakeLLMResponse:
    content: str


class FakeLLM:
    """Small deterministic LLM stub for unit tests."""

    def __init__(self, payload: str):
        self.payload = payload
        self.calls = 0

    def invoke(
        self,
        messages: Any,
    ) -> FakeLLMResponse:
        self.calls += 1

        return FakeLLMResponse(
            self.payload
        )


# ============================================================
# Test State
# ============================================================

def make_state(
    **overrides: Any,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "message": "",
        "conversation_history": [],

        "active_task": None,
        "task_status": "idle",
        "workflow_goal": None,
        "workflow_transition": None,
        "workflow_context": {},
        "workflow_history": [],

        "intent": "general",
        "user_goal": None,
        "detected_language": "en",
        "references": {},

        "entities": {},
        "order_items": [],

        "missing_fields": [],
        "current_missing_field": None,
        "follow_up_question": None,
        "awaiting_user_input": False,

        "checkout_id": None,
        "checkout_status": None,

        "order_created": False,
        "order_id": None,

        "cart_status": None,
        "cart_items": [],

        "transaction_error": None,
    }

    state.update(overrides)

    return state


# ============================================================
# LLM Patching Helpers
# ============================================================

def patch_workflow_llm(
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
) -> FakeLLM:
    fake = FakeLLM(payload)

    monkeypatch.setattr(
        workflow_module,
        "get_llm",
        lambda: fake,
    )

    return fake


def patch_followup_llm(
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
) -> FakeLLM:
    fake = FakeLLM(payload)

    monkeypatch.setattr(
        followup_module,
        "get_llm",
        lambda: fake,
    )

    return fake


# ============================================================
# 1. Continue Existing Workflow
# ============================================================

def test_workflow_continues_when_user_provides_followup_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": "grocery_order",
          "task_status": "collecting_information",
          "workflow_goal": "Purchase Tata Tea",
          "workflow_transition": "continue",
          "reason": "The current message supplies information for the existing order."
        }
        """,
    )

    state = make_state(
        message="Three",

        active_task="grocery_order",
        task_status="collecting_information",

        workflow_goal="Purchase Tata Tea",

        intent="order_create",

        entities={
            "product_name": "Tata Tea"
        },

        missing_fields=[],
        current_missing_field="quantity",

        awaiting_user_input=True,
    )

    result = workflow_module.workflow_node(
        state
    )

    assert fake.calls == 1

    assert result["active_task"] == (
        "grocery_order"
    )

    assert result["task_status"] == (
        "collecting_information"
    )

    assert result["workflow_transition"] == (
        "continue"
    )

    assert result["workflow_goal"] == (
        "Purchase Tata Tea"
    )


# ============================================================
# 2. Switch Workflow
# ============================================================

def test_workflow_switches_when_new_goal_is_established(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": "cart_management",
          "task_status": "active",
          "workflow_goal": "Review the shopping cart",
          "workflow_transition": "switch",
          "reason": "The current request establishes a different goal."
        }
        """,
    )

    state = make_state(
        message="Show me what is currently in my basket",

        active_task="grocery_order",
        task_status="collecting_information",

        workflow_goal="Purchase groceries",

        intent="cart",

        entities={
            "cart_action": "show_cart"
        },

        awaiting_user_input=True,
    )

    result = workflow_module.workflow_node(
        state
    )

    assert fake.calls == 1

    assert result["active_task"] == (
        "cart_management"
    )

    assert result["workflow_transition"] == (
        "switch"
    )

    # The NEW workflow must retain the lifecycle
    # returned for that workflow.
    assert result["task_status"] == (
        "active"
    )

    assert result["workflow_goal"] == (
        "Review the shopping cart"
    )


# ============================================================
# 3. Authoritative Completion
# ============================================================

def test_backend_completion_overrides_optimistic_llm_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": "grocery_order",
          "task_status": "active",
          "workflow_goal": "Purchase groceries",
          "workflow_transition": "continue",
          "reason": "Model output."
        }
        """,
    )

    state = make_state(
        message="Done",

        active_task="grocery_order",
        task_status="executing",

        workflow_goal="Purchase groceries",

        intent="order_create",

        order_created=True,
        order_id=12345,

        checkout_status="completed",
    )

    result = workflow_module.workflow_node(
        state
    )

    assert fake.calls == 1

    assert result["active_task"] == (
        "grocery_order"
    )

    assert result["task_status"] == (
        "completed"
    )

    assert result["workflow_transition"] == (
        "complete"
    )


# ============================================================
# 4. Failed Workflow
# ============================================================

def test_authoritative_transaction_failure_marks_workflow_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": "grocery_order",
          "task_status": "active",
          "workflow_goal": "Purchase groceries",
          "workflow_transition": "continue",
          "reason": "Model output."
        }
        """,
    )

    state = make_state(
        message="Try again",

        active_task="grocery_order",
        task_status="executing",

        workflow_goal="Purchase groceries",

        intent="order_create",

        transaction_error={
            "code": "order_failed",
            "message": "Backend rejected the transaction",
        },
    )

    result = workflow_module.workflow_node(
        state
    )

    assert fake.calls == 1

    assert result["task_status"] == (
        "failed"
    )


# ============================================================
# 5. Idle Workflow
# ============================================================

def test_idle_workflow_does_not_create_fake_task_when_llm_returns_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": null,
          "task_status": "idle",
          "workflow_goal": null,
          "workflow_transition": "idle",
          "reason": "No active task."
        }
        """,
    )

    state = make_state(
        message="Thanks, that's all",

        active_task=None,
        task_status="idle",

        workflow_goal=None,

        intent="general",
    )

    result = workflow_module.workflow_node(
        state
    )

    assert fake.calls == 1

    assert result["active_task"] is None

    assert result["task_status"] == (
        "idle"
    )

    assert result["workflow_transition"] == (
        "idle"
    )


# ============================================================
# 6. New Workflow After Completion
# ============================================================

def test_new_workflow_can_start_after_previous_workflow_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_workflow_llm(
        monkeypatch,
        """
        {
          "active_task": "cart_management",
          "task_status": "active",
          "workflow_goal": "Manage the shopping cart",
          "workflow_transition": "start",
          "reason": "A new goal has been established after completion."
        }
        """,
    )

    state = make_state(
        message="Now show my cart",

        active_task="grocery_order",
        task_status="completed",

        workflow_goal="Purchase groceries",

        intent="cart",

        order_created=True,
        order_id=12345,

        checkout_status="completed",
    )

    result = workflow_module.workflow_node(
        state
    )

    # Backend completion is authoritative.
    assert fake.calls == 1

    assert result["task_status"] == (
        "completed"
    )

    assert result["workflow_transition"] == (
        "complete"
    )


# ============================================================
# 7. Follow-up Selects Exactly One Missing Field
# ============================================================

def test_followup_selects_one_missing_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake = patch_followup_llm(
        monkeypatch,
        "How many would you like?",
    )

    state = make_state(
        message="I want Tata Tea",

        active_task="grocery_order",
        task_status="collecting_information",

        entities={
            "product_name": "Tata Tea"
        },

        missing_fields=[
            "quantity",
            "product_variant",
        ],

        current_missing_field=None,

        awaiting_user_input=False,
    )

    result = followup_module.followup_node(
        state
    )

    assert fake.calls == 1

    assert result["current_missing_field"] == (
        "quantity"
    )

    assert result["next_missing"] == (
        "quantity"
    )

    assert result["awaiting_user_input"] is True

    assert result["follow_up_question"] == (
        "How many would you like?"
    )


# ============================================================
# 8. Address / Payment Are External Checkout Selection
# ============================================================

@pytest.mark.parametrize(
    "missing_field",
    [
        "address_selection",
        "payment_method",
    ],
)
def test_followup_does_not_intercept_external_checkout_selection(
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:

    state = make_state(
        message="Continue",

        active_task="grocery_order",
        task_status="collecting_information",

        missing_fields=[
            missing_field
        ],
    )

    result = followup_module.followup_node(
        state
    )

    assert result["current_missing_field"] is None

    assert result["follow_up_question"] is None

    assert result["awaiting_user_input"] is False

    assert result["next_missing"] == (
        missing_field
    )


# ============================================================
# 9. Workflow LLM Failure
# ============================================================

def test_workflow_llm_failure_uses_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    class BrokenLLM:

        def invoke(
            self,
            messages: Any,
        ) -> Any:
            raise RuntimeError(
                "simulated LLM outage"
            )

    monkeypatch.setattr(
        workflow_module,
        "get_llm",
        lambda: BrokenLLM(),
    )

    state = make_state(
        message="Three",

        active_task="grocery_order",
        task_status="collecting_information",

        workflow_goal="Purchase Tata Tea",

        intent="order_create",

        # The current turn already supplied the
        # missing information.
        missing_fields=[],

        awaiting_user_input=True,
    )

    result = workflow_module.workflow_node(
        state
    )

    assert result["active_task"] == (
        "grocery_order"
    )

    assert result["workflow_transition"] == (
        "continue"
    )

    # No required information remains.
    # Therefore the safe fallback can proceed.
    assert result["task_status"] == (
        "ready_to_execute"
    )


# ============================================================
# 10. Follow-up LLM Failure
# ============================================================

def test_followup_llm_failure_uses_safe_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    class BrokenLLM:

        def invoke(
            self,
            messages: Any,
        ) -> Any:
            raise RuntimeError(
                "simulated LLM outage"
            )

    monkeypatch.setattr(
        followup_module,
        "get_llm",
        lambda: BrokenLLM(),
    )

    state = make_state(
        message="I want Tata Tea",

        missing_fields=[
            "quantity"
        ],
    )

    result = followup_module.followup_node(
        state
    )

    assert result["current_missing_field"] == (
        "quantity"
    )

    assert result["awaiting_user_input"] is True

    assert result["follow_up_question"]

    assert result["next_missing"] == (
        "quantity"
    )