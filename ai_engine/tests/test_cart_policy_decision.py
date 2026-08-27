from __future__ import annotations

import pytest

from ai_engine.nodes.policy_node import policy_node
from ai_engine.nodes.decision_node import decision_node


CART_CASES = [
    (
        "add_to_cart",
        "add_to_cart",
        {"product_name": "Maggi", "quantity": 2},
    ),
    (
        "remove_from_cart",
        "remove_from_cart",
        {"product_name": "Maggi"},
    ),
    (
        "update_cart_item",
        "update_cart_item",
        {"product_name": "Maggi", "quantity": 5},
    ),
    (
        "clear_cart",
        "clear_cart",
        {},
    ),
    (
        "show_cart",
        "show_cart",
        {},
    ),
]


@pytest.mark.parametrize(
    "tool,expected_tool,arguments",
    CART_CASES,
)
def test_cart_policy_allows_valid_cart_actions(
    tool,
    expected_tool,
    arguments,
):
    action = {
        "add_to_cart": "ADD_CART_ITEM",
        "remove_from_cart": "REMOVE_CART_ITEM",
        "update_cart_item": "UPDATE_CART_ITEM",
        "clear_cart": "CLEAR_CART",
        "show_cart": "SHOW_CART",
    }[tool]

    result = policy_node(
        {
            "planner": {
                "action": tool,
                "tool_name": tool,
                "arguments": arguments,
            },
            "planner_args": arguments,
        }
    )

    assert result["policy_result"]["allowed"] is True
    assert result["policy_result"]["tool"] == expected_tool


def test_policy_allows_checkout_cart_when_cart_has_items():
    result = policy_node(
        {
            "planner": {
                "action": "checkout_cart",
                "tool_name": "checkout_cart",
                "arguments": {},
            },
            "planner_args": {},
            "cart_items": [
                {
                    "product_id": 1,
                    "quantity": 2,
                }
            ],
        }
    )

    assert result["policy_result"]["allowed"] is True
    assert result["policy_result"]["tool"] == "checkout_cart"


def test_policy_rejects_checkout_empty_cart():
    result = policy_node(
        {
            "planner": {
                "action": "checkout_cart",
                "tool_name": "checkout_cart",
                "arguments": {},
            },
            "planner_args": {},
            "cart_items": [],
        }
    )

    assert result["policy_result"]["allowed"] is False
    assert result["policy_result"]["reason"] == "empty_cart"


@pytest.mark.parametrize(
    "action,tool,args,reason",
    [
        (
            "add_to_cart",
            "add_to_cart",
            {"quantity": 2},
            "missing_product_reference",
        ),
        (
            "add_to_cart",
            "add_to_cart",
            {"product_name": "Maggi"},
            "missing_quantity",
        ),
        (
            "update_cart_item",
            "update_cart_item",
            {"product_name": "Maggi", "quantity": 0},
            "invalid_quantity",
        ),
        (
            "update_cart_item",
            "update_cart_item",
            {"product_name": "Maggi", "quantity": -1},
            "invalid_quantity",
        ),
        (
            "remove_from_cart",
            "remove_from_cart",
            {},
            "missing_product_reference",
        ),
    ],
)
def test_policy_rejects_invalid_cart_arguments(
    action,
    tool,
    args,
    reason,
):
    result = policy_node(
        {
            "planner": {
                "action": action,
                "tool_name": tool,
                "arguments": args,
            },
            "planner_args": args,
        }
    )

    assert result["policy_result"]["allowed"] is False
    assert result["policy_result"]["reason"] == reason


def test_policy_rejects_cart_tool_mismatch():
    result = policy_node(
        {
            "planner": {
                "action": "add_to_cart",
                "tool_name": "remove_from_cart",
                "arguments": {
                    "product_name": "Maggi",
                    "quantity": 2,
                },
            },
            "planner_args": {
                "product_name": "Maggi",
                "quantity": 2,
            },
        }
    )

    assert result["policy_result"]["allowed"] is False
    assert result["policy_result"]["reason"] == "cart_action_tool_mismatch"


def test_policy_rejects_unknown_tool():
    result = policy_node(
        {
            "planner": {
                "action": "do_something",
                "tool_name": "invented_tool",
                "arguments": {},
            },
            "planner_args": {},
        }
    )

    assert result["policy_result"]["allowed"] is False
    assert result["policy_result"]["reason"] == "unsupported_tool"


def test_decision_routes_approved_cart_tool():
    policy = policy_node(
        {
            "planner": {
                "action": "add_to_cart",
                "tool_name": "add_to_cart",
                "arguments": {
                    "product_name": "Maggi",
                    "quantity": 2,
                },
            },
            "planner_args": {
                "product_name": "Maggi",
                "quantity": 2,
            },
        }
    )

    decision = decision_node(policy)

    assert decision["decision_route"] == "tool"
    assert decision["tool_name"] == "add_to_cart"


def test_decision_routes_rejected_cart_action_to_response():
    policy = policy_node(
        {
            "planner": {
                "action": "add_to_cart",
                "tool_name": "add_to_cart",
                "arguments": {
                    "product_name": "Maggi",
                },
            },
            "planner_args": {
                "product_name": "Maggi",
            },
        }
    )

    decision = decision_node(policy)

    assert decision["decision_route"] == "response"
    assert decision["tool_name"] is None
    assert decision["policy_error"]["reason"] == "missing_quantity"


def test_decision_fails_closed_for_missing_policy():
    decision = decision_node({})

    assert decision["decision_route"] == "response"
    assert decision["tool_name"] is None
    assert decision["policy_error"]["reason"] == "missing_policy_result"


def test_decision_never_bypasses_policy_for_toolless_action():
    decision = decision_node(
        {
            "policy_result": {
                "allowed": False,
                "action": "ANSWER",
                "tool": None,
                "reason": "some_policy_rejection",
            }
        }
    )

    assert decision["decision_route"] == "response"
    assert decision["tool_name"] is None
    assert decision["policy_error"]["reason"] == "some_policy_rejection"


def test_decision_fails_closed_if_conversational_action_has_tool():
    decision = decision_node(
        {
            "policy_result": {
                "allowed": True,
                "action": "ANSWER",
                "tool": "add_to_cart",
                "reason": None,
            }
        }
    )

    assert decision["decision_route"] == "response"
    assert decision["tool_name"] is None
    assert (
        decision["policy_error"]["reason"]
        == "tool_not_allowed_for_toolless_action"
    )