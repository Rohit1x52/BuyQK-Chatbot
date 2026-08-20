# =========================================================
# BuyQK AI - Decision Node
# =========================================================
#
# Responsibility:
#
# Planner
#     ↓
# Policy
#     ↓
# Decision
#     ↓
# Tool
#
# The Decision Node does NOT:
#
#   - decide user intent
#   - select a new tool
#   - bypass policy
#   - execute backend operations
#   - create orders
#   - modify transactional state
#
# It only converts the approved Policy result into a
# deterministic routing decision.
#
# =========================================================

from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Routing Constants
# =========================================================

ROUTE_TOOL = "tool"
ROUTE_RESPONSE = "response"


# =========================================================
# Actions That Never Need Policy Approval
# =========================================================
#
# FIX:
#
# These are pure conversational actions. They never call a tool,
# never touch checkout state, and never mutate backend data. They
# must always be allowed regardless of what Policy decided, because
# a plain "answer" turn (e.g. replying to "Hi") cannot violate any
# business/checkout invariant.
#
# Without this, an upstream Policy rejection meant for a different,
# transactional action can incorrectly block ordinary conversation.
# =========================================================

SAFE_ACTIONS_WITHOUT_TOOL = {
    "ANSWER",
    "GENERAL",
    "CHAT",
    "RESPOND",
    "GREETING",
}


# =========================================================
# Helpers
# =========================================================

def _normalize_action(
    value: Any,
) -> str | None:
    """
    Normalize an action safely.
    """

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    return value.upper()


def _normalize_tool(
    value: Any,
) -> str | None:
    """
    Normalize a tool name safely.
    """

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    return value.casefold()


def _get_policy_result(
    state: GraphState,
) -> dict[str, Any]:
    """
    Safely read policy_result from GraphState.
    """

    policy_result = state.get(
        "policy_result"
    )

    if not isinstance(
        policy_result,
        dict,
    ):
        return {}

    return policy_result


# =========================================================
# Decision Node
# =========================================================

def decision_node(
    state: GraphState,
) -> GraphState:
    """
    Deterministically route the graph after Policy.

    Policy decides:
        allowed / rejected

    Decision decides:
        tool / response

    Tool execution happens later.

    Response generation happens later.

    IMPORTANT (fix):

    Every return path below now explicitly sets "policy_error".
    Response Node reads this key to explain a rejected transaction.
    Because Decision Node runs on every turn, always writing this
    key (even to None) guarantees a rejection from an earlier turn
    can never leak into a later, unrelated turn (e.g. "Hi" being
    shown a stale checkout-rejection message).
    """

    policy_result = _get_policy_result(
        state
    )

    allowed = bool(
        policy_result.get(
            "allowed",
            False,
        )
    )

    action = _normalize_action(
        policy_result.get(
            "action"
        )
    )

    tool = _normalize_tool(
        policy_result.get(
            "tool"
        )
    )

    # =====================================================
    # SAFE ACTION OVERRIDE
    # =====================================================
    #
    # A tool-less conversational action can never be a policy
    # violation. If Policy withheld approval (or omitted it) for
    # one of these actions, approve it here instead of rejecting
    # ordinary conversation.
    # =====================================================

    if (
        not allowed
        and not tool
        and action in SAFE_ACTIONS_WITHOUT_TOOL
    ):

        allowed = True

    # =====================================================
    # DEBUG
    # =====================================================

    print(
        "\n"
        "====================================================\n"
        "[DECISION NODE]\n"
        "====================================================\n"
        f"allowed = {allowed!r}\n"
        f"action  = {action!r}\n"
        f"tool    = {tool!r}\n"
        "====================================================\n"
    )

    # =====================================================
    # POLICY MISSING
    # =====================================================

    if not policy_result:

        return {
            "decision": {
                "route": ROUTE_RESPONSE,
                "allowed": False,
                "action": None,
                "tool": None,
                "reason": "missing_policy_result",
            },
            "decision_route": ROUTE_RESPONSE,
            "tool_name": None,
            "policy_error": None,
        }

    # =====================================================
    # POLICY REJECTED
    # =====================================================

    if not allowed:

        reason = policy_result.get(
            "reason"
        )

        return {
            "decision": {
                "route": ROUTE_RESPONSE,
                "allowed": False,
                "action": action,
                "tool": None,
                "reason": reason,
            },
            "decision_route": ROUTE_RESPONSE,
            "tool_name": None,
            "policy_error": {
                "allowed": False,
                "action": action,
                "reason": reason,
            },
        }

    # =====================================================
    # APPROVED BUT NO TOOL
    # =====================================================

    if not tool:

        return {
            "decision": {
                "route": ROUTE_RESPONSE,
                "allowed": True,
                "action": action,
                "tool": None,
                "reason": None,
            },
            "decision_route": ROUTE_RESPONSE,
            "tool_name": None,
            "policy_error": None,
        }

    # =====================================================
    # APPROVED TOOL
    # =====================================================

    return {
        "decision": {
            "route": ROUTE_TOOL,
            "allowed": True,
            "action": action,
            "tool": tool,
            "reason": None,
        },
        "decision_route": ROUTE_TOOL,
        "tool_name": tool,
        "policy_error": None,
    }