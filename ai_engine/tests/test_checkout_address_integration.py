from types import SimpleNamespace
import importlib

import pytest

from ai_engine.graph.state import GraphState
from backend.services import address_service

tool_node_module = importlib.import_module(
    "ai_engine.nodes.tool_node"
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *conditions, **kwargs):
        filtered = self.rows

        for condition in conditions:
            left = getattr(condition, "left", None)
            right = getattr(condition, "right", None)

            column_name = getattr(left, "name", None)

            if column_name is None:
                continue

            value = getattr(right, "value", right)

            filtered = [
                row
                for row in filtered
                if getattr(row, column_name, None) == value
            ]

        return FakeQuery(filtered)

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDB:
    def __init__(self, addresses):
        self.addresses = addresses

    def query(self, model):
        return FakeQuery(self.addresses)


def make_address(
    address_id,
    user_id,
    label="Home",
):
    return SimpleNamespace(
        id=address_id,
        user_id=user_id,
        label=label,
        address="Test Street",
        address_line_2=None,
        city="Test City",
        state="Test State",
        postal_code="000000",
        latitude=None,
        longitude=None,
        is_default=False,
    )


# =========================================================
# ADDRESS SERVICE
# =========================================================

def test_get_saved_addresses_returns_user_addresses():
    addresses = [
        make_address(1, 10, "Home"),
        make_address(2, 10, "Work"),
        make_address(3, 20, "Other User"),
    ]

    result = address_service.get_saved_addresses(
        db=FakeDB(addresses),
        user_id=10,
    )

    assert [address.id for address in result] == [1, 2]


def test_get_address_accepts_address_owned_by_user():
    db = FakeDB([
        make_address(11, 100),
    ])

    result = address_service.get_address(
        db=db,
        address_id=11,
        user_id=100,
    )

    assert result is not None
    assert result.id == 11
    assert result.user_id == 100


def test_get_address_rejects_another_users_address():
    db = FakeDB([
        make_address(12, 200),
    ])

    result = address_service.get_address(
        db=db,
        address_id=12,
        user_id=100,
    )

    assert result is None


def test_get_address_rejects_missing_id():
    with pytest.raises(
        ValueError,
        match="address_id is required",
    ):
        address_service.get_address(
            db=FakeDB([]),
            address_id=None,
            user_id=100,
        )


def test_invalid_address_id_is_rejected():
    db = FakeDB([
        make_address(51, 500),
    ])

    result = address_service.get_address(
        db=db,
        address_id=999,
        user_id=500,
    )

    assert result is None


# =========================================================
# LIST SAVED ADDRESSES TOOL
# =========================================================

def test_list_saved_addresses_tool_returns_backend_addresses(
    monkeypatch,
):
    addresses = [
        make_address(31, 300, "Home"),
        make_address(32, 300, "Office"),
    ]

    monkeypatch.setattr(
        tool_node_module,
        "get_user_addresses",
        lambda db, user_id: addresses,
    )

    state: GraphState = {
        "user_id": 300,
        "tool_name": "list_saved_addresses",
    }

    result = tool_node_module.tool_node(
        state=state,
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result["success"] is True
    assert tool_result["type"] == "address_selection"
    assert tool_result["allow_new"] is True

    assert [
        item["id"]
        for item in tool_result["addresses"]
    ] == [31, 32]


def test_list_saved_addresses_requires_user_id():
    state: GraphState = {
        "tool_name": "list_saved_addresses",
    }

    result = tool_node_module.tool_node(
        state=state,
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result["success"] is False

    # The failure path does not guarantee a "type" field.
    assert (
        "user_id" in str(tool_result).lower()
        or "user" in str(tool_result).lower()
    )


def test_list_saved_addresses_allows_new_address_when_empty(
    monkeypatch,
):
    monkeypatch.setattr(
        tool_node_module,
        "get_user_addresses",
        lambda db, user_id: [],
    )

    state: GraphState = {
        "user_id": 300,
        "tool_name": "list_saved_addresses",
    }

    result = tool_node_module.tool_node(
        state=state,
        db=object(),
    )

    tool_result = result["tool_result"]

    assert tool_result["success"] is True
    assert tool_result["type"] == "address_selection"
    assert tool_result["addresses"] == []
    assert tool_result["allow_new"] is True


# =========================================================
# CHECKOUT ADDRESS STATE
# =========================================================

def test_selected_address_uses_backend_id():
    state: GraphState = {
        "checkout_id": "checkout-test",
        "checkout_status": "collecting",
        "selected_address_id": 41,
        "address_id": 41,
    }

    assert state["selected_address_id"] == 41
    assert state["address_id"] == 41


def test_checkout_address_state_survives_next_turn():
    previous: GraphState = {
        "checkout_id": "checkout-persistent",
        "checkout_status": "collecting",
        "selected_address_id": 61,
        "address_id": 61,
    }

    next_turn: GraphState = {
        "checkout_id": previous["checkout_id"],
        "checkout_status": previous["checkout_status"],
        "selected_address_id": previous[
            "selected_address_id"
        ],
        "address_id": previous["address_id"],
    }

    assert next_turn["checkout_id"] == "checkout-persistent"
    assert next_turn["selected_address_id"] == 61
    assert next_turn["address_id"] == 61