# =========================================================
# BuyQK AI - Phase 9 Customer Support E2E Tests
# =========================================================
#
# Covers:
#   - support issue classification fallback
#   - support detail collection
#   - planner support action
#   - policy validation
#   - tool verification / ticket creation
#   - Ticket ID propagation
#   - response safety
#
# Run:
#   pytest ai_engine/tests/test_customer_support_e2e.py -v
# =========================================================

from __future__ import annotations

from types import SimpleNamespace

import ai_engine.nodes.entity_node as entity_module
import ai_engine.nodes.tool_node as tool_module

from ai_engine.graph.state import GraphState
from ai_engine.nodes.decision_node import decision_node
from ai_engine.nodes.planner_node import planner_node
from ai_engine.nodes.policy_node import policy_node
from ai_engine.nodes.response_node import response_node


def test_support_issue_type_fallback():
    assert (
        entity_module._detect_support_issue_type(
            "I received the wrong product"
        )
        == "wrong_product"
    )
    assert (
        entity_module._detect_support_issue_type(
            "Payment failed"
        )
        == "payment_failure"
    )
    assert (
        entity_module._detect_support_issue_type(
            "My order is late"
        )
        == "delivery_delay"
    )
    assert (
        entity_module._detect_support_issue_type(
            "Where is my refund?"
        )
        == "refund_status"
    )
    assert (
        entity_module._detect_support_issue_type(
            "Connect me to support"
        )
        == "human_escalation"
    )


def test_support_missing_fields_wrong_product():
    entities = entity_module.EntityOutput(
        support_issue_type="wrong_product",
    )

    missing = entity_module.get_missing_fields(
        intent="customer_support",
        entities=entities,
    )

    assert "order_id" in missing


def test_support_missing_evidence_after_order_id(monkeypatch):
    monkeypatch.setattr(
        entity_module,
        "resolve_current_turn_intent",
        lambda state, message: entity_module.IntentDecision(
            intent="customer_support",
            order_action="none",
            confidence=1.0,
        ),
    )
    monkeypatch.setattr(
        entity_module,
        "extract_entities",
        lambda message, conversation_history=None: entity_module.LLMEntityOutput(
            order_id=123,
            support_issue_type="wrong_product",
            support_description=message,
        ),
    )

    state: GraphState = {
        "intent": "customer_support",
        "message": "I received the wrong product. Order 123.",
        "entities": {},
    }

    result = entity_module.entity_node(state)

    assert result["entities"]["order_id"] == 123
    assert result["entities"]["support_issue_type"] == "wrong_product"
    assert "support_evidence" in result["missing_fields"]


def test_support_payment_reference_requirement():
    state: GraphState = {
        "intent": "customer_support",
        "message": "Payment failed",
        "entities": {
            "support_issue_type": "payment_failure",
        },
    }

    result = entity_module.entity_node(state)

    assert "payment_reference" in result.get("missing_fields", [])


def test_support_policy_and_decision_route():
    state: GraphState = {
        "intent": "customer_support",
        "user_id": 1,
        "entities": {
            "support_issue_type": "human_escalation",
            "support_description": "Connect me to support.",
        },
        "planner": {
            "action": "request_support",
            "tool_name": "create_support_ticket",
            "arguments": {
                "support_issue_type": "human_escalation",
                "support_description": "Connect me to support.",
            },
        },
        "planner_args": {
            "support_issue_type": "human_escalation",
            "support_description": "Connect me to support.",
        },
    }

    policy_result = policy_node(state)
    assert policy_result["policy_result"]["allowed"] is True
    assert policy_result["policy_result"]["tool"] == "create_support_ticket"

    state.update(policy_result)

    decision_result = decision_node(state)
    assert decision_result["decision_route"] == "tool"
    assert decision_result["tool_name"] == "create_support_ticket"


def test_support_planner_deterministic_fallback():
    state: GraphState = {
        "intent": "customer_support",
        "message": "Connect me to support",
        "entities": {
            "support_issue_type": "human_escalation",
            "support_description": "Connect me to support",
        },
        "missing_fields": [],
    }

    result = entity_module._fallback_current_turn_intent(
        state,
        state["message"],
    )
    assert result.intent == "customer_support"

    plan = planner_node.__globals__["_deterministic_plan_fallback"](state)
    assert plan["action"] == "request_support"
    assert plan["tool_name"] == "request_support"
    assert plan["arguments"]["support_issue_type"] == "human_escalation"


def test_support_tool_creates_ticket_and_returns_reference(monkeypatch):
    def fake_verify_support_request(**kwargs):
        return {
            "success": True,
            "type": "support_verification",
            "issue_type": "wrong_product",
            "resolved": False,
            "needs_ticket": True,
            "reason": "manual_product_issue_review_required",
            "order_id": 123,
            "verification": {
                "order_verified": True,
                "evidence_received": True,
            },
        }

    fake_ticket = SimpleNamespace(
        id=10231,
        status="open",
    )

    monkeypatch.setattr(
        tool_module,
        "verify_support_request",
        fake_verify_support_request,
    )
    monkeypatch.setattr(
        tool_module,
        "create_ticket",
        lambda **kwargs: fake_ticket,
    )

    state: GraphState = {
        "tool_name": "create_support_ticket",
        "user_id": 1,
        "message": "Wrong product for order 123.",
        "entities": {
            "support_issue_type": "wrong_product",
            "support_description": "Wrong product for order 123.",
            "order_id": 123,
            "support_evidence_url": "https://example.com/evidence.jpg",
        },
        "planner_args": {},
    }

    result = tool_module.tool_node(
        state,
        db=object(),
    )

    tool_result = result["tool_result"]
    assert tool_result["success"] is True
    assert tool_result["data"]["type"] == "support_ticket"
    assert tool_result["data"]["ticket_id"] == 10231
    assert tool_result["data"]["ticket_reference"] == "SUP10231"
    assert result["support_ticket_id"] == 10231
    assert result["support_ticket_reference"] == "SUP10231"


def test_support_payment_verification_can_resolve_without_ticket(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "verify_support_request",
        lambda **kwargs: {
            "success": True,
            "type": "support_verification",
            "issue_type": "payment_failure",
            "resolved": True,
            "needs_ticket": False,
            "reason": "payment_failure_confirmed",
            "order_id": 10,
            "verification": {
                "payment_found": True,
                "payment_status": "failed",
            },
        },
    )

    state: GraphState = {
        "tool_name": "create_support_ticket",
        "user_id": 1,
        "message": "Payment failed for order 10.",
        "entities": {
            "support_issue_type": "payment_failure",
            "support_description": "Payment failed for order 10.",
            "order_id": 10,
        },
        "planner_args": {},
    }

    result = tool_module.tool_node(
        state,
        db=object(),
    )

    tool_result = result["tool_result"]
    assert tool_result["success"] is True
    assert tool_result["data"]["type"] == "support_verification"
    assert tool_result["data"]["resolved"] is True
    assert result["support_ticket_id"] is None


def test_response_must_show_ticket_id():
    state: GraphState = {
        "intent": "customer_support",
        "tool_name": "create_support_ticket",
        "missing_fields": [],
        "tool_result": {
            "success": True,
            "type": "support_ticket",
            "issue_type": "wrong_product",
            "ticket_id": 10231,
            "ticket_reference": "SUP10231",
            "status": "open",
            "human_escalation": True,
        },
    }

    result = response_node(state)
    response = result["response"]

    assert "SUP10231" in response
    assert result["metadata"]["ticket_reference"] == "SUP10231"


def test_failed_ticket_creation_cannot_claim_success():
    state: GraphState = {
        "intent": "customer_support",
        "tool_name": "create_support_ticket",
        "missing_fields": [],
        "tool_result": {
            "success": False,
            "type": "support_ticket",
            "error": "Support service is temporarily unavailable.",
            "error_code": "backend_error",
        },
    }

    result = response_node(state)
    response = result["response"].lower()

    assert "ticket id" not in response
    assert "successfully created" not in response


if __name__ == "__main__":
    import pytest

    raise SystemExit(
        pytest.main([__file__, "-v"])
    )
