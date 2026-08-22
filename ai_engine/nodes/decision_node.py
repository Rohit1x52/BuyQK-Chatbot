# =========================================================
# BuyQK AI - Decision Node
# =========================================================
#
# Responsibility:
#
#     Planner
#         ↓
#     Policy
#         ↓
#     Decision
#         ↓
#     Tool / Response
#
# The Decision Node is ONLY a routing layer.
#
# It does NOT:
#
#   - decide user intent
#   - choose a tool
#   - reinterpret planner output
#   - apply business rules
#   - validate cart operations
#   - validate checkout state
#   - execute backend operations
#   - create orders
#   - modify transactional state
#
# Source of truth:
#
#   Planner
#       → proposes the action/tool
#
#   Policy
#       → approves or rejects the proposal
#
#   Decision
#       → routes the Policy result
#
#   Tool
#       → executes an approved backend capability
#
#   Response
#       → handles user-facing output
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
# Policy Result Helper
# =========================================================

def _get_policy_result(
    state: GraphState,
) -> dict[str, Any]:
    """
    Safely retrieve the Policy result from GraphState.

    Policy is the only authority used by this node.

    Returns:
        A dictionary when policy_result is valid.
        An empty dictionary otherwise.
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
# Normalization Helpers
# =========================================================

def _normalize_action(
    value: Any,
) -> str | None:
    """
    Normalize an action for consistent graph state.

    The Decision Node does not interpret the action.

    Example:

        "add_to_cart"
            ↓
        "ADD_TO_CART"
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    return value.upper()


def _normalize_tool(
    value: Any,
) -> str | None:
    """
    Normalize a tool name.

    Tool names are kept lowercase because the Tool Node
    uses the canonical backend capability name.
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    return value.casefold()


# =========================================================
# Decision Result Builder
# =========================================================

def _build_decision(
    *,
    route: str,
    allowed: bool,
    action: str | None,
    tool: str | None,
    reason: Any = None,
) -> GraphState:
    """
    Build the complete deterministic Decision result.

    This keeps every return path consistent and prevents
    stale routing/error state from leaking between turns.
    """

    return {
        "decision": {
            "route": route,
            "allowed": allowed,
            "action": action,
            "tool": tool,
            "reason": reason,
        },
        "decision_route": route,
        "tool_name": tool,
        "policy_error": (
            None
            if allowed
            else {
                "allowed": False,
                "action": action,
                "reason": reason,
            }
        ),
    }


# =========================================================
# Decision Node
# =========================================================

def decision_node(
    state: GraphState,
) -> GraphState:
    """
    Convert the approved Policy result into a routing decision.

    Routing rules are intentionally minimal:

        Policy missing
            → Response

        Policy rejected
            → Response

        Policy approved + no tool
            → Response

        Policy approved + tool
            → Tool

    The Decision Node does not know what an action means.

    Therefore:

        ADD_TO_CART
        CREATE_ORDER
        TRACK_ORDER
        ASK_CLARIFICATION
        ANSWER
        etc.

    are NOT interpreted here.

    Policy has already decided whether the proposal is valid.
    """

    # =====================================================
    # Read Policy Result
    # =====================================================

    policy_result = _get_policy_result(
        state
    )

    # =====================================================
    # Missing Policy Result
    # =====================================================
    #
    # Without Policy approval, the Tool Node must never run.
    #
    # Fail closed.
    # =====================================================

    if not policy_result:

        print(
            "\n"
            "====================================================\n"
            "[DECISION NODE]\n"
            "====================================================\n"
            "Policy result is missing.\n"
            "Routing to RESPONSE.\n"
            "====================================================\n"
        )

        return _build_decision(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=None,
            tool=None,
            reason="missing_policy_result",
        )

    # =====================================================
    # Read Policy Fields
    # =====================================================

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

    reason = policy_result.get(
        "reason"
    )

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
        f"reason  = {reason!r}\n"
        "====================================================\n"
    )

    # =====================================================
    # POLICY REJECTED
    # =====================================================
    #
    # Decision MUST NOT override Policy.
    #
    # Even if Policy supplied a tool together with a rejection,
    # the tool is discarded.
    # =====================================================

    if not allowed:

        return _build_decision(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=action,
            tool=None,
            reason=reason or "policy_rejected",
        )

    # =====================================================
    # POLICY APPROVED WITHOUT TOOL
    # =====================================================
    #
    # This naturally handles:
    #
    #   ANSWER
    #   ASK_CLARIFICATION
    #   CONFIRM
    #   END_CONVERSATION
    #   START_CHECKOUT
    #   MODIFY_CHECKOUT
    #
    # Decision does NOT need to know these names.
    #
    # If Policy says:
    #
    #   allowed = True
    #   tool = None
    #
    # then this is a response route.
    # =====================================================

    if tool is None:

        return _build_decision(
            route=ROUTE_RESPONSE,
            allowed=True,
            action=action,
            tool=None,
            reason=None,
        )

    # =====================================================
    # POLICY APPROVED WITH TOOL
    # =====================================================
    #
    # Policy has already validated the tool.
    #
    # Decision forwards it unchanged except for safe
    # normalization.
    #
    # Examples:
    #
    #   add_to_cart
    #   remove_from_cart
    #   update_cart_item
    #   clear_cart
    #   show_cart
    #   checkout_cart
    #   create_order
    #   track_order
    #
    # No tool mapping belongs here.
    # =====================================================

    return _build_decision(
        route=ROUTE_TOOL,
        allowed=True,
        action=action,
        tool=tool,
        reason=None,
    )