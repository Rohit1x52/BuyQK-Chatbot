import pytest

from ai_engine.graph.state import GraphState
from ai_engine.nodes import entity_node as entity_module
from ai_engine.nodes import planner_node as planner_module
from ai_engine.nodes import policy_node as policy_module
from ai_engine.nodes import tool_node as tool_module
from ai_engine.nodes import response_node as response_module
from ai_engine.tools.results import ToolResult
from backend.services import order_service


class FakeOrder:
    def __init__(self, order_id, user_id=7, status="processing"):
        self.id = order_id
        self.user_id = user_id
        self.status = status
        self.payment_status = "pending"


# =========================================================
# 8B.1 - Order reference continuity
# =========================================================

@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Cancel order 123", 123),
        ("Cancel my order 123", 123),
        ("Please cancel order #123", 123),
    ],
)
def test_cancellation_order_id_extraction(message, expected):
    assert entity_module.detect_order_id(message) == expected


def test_cancellation_without_order_id_reports_missing_reference(monkeypatch):
    monkeypatch.setattr(
        entity_module,
        "extract_entities",
        lambda message, conversation_history=None: entity_module.LLMEntityOutput(),
    )

    state: GraphState = {
        "message": "Cancel my order",
        "intent": "order_cancel",
        "entities": {},
        "conversation_history": [],
    }

    result = entity_module.entity_node(state)

    assert result["intent"] == "order_cancel"
    assert "order_id" in result["missing_fields"]


def test_latest_and_previous_cancellation_references_are_preserved():
    latest = entity_module.detect_order_reference_type("Cancel my latest order")
    previous = entity_module.detect_order_reference_type("Cancel my previous order")

    assert latest == "latest"
    assert previous == "previous"


# =========================================================
# 8B.3 - Cancellation reason extraction
# =========================================================

def test_explicit_cancellation_reason_is_extracted():
    assert entity_module.detect_cancellation_reason(
        "Cancel my order 42 because I ordered by mistake"
    ) == "I ordered by mistake"

    assert entity_module.detect_cancellation_reason(
        "Cancellation reason: wrong address"
    ) == "wrong address"


def test_cancellation_reason_is_not_invented():
    assert entity_module.detect_cancellation_reason("Cancel my order 42") is None


def test_reason_reply_continues_pending_cancellation(monkeypatch):
    monkeypatch.setattr(
        entity_module,
        "extract_entities",
        lambda message, conversation_history=None: entity_module.LLMEntityOutput(),
    )

    state: GraphState = {
        "message": "I ordered by mistake",
        "intent": "general",
        "entities": {"order_id": 42},
        "conversation_history": [],
        "order_id": 42,
        "awaiting_cancellation_reason": True,
        "cancellation_eligibility": {
            "eligible": True,
            "order_id": 42,
        },
    }

    result = entity_module.entity_node(state)

    assert result["intent"] == "order_cancel"
    assert result["cancellation_reason"] == "I ordered by mistake"
    assert result["entities"]["cancellation_reason"] == "I ordered by mistake"


# =========================================================
# 8B.4 - Planner / Policy
# =========================================================

def test_planner_cancellation_requires_order_reference():
    state = {
        "intent": "order_cancel",
        "entities": {},
        "missing_fields": ["order_id"],
    }

    plan = planner_module._deterministic_plan_fallback(state)

    assert plan["action"] == "ask_clarification"
    assert plan["missing_fields"] == ["order_id"]


def test_planner_preserves_cancellation_reason_and_reference():
    state = {
        "intent": "order_cancel",
        "entities": {
            "order_id": 42,
            "cancellation_reason": "wrong address",
        },
        "missing_fields": [],
    }

    plan = planner_module._deterministic_plan_fallback(state)

    assert plan["action"] == "cancel_order"
    assert plan["arguments"]["order_id"] == 42
    assert plan["arguments"]["cancellation_reason"] == "wrong address"


def test_policy_rejects_cancellation_without_reference():
    state = {
        "planner_decision": {
            "action": "cancel_order",
            "tool": "cancel_order",
        },
        "planned_arguments": {},
        "order_id": None,
        "order_reference": None,
        "order_reference_type": None,
    }

    result = policy_module.policy_node(state)

    assert result["policy_allowed"] is False
    assert result["policy_reason"] == "missing_order_reference"


def test_policy_allows_initial_cancellation_without_reason():
    state = {
        "planner_decision": {
            "action": "cancel_order",
            "tool": "cancel_order",
        },
        "planned_arguments": {"order_id": 42},
        "order_id": 42,
        "cancellation_eligibility": None,
    }

    result = policy_module.policy_node(state)

    assert result["policy_allowed"] is True
    assert result["tool_name"] == "cancel_order"


def test_policy_requires_reason_after_backend_eligibility():
    state = {
        "planner_decision": {
            "action": "cancel_order",
            "tool": "cancel_order",
        },
        "planned_arguments": {"order_id": 42},
        "order_id": 42,
        "cancellation_eligibility": {
            "eligible": True,
            "order_id": 42,
        },
        "cancellation_reason": None,
    }

    result = policy_module.policy_node(state)

    assert result["policy_allowed"] is False
    assert result["policy_reason"] == "missing_cancellation_reason"


# =========================================================
# 8B.2 - Backend eligibility
# =========================================================

def test_backend_cancellation_eligibility_is_authoritative(monkeypatch):
    order = FakeOrder(42, user_id=7, status="processing")
    monkeypatch.setattr(order_service, "get_order", lambda db, order_id: order)

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=42,
        user_id=7,
    )

    assert result["eligible"] is True
    assert result["order_id"] == 42


def test_backend_rejects_delivered_order(monkeypatch):
    order = FakeOrder(42, user_id=7, status="delivered")
    monkeypatch.setattr(order_service, "get_order", lambda db, order_id: order)

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=42,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "not_cancellable_status"


def test_backend_rejects_other_users_order(monkeypatch):
    order = FakeOrder(42, user_id=99, status="processing")
    monkeypatch.setattr(order_service, "get_order", lambda db, order_id: order)

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=42,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "unauthorized"


# =========================================================
# 8B.4 / 8B.5 - Tool workflow
# =========================================================

def test_tool_checks_eligibility_before_cancellation(monkeypatch):
    calls = []

    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: calls.append(("eligibility", order_id, user_id)) or {
            "eligible": True,
            "order_id": order_id,
        },
    )
    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda db, order_id, user_id: calls.append(("cancel", order_id, user_id)) or FakeOrder(order_id, user_id, "cancelled"),
    )

    state = {
        "tool_name": "cancel_order",
        "user_id": 7,
        "entities": {"order_id": 42},
        "order_id": 42,
    }

    result = tool_module.tool_node(state, db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.data["type"] == "cancellation_eligibility"
    assert tool_result.data["needs_reason"] is True
    assert calls == [("eligibility", 42, 7)]


def test_tool_requires_reason_after_eligibility(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {"eligible": True, "order_id": order_id},
    )
    cancel_calls = []
    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    state = {
        "tool_name": "cancel_order",
        "user_id": 7,
        "entities": {"order_id": 42},
        "order_id": 42,
    }

    result = tool_module.tool_node(state, db=object())

    assert result["awaiting_cancellation_reason"] is True
    assert result["cancellation_eligibility"]["eligible"] is True
    assert cancel_calls == []


def test_tool_cancellation_calls_backend_with_authenticated_user_and_returns_refund(monkeypatch):
    order = FakeOrder(42, user_id=7, status="cancelled")

    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {"eligible": True, "order_id": order_id, "status": "processing"},
    )
    calls = []
    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda db, order_id, user_id: calls.append((order_id, user_id)) or order,
    )
    monkeypatch.setattr(
        tool_module,
        "get_refund_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "refunded",
            "payment_status": "refunded",
        },
    )

    state = {
        "tool_name": "cancel_order",
        "user_id": 7,
        "entities": {
            "order_id": 42,
            "cancellation_reason": "wrong address",
        },
        "order_id": 42,
        "cancellation_reason": "wrong address",
    }

    result = tool_module.tool_node(state, db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.tool == "cancel_order"
    assert tool_result.data["type"] == "order_cancelled"
    assert tool_result.data["order_id"] == 42
    assert tool_result.data["cancellation_reason"] == "wrong address"
    assert tool_result.data["refund_eligibility"]["status"] == "refunded"
    assert calls == [(42, 7)]


def test_tool_rejects_ineligible_order_without_cancelling(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": False,
            "order_id": order_id,
            "reason_code": "not_cancellable_status",
        },
    )
    cancel_calls = []
    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    state = {
        "tool_name": "cancel_order",
        "user_id": 7,
        "entities": {"order_id": 42},
        "order_id": 42,
    }

    result = tool_module.tool_node(state, db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert tool_result.error.code == "order_cancellation"
    assert (
        tool_result.error.message
        == "This order is not eligible for cancellation."
    )
    assert cancel_calls == []


# =========================================================
# 8B.5 - Response confirmation gate
# =========================================================

def test_response_never_confirms_from_eligibility_only():
    text = response_module._tool_fallback({
        "success": True,
        "type": "cancellation_eligibility",
        "order_id": 42,
        "eligible": True,
        "needs_reason": True,
    })

    assert "cancelled" not in text.lower()
    assert "reason" in text.lower()


def test_response_confirms_only_successful_cancellation_and_uses_backend_refund_data():
    text = response_module._tool_fallback({
        "success": True,
        "type": "order_cancelled",
        "order_id": 42,
        "status": "cancelled",
        "cancellation_reason": "wrong address",
        "refund_eligibility": {
            "eligible": True,
            "status": "refunded",
            "payment_status": "refunded",
        },
    })

    assert "Order #42 has been cancelled." in text
    assert "Refund status: refunded." in text
    assert "eta" not in text.lower()
    assert "amount" not in text.lower()


def test_response_does_not_confirm_failed_cancellation():
    text = response_module._tool_fallback({
        "success": False,
        "type": "order_cancellation",
        "error": "This order is not eligible for cancellation.",
    })

    assert "cancelled" not in text.lower()
