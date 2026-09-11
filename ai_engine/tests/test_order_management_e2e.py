import pytest

from ai_engine.nodes import tool_node
from ai_engine.nodes import response_node
from ai_engine.tools.results import ToolResult
from backend.services import order_service


class FakeOrder:
    def __init__(self, order_id, user_id, status, payment_status="pending"):
        self.id = order_id
        self.user_id = user_id
        self.status = status
        self.payment_status = payment_status
        self.total_amount = None


def _state(
    tool_name,
    user_id=7,
    order_id=None,
    reason=None,
):
    state = {
        "tool_name": tool_name,
        "user_id": user_id,
        "entities": {},
    }

    if order_id is not None:
        state["order_id"] = order_id
        state["entities"]["order_id"] = order_id

    if reason is not None:
        state["cancellation_reason"] = reason
        state["entities"]["cancellation_reason"] = reason

    return state


# =========================================================
# TRACKING E2E
# =========================================================

def test_tracking_e2e_success_preserves_backend_status(monkeypatch):
    order = FakeOrder(
        order_id=9001,
        user_id=7,
        status="out_for_delivery",
        payment_status="success",
    )

    monkeypatch.setattr(
        tool_node,
        "get_order",
        lambda db, order_id: order,
    )
    monkeypatch.setattr(
        tool_node,
        "build_order_bill",
        lambda db, order: None,
    )

    tool_state = tool_node.tool_node(
        _state("track_order", order_id=9001),
        db=object(),
    )

    result = tool_state["tool_result"]

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.tool == "track_order"
    assert result.data["type"] == "order_tracking"
    assert result.data["order_id"] == 9001
    assert result.data["status"] == "out_for_delivery"
    assert result.data["payment_status"] == "success"

    response_state = dict(tool_state)
    response_state["intent"] = "order_tracking"
    response_state["message"] = "Track order 9001"

    # Use the deterministic presentation fallback so this E2E test
    # does not depend on an external LLM provider.
    response = response_node._tool_fallback(result.to_dict() | result.data)

    assert isinstance(response, str)
    assert "9001" in response
    assert "out_for_delivery" in response


def test_tracking_e2e_wrong_user_is_rejected(monkeypatch):
    order = FakeOrder(
        order_id=9002,
        user_id=99,
        status="shipped",
    )

    monkeypatch.setattr(
        tool_node,
        "get_order",
        lambda db, order_id: order,
    )

    result = tool_node.tool_node(
        _state("track_order", user_id=7, order_id=9002),
        db=object(),
    )["tool_result"]

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error is not None
    assert "authorized" in result.error.message.lower()


def test_tracking_e2e_backend_failure_stops_flow(monkeypatch):
    def failing_get_order(db, order_id):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        tool_node,
        "get_order",
        failing_get_order,
    )

    result = tool_node.tool_node(
        _state("track_order", order_id=9003),
        db=object(),
    )["tool_result"]

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.data is None
    assert result.error is not None


# =========================================================
# CANCELLATION E2E
# =========================================================

def test_cancellation_e2e_collects_reason_before_mutation(monkeypatch):
    monkeypatch.setattr(
        tool_node,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_node,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    result = tool_node.tool_node(
        _state("cancel_order", order_id=9010),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.data["type"] == "cancellation_eligibility"
    assert tool_result.data["needs_reason"] is True
    assert result["awaiting_cancellation_reason"] is True
    assert cancel_calls == []


def test_cancellation_e2e_success_and_backend_refund_result(monkeypatch):
    order = FakeOrder(
        order_id=9011,
        user_id=7,
        status="cancelled",
        payment_status="refunded",
    )

    eligibility = {
        "eligible": True,
        "order_id": 9011,
        "status": "processing",
    }

    refund = {
        "eligible": True,
        "order_id": 9011,
        "status": "refunded",
        "payment_status": "refunded",
        "reason_code": "payment_success",
    }

    monkeypatch.setattr(
        tool_node,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: eligibility,
    )
    monkeypatch.setattr(
        tool_node,
        "cancel_order",
        lambda db, order_id, user_id: order,
    )
    monkeypatch.setattr(
        tool_node,
        "get_refund_eligibility",
        lambda db, order_id, user_id: refund,
    )

    result = tool_node.tool_node(
        _state(
            "cancel_order",
            order_id=9011,
            reason="ordered by mistake",
        ),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.data["type"] == "order_cancelled"
    assert tool_result.data["order_id"] == 9011
    assert tool_result.data["status"] == "cancelled"
    assert tool_result.data["cancellation_reason"] == "ordered by mistake"
    assert tool_result.data["refund_eligibility"] == refund
    assert result["awaiting_cancellation_reason"] is False

    response = response_node._tool_fallback(
        tool_result.to_dict() | tool_result.data
    )

    assert isinstance(response, str)
    assert "9011" in response
    assert "cancel" in response.lower()


def test_cancellation_e2e_ineligible_order_never_mutates(monkeypatch):
    eligibility = {
        "eligible": False,
        "order_id": 9012,
        "status": "delivered",
        "reason_code": "not_cancellable_status",
    }

    monkeypatch.setattr(
        tool_node,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: eligibility,
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_node,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    result = tool_node.tool_node(
        _state(
            "cancel_order",
            order_id=9012,
            reason="changed my mind",
        ),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert cancel_calls == []

    response = response_node._tool_fallback(tool_result.to_dict())

    assert "cancelled" not in response.lower()


def test_cancellation_e2e_backend_failure_cannot_confirm(monkeypatch):
    monkeypatch.setattr(
        tool_node,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )

    def failing_cancel(db, order_id, user_id):
        raise RuntimeError("backend cancellation failure")

    monkeypatch.setattr(
        tool_node,
        "cancel_order",
        failing_cancel,
    )

    result = tool_node.tool_node(
        _state(
            "cancel_order",
            order_id=9013,
            reason="wrong order",
        ),
        db=object(),
    )["tool_result"]

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.data is None
    assert result.error is not None

    response = response_node._tool_fallback(result.to_dict())

    assert "cancelled" not in response.lower()


# =========================================================
# BACKEND ELIGIBILITY E2E
# =========================================================

def test_backend_eligibility_blocks_already_cancelled_order(monkeypatch):
    order = FakeOrder(
        order_id=9020,
        user_id=7,
        status="cancelled",
    )

    monkeypatch.setattr(
        order_service,
        "get_order",
        lambda db, order_id: order,
    )

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=9020,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "already_cancelled"


def test_backend_eligibility_blocks_delivered_order(monkeypatch):
    order = FakeOrder(
        order_id=9021,
        user_id=7,
        status="delivered",
    )

    monkeypatch.setattr(
        order_service,
        "get_order",
        lambda db, order_id: order,
    )

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=9021,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "not_cancellable_status"


def test_backend_eligibility_rejects_other_users_order(monkeypatch):
    order = FakeOrder(
        order_id=9022,
        user_id=99,
        status="processing",
    )

    monkeypatch.setattr(
        order_service,
        "get_order",
        lambda db, order_id: order,
    )

    result = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=9022,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "unauthorized"


# =========================================================
# STATE / CONTRACT INTEGRITY
# =========================================================

def test_e2e_tool_result_contract_is_structured():
    tracking = ToolResult.ok(
        tool="track_order",
        data={
            "type": "order_tracking",
            "order_id": 9030,
            "status": "shipped",
        },
    )

    cancellation = ToolResult.ok(
        tool="cancel_order",
        data={
            "type": "order_cancelled",
            "order_id": 9031,
            "status": "cancelled",
            "refund_eligibility": {
                "eligible": False,
                "status": "not_eligible",
            },
        },
    )

    assert isinstance(tracking, ToolResult)
    assert isinstance(cancellation, ToolResult)
    assert tracking.success is True
    assert cancellation.success is True
    assert tracking.data["type"] == "order_tracking"
    assert cancellation.data["type"] == "order_cancelled"
