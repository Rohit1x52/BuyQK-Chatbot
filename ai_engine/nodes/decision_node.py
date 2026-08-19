# =========================================================
# BuyQK AI - Decision Node
# =========================================================
#
# Phase 2
#
# Responsibility:
#
#     Context
#        ↓
#     Understanding
#        ↓
#     Planner
#        ↓
#     Policy
#        ↓
#     Decision Node
#        ↓
#     Tool / Response
#
# =========================================================
#
# IMPORTANT:
#
# This node is intentionally SMALL.
#
# It does NOT:
#
#   - understand natural language
#   - extract entities
#   - calculate prices
#   - calculate bills
#   - determine stock
#   - determine authorization
#   - determine cancellation eligibility
#   - determine refund eligibility
#   - decide whether a user SHOULD perform an action
#   - independently create an order
#   - independently cancel an order
#
# Those responsibilities belong to:
#
#   AI Understanding -> Entity Node
#   Planning         -> Planner Node
#   Validation       -> Policy Node
#   Execution        -> Tool Node / Backend
#
# The Decision Node only converts the already validated
# planner/policy result into a simple graph routing decision.
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Supported Graph Actions
# =========================================================
#
# These are internal workflow actions.
#
# They are NOT natural-language intents.
#
# =========================================================


SUPPORTED_ACTIONS = {
    "search_products",
    "create_order",
    "track_order",
    "cancel_order",
    "create_support_ticket",
    "list_saved_addresses",
    "list_payment_methods",
    "respond",
    "ask_user",
    "none",
}


# =========================================================
# Supported Tools
# =========================================================


SUPPORTED_TOOLS = {
    "search_products",
    "create_order",
    "track_order",
    "cancel_order",
    "create_support_ticket",
    "list_saved_addresses",
    "list_payment_methods",
}


# =========================================================
# Safe Value Helper
# =========================================================


def _has_value(
    value: Any,
) -> bool:
    """
    Return True when a value is present.

    This function performs structural validation only.

    It does not interpret natural language.
    """

    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(
            value.strip()
        )

    return True


# =========================================================
# Planner Result
# =========================================================


def _get_planner_action(
    state: GraphState,
) -> str | None:
    """
    Read the action selected by planner_node.py.

    Planner output may be stored directly in GraphState
    or inside planner_state depending on the current
    graph implementation.
    """

    action = state.get(
        "planner_action"
    )

    if _has_value(action):
        return str(
            action
        ).strip().casefold()

    planner_state = state.get(
        "planner"
    )

    if isinstance(
        planner_state,
        dict,
    ):

        action = planner_state.get(
            "action"
        )

        if _has_value(action):
            return str(
                action
            ).strip().casefold()

    return None


# =========================================================
# Planner Tool
# =========================================================


def _get_planner_tool(
    state: GraphState,
) -> str | None:
    """
    Read the tool selected by planner_node.py.

    The Decision Node does not independently select a tool.
    """

    tool_name = state.get(
        "planner_tool"
    )

    if _has_value(tool_name):
        return str(
            tool_name
        ).strip().casefold()

    planner_state = state.get(
        "planner"
    )

    if isinstance(
        planner_state,
        dict,
    ):

        tool_name = planner_state.get(
            "tool_name"
        )

        if _has_value(tool_name):
            return str(
                tool_name
            ).strip().casefold()

    # Compatibility with an existing GraphState that may
    # already contain tool_name.
    #
    # This is only a fallback.
    #
    # New planner architecture should populate planner_tool.

    tool_name = state.get(
        "tool_name"
    )

    if _has_value(tool_name):
        return str(
            tool_name
        ).strip().casefold()

    return None


# =========================================================
# Policy Result
# =========================================================


def _get_policy_decision(
    state: GraphState,
) -> str | None:
    """
    Read the result produced by policy_node.py.

    Expected values:

        allowed
        denied
        needs_confirmation
        needs_information

    The exact policy vocabulary may be extended later.
    """

    policy_decision = state.get(
        "policy_decision"
    )

    if _has_value(
        policy_decision
    ):
        return str(
            policy_decision
        ).strip().casefold()

    policy_state = state.get(
        "policy"
    )

    if isinstance(
        policy_state,
        dict,
    ):

        policy_decision = (
            policy_state.get(
                "decision"
            )
        )

        if _has_value(
            policy_decision
        ):
            return str(
                policy_decision
            ).strip().casefold()

    return None


# =========================================================
# Policy Allowed
# =========================================================


def _policy_allows_execution(
    state: GraphState,
) -> bool:
    """
    Return whether policy_node.py has explicitly allowed
    the planned action.

    Fail closed.

    If policy information is missing, execution is NOT allowed.
    """

    decision = _get_policy_decision(
        state
    )

    return decision in {
        "allowed",
        "allow",
        "approved",
        "approve",
        "valid",
    }


# =========================================================
# Policy Block Reason
# =========================================================


def _get_policy_reason(
    state: GraphState,
) -> str | None:
    """
    Read the explanation produced by policy_node.py.
    """

    reason = state.get(
        "policy_reason"
    )

    if _has_value(reason):
        return str(
            reason
        ).strip()

    policy_state = state.get(
        "policy"
    )

    if isinstance(
        policy_state,
        dict,
    ):

        reason = policy_state.get(
            "reason"
        )

        if _has_value(reason):
            return str(
                reason
            ).strip()

        reason = policy_state.get(
            "message"
        )

        if _has_value(reason):
            return str(
                reason
            ).strip()

    return None


# =========================================================
# Planner Status
# =========================================================


def _get_planner_status(
    state: GraphState,
) -> str | None:
    """
    Read planner status when available.
    """

    status = state.get(
        "planner_status"
    )

    if _has_value(status):
        return str(
            status
        ).strip().casefold()

    planner_state = state.get(
        "planner"
    )

    if isinstance(
        planner_state,
        dict,
    ):

        status = planner_state.get(
            "status"
        )

        if _has_value(status):
            return str(
                status
            ).strip().casefold()

    return None


# =========================================================
# Decision Node
# =========================================================


def decision_node(
    state: GraphState,
) -> GraphState:
    """
    Convert planner + policy output into graph routing state.

    ========================================================
    Phase 2 contract
    ========================================================

    Planner answers:

        "What should happen next?"

    Policy answers:

        "Is that action allowed?"

    Decision Node answers:

        "Where should the graph go?"

    ========================================================

    This node does NOT make a new business decision.

    It only routes an already-planned and policy-validated
    action.
    """

    # =====================================================
    # Read planner output
    # =====================================================

    planner_action = _get_planner_action(
        state
    )

    planner_tool = _get_planner_tool(
        state
    )

    planner_status = _get_planner_status(
        state
    )

    # =====================================================
    # Read policy output
    # =====================================================

    policy_decision = _get_policy_decision(
        state
    )

    policy_reason = _get_policy_reason(
        state
    )

    policy_allowed = (
        _policy_allows_execution(
            state
        )
    )

    # =====================================================
    # Basic debug information
    # =====================================================

    print(
        "\n"
        "====================================================\n"
        "[DECISION NODE]\n"
        "====================================================\n"
        f"planner_action  = {planner_action!r}\n"
        f"planner_tool    = {planner_tool!r}\n"
        f"planner_status  = {planner_status!r}\n"
        f"policy_decision = {policy_decision!r}\n"
        f"policy_allowed  = {policy_allowed!r}\n"
        f"policy_reason   = {policy_reason!r}\n"
        "====================================================\n"
    )

    # =====================================================
    # 1. No planner decision
    # =====================================================
    #
    # Fail closed.
    #
    # We do NOT try to reconstruct an action from:
    #
    #   intent
    #   entities
    #   checkout state
    #
    # That would recreate the old Decision Node.
    #
    # =====================================================

    if planner_action is None:

        print(
            "[DECISION NODE]"
            " -> no planner action"
            " -> response"
        )

        return {
            "decision": "respond",
            "next_action": "respond",
            "tool_name": None,
        }

    # =====================================================
    # 2. Planner explicitly says no action
    # =====================================================

    if planner_action in {
        "none",
        "respond",
        "answer",
    }:

        print(
            "[DECISION NODE]"
            f" -> planner action={planner_action!r}"
            " -> response"
        )

        return {
            "decision": "respond",
            "next_action": "respond",
            "tool_name": None,
        }

    # =====================================================
    # 3. Ask user
    # =====================================================

    if planner_action in {
        "ask_user",
        "request_information",
        "needs_information",
        "clarification",
    }:

        print(
            "[DECISION NODE]"
            " -> planner requires user information"
        )

        return {
            "decision": "ask_user",
            "next_action": "ask_user",
            "tool_name": None,
        }

    # =====================================================
    # 4. Policy has not approved the action
    # =====================================================
    #
    # This is fail-closed.
    #
    # The Decision Node must NEVER bypass policy.
    #
    # =====================================================

    if not policy_allowed:

        print(
            "[DECISION NODE]"
            " -> policy did not allow execution"
            f" | action={planner_action!r}"
            f" | reason={policy_reason!r}"
        )

        return {
            "decision": "respond",
            "next_action": "respond",
            "tool_name": None,
            "policy_blocked": True,
            "policy_reason": policy_reason,
        }

    # =====================================================
    # 5. Planner requested an action but no tool
    # =====================================================

    if planner_tool is None:

        print(
            "[DECISION NODE]"
            " -> planner action has no tool"
            f" | action={planner_action!r}"
        )

        return {
            "decision": "respond",
            "next_action": "respond",
            "tool_name": None,
            "policy_blocked": False,
        }

    # =====================================================
    # 6. Validate tool
    # =====================================================

    if planner_tool not in SUPPORTED_TOOLS:

        print(
            "[DECISION NODE]"
            " -> unsupported tool"
            f" | tool={planner_tool!r}"
        )

        return {
            "decision": "respond",
            "next_action": "respond",
            "tool_name": None,
            "tool_error": (
                f"Unsupported tool: {planner_tool}"
            ),
        }

    # =====================================================
    # 7. Route to tool
    # =====================================================

    print(
        "[DECISION NODE]"
        f" -> tool={planner_tool!r}"
    )

    return {
        "decision": "tool",
        "next_action": planner_action,
        "tool_name": planner_tool,
        "policy_blocked": False,
    }