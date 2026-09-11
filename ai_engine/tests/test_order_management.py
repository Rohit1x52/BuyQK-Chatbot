import pytest

from ai_engine.graph.state import GraphState
from ai_engine.nodes import entity_node as entity_module
from ai_engine.nodes import planner_node as planner_module
from ai_engine.nodes import policy_node as policy_module
from ai_engine.nodes import tool_node as tool_module
from ai_engine.nodes import response_node as response_module
from ai_engine.tools.results import ToolErrorResult, ToolResult
from backend.services import order_service


class FakeOrder:
    def __init__(
        self,
        order_id,
        user_id=7,
        status="processing",
        payment_status="pending",
        total_amount=None,
    ):
        self.id = order_id
        self.user_id = user_id
        self.status = status
        self.payment_status = payment_status
        self.total_amount = total_amount


def _tracking_state(order_id=None, user_id=7):
    state = {
        "tool_name": "track_order",
        "user_id": user_id,
        "entities": {},
    }

    if order_id is not None:
        state["order_id"] = order_id
        state["entities"]["order_id"] = order_id

    return state


def _cancellation_state(
    order_id=None,
    user_id=7,
    reason=None,
):
    state = {
        "tool_name": "cancel_order",
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
# PHASE 8C — TRACKING SAFETY / INTEGRITY
# =========================================================

def test_01_tracking_missing_order_id():
    result = tool_module.tool_node(
        _tracking_state(),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert tool_result.error.code == "order_tracking"
    assert result["awaiting_order_tracking_order_id"] is True


def test_02_tracking_valid_order_id(monkeypatch):
    order = FakeOrder(
        101,
        user_id=7,
        status="shipped",
        payment_status="success",
    )

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: order,
    )
    monkeypatch.setattr(
        tool_module,
        "build_order_bill",
        lambda db, order: None,
    )

    result = tool_module.tool_node(
        _tracking_state(101),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.tool == "track_order"
    assert tool_result.data["type"] == "order_tracking"
    assert tool_result.data["order_id"] == 101
    assert tool_result.data["status"] == "shipped"
    assert tool_result.data["payment_status"] == "success"


def test_03_tracking_invalid_order_id(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: None,
    )

    result = tool_module.tool_node(
        _tracking_state(999999),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert "does not exist" in tool_result.error.message.lower()


def test_04_tracking_rejects_another_users_order(monkeypatch):
    order = FakeOrder(
        202,
        user_id=99,
        status="shipped",
    )

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: order,
    )

    result = tool_module.tool_node(
        _tracking_state(202, user_id=7),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.error is not None
    assert "authorized" in tool_result.error.message.lower()


def test_05_tracking_backend_failure(monkeypatch):
    def failing_get_order(db, order_id):
        raise RuntimeError("tracking backend unavailable")

    monkeypatch.setattr(
        tool_module,
        "get_order",
        failing_get_order,
    )

    result = tool_module.tool_node(
        _tracking_state(303),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert "tracking backend unavailable" in tool_result.error.message


def test_06_tracking_preserves_backend_status(monkeypatch):
    order = FakeOrder(
        404,
        user_id=7,
        status="out_for_delivery",
        payment_status="success",
    )

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: order,
    )
    monkeypatch.setattr(
        tool_module,
        "build_order_bill",
        lambda db, order: None,
    )

    result = tool_module.tool_node(
        _tracking_state(404),
        db=object(),
    )

    data = result["tool_result"].data

    assert data["status"] == "out_for_delivery"
    assert data["payment_status"] == "success"


def test_07_latest_order_is_resolved_by_backend(monkeypatch):
    latest = FakeOrder(
        501,
        user_id=7,
        status="shipped",
    )
    previous = FakeOrder(
        500,
        user_id=7,
        status="delivered",
    )

    calls = []

    def fake_get_user_orders(db, user_id, limit=20):
        calls.append((user_id, limit))
        return [latest, previous]

    monkeypatch.setattr(
        tool_module,
        "get_user_orders",
        fake_get_user_orders,
    )
    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: latest,
    )
    monkeypatch.setattr(
        tool_module,
        "build_order_bill",
        lambda db, order: None,
    )

    state = {
        "tool_name": "track_order",
        "user_id": 7,
        "entities": {
            "order_reference_type": "latest",
        },
        "order_reference_type": "latest",
    }

    result = tool_module.tool_node(
        state,
        db=object(),
    )

    data = result["tool_result"].data

    assert data["order_id"] == 501
    assert data["status"] == "shipped"
    assert calls == [(7, 2)]


def test_08_multiple_orders_without_reference_are_not_ambiguous_by_ai(monkeypatch):
    calls = []

    monkeypatch.setattr(
        tool_module,
        "get_user_orders",
        lambda db, user_id, limit=20: calls.append(True) or [
            FakeOrder(601, user_id=7),
            FakeOrder(600, user_id=7),
        ],
    )

    result = tool_module.tool_node(
        _tracking_state(),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert result["awaiting_order_tracking_order_id"] is True
    assert calls == []


# =========================================================
# PHASE 8C — CANCELLATION SAFETY / INTEGRITY
# =========================================================

def test_09_cancellation_missing_order_id():
    result = tool_module.tool_node(
        _cancellation_state(),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert tool_result.error.code == "order_cancellation"


def test_10_cancellation_invalid_order_id(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": False,
            "order_id": order_id,
            "reason_code": "invalid_order_id",
        },
    )

    result = tool_module.tool_node(
        _cancellation_state("not-a-number"),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False


def test_11_cancellation_rejects_another_users_order(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": False,
            "order_id": order_id,
            "reason_code": "unauthorized",
        },
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    result = tool_module.tool_node(
        _cancellation_state(701),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert cancel_calls == []


def test_12_backend_rejects_already_cancelled_order(monkeypatch):
    order = FakeOrder(
        702,
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
        order_id=702,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "already_cancelled"


def test_13_backend_rejects_delivered_order(monkeypatch):
    order = FakeOrder(
        703,
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
        order_id=703,
        user_id=7,
    )

    assert result["eligible"] is False
    assert result["reason_code"] == "not_cancellable_status"


def test_14_cancellation_eligibility_failure_does_not_cancel(monkeypatch):
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

    result = tool_module.tool_node(
        _cancellation_state(704),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert tool_result.error.code == "order_cancellation"
    assert cancel_calls == []


def test_15_cancellation_requires_reason_after_backend_eligibility(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    result = tool_module.tool_node(
        _cancellation_state(705),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result.success is True
    assert tool_result.data["type"] == "cancellation_eligibility"
    assert tool_result.data["needs_reason"] is True
    assert result["awaiting_cancellation_reason"] is True
    assert cancel_calls == []


def test_16_successful_cancellation(monkeypatch):
    order = FakeOrder(
        706,
        user_id=7,
        status="cancelled",
        payment_status="refunded",
    )

    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda db, order_id, user_id: (
            cancel_calls.append((order_id, user_id))
            or order
        ),
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

    result = tool_module.tool_node(
        _cancellation_state(
            706,
            reason="ordered by mistake",
        ),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is True
    assert tool_result.data["type"] == "order_cancelled"
    assert tool_result.data["order_id"] == 706
    assert tool_result.data["status"] == "cancelled"
    assert tool_result.data["cancellation_reason"] == "ordered by mistake"
    assert cancel_calls == [(706, 7)]
    assert result["awaiting_cancellation_reason"] is False


def test_17_refund_eligibility_is_taken_from_backend(monkeypatch):
    order = FakeOrder(
        707,
        user_id=7,
        status="cancelled",
    )

    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )
    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda db, order_id, user_id: order,
    )

    backend_refund = {
        "eligible": False,
        "order_id": 707,
        "status": "not_eligible",
        "payment_status": "pending",
        "reason_code": "payment_not_completed",
    }

    monkeypatch.setattr(
        tool_module,
        "get_refund_eligibility",
        lambda db, order_id, user_id: backend_refund,
    )

    result = tool_module.tool_node(
        _cancellation_state(
            707,
            reason="changed my mind",
        ),
        db=object(),
    )

    data = result["tool_result"].data

    assert data["type"] == "order_cancelled"
    assert data["refund_eligibility"] == backend_refund
    assert data["refund_eligibility"]["status"] == "not_eligible"


def test_18_backend_cancellation_failure(monkeypatch):
    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: {
            "eligible": True,
            "order_id": order_id,
            "status": "processing",
        },
    )

    def failing_cancel(db, order_id, user_id):
        raise RuntimeError("cancellation backend unavailable")

    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        failing_cancel,
    )

    result = tool_module.tool_node(
        _cancellation_state(
            708,
            reason="wrong order",
        ),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert isinstance(tool_result, ToolResult)
    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert "cancellation" in tool_result.error.message.lower()


def test_19_failed_cancellation_cannot_produce_confirmation():
    text = response_module._tool_fallback({
        "success": False,
        "type": "order_cancellation",
        "error": "Cancellation failed.",
    })

    assert "cancelled" not in text.lower()


# =========================================================
# PHASE 8C — STATE SAFETY
# =========================================================

def test_20_successful_tracking_state():
    order = FakeOrder(
        801,
        user_id=7,
        status="shipped",
        payment_status="success",
    )

    # This test verifies the state shape expected after a successful
    # tracking execution without allowing the response layer to invent
    # additional tracking data.
    state = {
        "tool_name": "track_order",
        "tool_result": ToolResult.ok(
            tool="track_order",
            data={
                "type": "order_tracking",
                "order_id": order.id,
                "status": order.status,
                "payment_status": order.payment_status,
            },
        ),
        "order_id": order.id,
        "awaiting_order_tracking_confirmation": False,
    }

    assert state["tool_result"].success is True
    assert state["tool_result"].data["type"] == "order_tracking"
    assert state["order_id"] == 801
    assert state["awaiting_order_tracking_confirmation"] is False


def test_21_failed_tracking_state():
    state = {
        "tool_name": "track_order",
        "tool_result": ToolResult.fail(
            tool="track_order",
            error=ToolErrorResult(
                code="order_tracking",
                message="Order does not exist.",
            ),
        ),
        "order_id": 802,
        "awaiting_order_tracking_confirmation": False,
    }

    assert state["tool_result"].success is False
    assert (
        state["tool_result"].error.message
        == "Order does not exist."
    )
    assert state["order_id"] == 802


def test_22_successful_cancellation_state():
    state = {
        "tool_name": "cancel_order",
        "tool_result": ToolResult.ok(
            tool="cancel_order",
            data={
                "type": "order_cancelled",
                "order_id": 803,
                "status": "cancelled",
                "cancellation_reason": "ordered by mistake",
                "refund_eligibility": {
                    "eligible": True,
                    "status": "refunded",
                },
            },
        ),
        "order_id": 803,
        "order_created": False,
        "checkout_completed": False,
        "awaiting_cancellation_reason": False,
    }

    assert state["tool_result"].success is True
    assert state["tool_result"].data["type"] == "order_cancelled"
    assert state["order_id"] == 803
    assert state["awaiting_cancellation_reason"] is False


def test_23_failed_cancellation_state():
    state = {
        "tool_name": "cancel_order",
        "tool_result": ToolResult.fail(
            tool="cancel_order",
            error=ToolErrorResult(
                code="order_cancellation",
                message="This order is not eligible for cancellation.",
            ),
        ),
        "order_id": 804,
        "awaiting_cancellation_reason": False,
    }

    assert state["tool_result"].success is False
    assert state["tool_result"].data is None
    assert state["order_id"] == 804
    assert state["awaiting_cancellation_reason"] is False


def test_24_stale_order_id_cannot_leak_between_users(monkeypatch):
    stale_order = FakeOrder(
        805,
        user_id=99,
        status="shipped",
    )

    monkeypatch.setattr(
        tool_module,
        "get_order",
        lambda db, order_id: stale_order,
    )

    state = _tracking_state(
        805,
        user_id=7,
    )

    result = tool_module.tool_node(
        state,
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result.success is False
    assert tool_result.error is not None
    assert "authorized" in tool_result.error.message.lower()


def test_25_cancelled_order_cannot_be_cancelled_again_incorrectly(monkeypatch):
    order = FakeOrder(
        806,
        user_id=7,
        status="cancelled",
    )

    monkeypatch.setattr(
        order_service,
        "get_order",
        lambda db, order_id: order,
    )

    eligibility = order_service.check_cancellation_eligibility(
        db=object(),
        order_id=806,
        user_id=7,
    )

    assert eligibility["eligible"] is False
    assert eligibility["reason_code"] == "already_cancelled"

    monkeypatch.setattr(
        tool_module,
        "check_cancellation_eligibility",
        lambda db, order_id, user_id: eligibility,
    )

    cancel_calls = []

    monkeypatch.setattr(
        tool_module,
        "cancel_order",
        lambda **kwargs: cancel_calls.append(kwargs),
    )

    result = tool_module.tool_node(
        _cancellation_state(
            806,
            reason="try again",
        ),
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result.success is False
    assert tool_result.data is None
    assert tool_result.error is not None
    assert tool_result.error.code == "order_cancellation"
    assert cancel_calls == []
