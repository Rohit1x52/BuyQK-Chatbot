import pytest

from ai_engine.graph.state import GraphState
from ai_engine.nodes import entity_node as entity_module
from ai_engine.nodes import planner_node as planner_module
from ai_engine.nodes import policy_node as policy_module
from ai_engine.nodes import tool_node as tool_module
from ai_engine.tools.results import ToolResult


# =========================================================
# 8A.1 - Order reference extraction
# =========================================================

@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Track order 123", 123),
        ("Track my order 123", 123),
        ("Order 123 status?", 123),
        ("order id: 123", 123),
        ("order #123", 123),
    ],
)
def test_explicit_order_id_extraction(message, expected):
    assert entity_module.detect_order_id(message) == expected


def test_order_id_detector_does_not_confuse_purchase_quantity():
    assert entity_module.detect_order_id("I want to order 11 Maggi") is None


def test_bqk_reference_is_preserved_without_invention():
    assert entity_module.detect_order_reference("Track BQK12345") == "BQK12345"


def test_latest_and_previous_reference_detection():
    assert entity_module.detect_order_reference_type("Track my latest order") == "latest"
    assert entity_module.detect_order_reference_type("Track my previous order") == "previous"
    assert entity_module.detect_order_reference_type("Show my most recent order") == "latest"
    assert entity_module.detect_order_reference_type("Track my pichla order") == "previous"


# =========================================================
# 8A.2 - Conversational continuity
# =========================================================

def test_tracking_without_order_id_waits_for_order_id(monkeypatch):
    monkeypatch.setattr(
        entity_module,
        "extract_entities",
        lambda message, conversation_history=None: entity_module.LLMEntityOutput(),
    )

    state: GraphState = {
        "message": "Track my order",
        "intent": "order_tracking",
        "entities": {},
        "conversation_history": [],
        "awaiting_order_tracking_order_id": False,
    }

    result = entity_module.entity_node(state)

    assert result["intent"] == "order_tracking"
    assert "order_id" in result["missing_fields"]
    assert result["awaiting_order_tracking_order_id"] is True


def test_numeric_reply_continues_tracking_prompt(monkeypatch):
    monkeypatch.setattr(
        entity_module,
        "extract_entities",
        lambda message, conversation_history=None: entity_module.LLMEntityOutput(),
    )

    state: GraphState = {
        "message": "42",
        "intent": "general",
        "entities": {},
        "conversation_history": [],
        "awaiting_order_tracking_order_id": True,
    }

    result = entity_module.entity_node(state)

    assert result["intent"] == "order_tracking"
    assert result["order_id"] == 42
    assert result["entities"]["order_id"] == 42
    assert result["entities"]["order_reference_type"] == "specific"
    assert result["missing_fields"] == []
    assert result["awaiting_order_tracking_order_id"] is False


# =========================================================
# 8A.3 - Planner / Policy reference handling
# =========================================================

def test_planner_preserves_latest_tracking_reference():
    state = {
        "intent": "order_tracking",
        "entities": {"order_reference_type": "latest"},
        "missing_fields": [],
    }

    plan = planner_module._deterministic_plan_fallback(state)

    assert plan["action"] == "track_order"
    assert plan["tool_name"] == "track_order"
    assert plan["arguments"]["order_reference_type"] == "latest"
    assert plan["missing_fields"] == []


def test_policy_allows_latest_tracking_reference():
    state = {
        "planner_decision": {
            "action": "track_order",
            "tool": "track_order",
        },
        "planned_arguments": {
            "order_reference_type": "latest",
        },
        "order_reference_type": "latest",
    }

    result = policy_module.policy_node(state)

    assert result["policy_allowed"] is True
    assert result["tool_name"] == "track_order"


def test_policy_rejects_tracking_without_reference():
    state = {
        "planner_decision": {
            "action": "track_order",
            "tool": "track_order",
        },
        "planned_arguments": {},
        "order_id": None,
        "order_reference": None,
        "order_reference_type": None,
    }

    result = policy_module.policy_node(state)

    assert result["policy_allowed"] is False
    assert result["policy_reason"] == "missing_order_reference"


# =========================================================
# 8A.4 - Backend-authoritative latest/previous tracking
# =========================================================

class FakeOrder:
    def __init__(self, order_id, user_id=7, status="processing", payment_status="pending"):
        self.id = order_id
        self.user_id = user_id
        self.status = status
        self.payment_status = payment_status
        self.total_amount = None


def _tracking_state(reference_type):
    return {
        "tool_name": "track_order",
        "user_id": 7,
        "entities": {
            "order_reference_type": reference_type,
        },
        "order_reference_type": reference_type,
    }


def test_latest_order_is_resolved_by_backend(monkeypatch):
    latest = FakeOrder(200, status="shipped")
    previous = FakeOrder(199, status="processing")

    monkeypatch.setattr(
        tool_module,
        "get_user_orders",
        lambda db, user_id, limit=20: [latest, previous],
    )
    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: latest if order_id == 200 else previous,
    )
    monkeypatch.setattr(tool_module, "build_order_bill", lambda db, order: None)

    result = tool_module.tool_node(_tracking_state("latest"), db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.tool == "track_order"
    assert tool_result.data["type"] == "order_tracking"
    assert tool_result.data["order_id"] == 200
    assert tool_result.data["status"] == "shipped"


def test_previous_order_is_resolved_by_backend(monkeypatch):
    latest = FakeOrder(200, status="shipped")
    previous = FakeOrder(199, status="delivered")

    monkeypatch.setattr(
        tool_module,
        "get_user_orders",
        lambda db, user_id, limit=20: [latest, previous],
    )
    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: latest if order_id == 200 else previous,
    )
    monkeypatch.setattr(tool_module, "build_order_bill", lambda db, order: None)

    result = tool_module.tool_node(_tracking_state("previous"), db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.data["type"] == "order_tracking"
    assert tool_result.data["order_id"] == 199
    assert tool_result.data["status"] == "delivered"


def test_tracking_enforces_user_ownership(monkeypatch):
    other_user_order = FakeOrder(300, user_id=99, status="shipped")

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: other_user_order,
    )

    state = {
        "tool_name": "track_order",
        "user_id": 7,
        "entities": {"order_id": 300, "order_reference_type": "specific"},
        "order_id": 300,
    }

    result = tool_module.tool_node(state, db=object())
    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.error is not None


def test_tracking_result_contains_no_ai_invented_tracking_fields(monkeypatch):
    order = FakeOrder(400, status="delivered")

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: order,
    )
    monkeypatch.setattr(tool_module, "build_order_bill", lambda db, order: None)

    state = {
        "tool_name": "track_order",
        "user_id": 7,
        "entities": {"order_id": 400, "order_reference_type": "specific"},
        "order_id": 400,
    }

    result = tool_module.tool_node(state, db=object())
    data = result["tool_result"].data

    assert data["type"] == "order_tracking"
    assert data["order_id"] == 400
    assert data["status"] == "delivered"
    assert "eta" not in data
    assert "courier" not in data
    assert "tracking_url" not in data
    assert "location" not in data
