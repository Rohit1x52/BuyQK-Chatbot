# =========================================================
# BuyQK AI - Policy / Validator Node
# =========================================================
#
# Purpose:
# Validate the AI Planner's proposed action before allowing
# the Tool Node to execute anything.
#
# Phase 2 architecture:
#
#   Context
#      ↓
#   Understander
#      ↓
#   Planner
#      ↓
#   Policy / Validator
#      ↓
#   Tool
#
# IMPORTANT:
#
# The Policy Node is NOT another AI decision maker.
#
# The AI Planner proposes:
#
#   action
#   tool
#   arguments
#
# This node verifies whether that proposal is compatible
# with the authoritative application state.
#
# It does NOT:
#
#   - calculate prices
#   - calculate bills
#   - check product stock by itself
#   - create orders
#   - generate order IDs
#   - generate checkout IDs
#   - invent payment methods
#   - invent addresses
#
# Those responsibilities belong to backend services.
#
# The Policy Node protects backend tools from invalid AI
# proposals and prevents completed transactions from being
# executed again.
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


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
}


# =========================================================
# Actions That Do Not Require Backend Tools
# =========================================================

NON_TOOL_ACTIONS = {
    "ANSWER",
    "ASK_CLARIFICATION",
    "CONFIRM",
    "END_CONVERSATION",
}


# =========================================================
# Utility
# =========================================================

def _has_value(
    value: Any,
) -> bool:
    """
    Determine whether a value is meaningfully present.

    Empty strings and None are considered absent.
    Numeric zero remains a valid value.
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


def _failure(
    reason: str,
    *,
    action: str | None = None,
    tool: str | None = None,
    retryable: bool = False,
) -> GraphState:
    """
    Build a standardized policy rejection.

    A rejection does not execute a tool.
    """

    result = {
        "allowed": False,
        "action": action,
        "tool": tool,
        "reason": reason,
        "retryable": retryable,
    }

    return {
        "policy_result": result,
        "policy_error": result,
        "tool_name": None,
    }


def _success(
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Build a standardized policy approval.
    """

    result = {
        "allowed": True,
        "action": action,
        "tool": tool,
    }

    return {
        "policy_result": result,
        "policy_error": None,
        "tool_name": tool,
    }


# =========================================================
# Completed Transaction Guard
# =========================================================

def _transaction_already_completed(
    state: GraphState,
) -> bool:
    """
    Determine whether this checkout already resulted in a
    successfully created order.

    This is the critical Phase 1 → Phase 2 duplicate-order
    protection.

    Example:

        Order created
            ↓
        user: "Thank you"
            ↓
        planner proposes ANSWER
            ↓
        allowed

    Even if the planner incorrectly proposes CREATE_ORDER,
    the policy layer prevents another transaction.
    """

    order_created = bool(
        state.get(
            "order_created",
            False,
        )
    )

    checkout_completed = bool(
        state.get(
            "checkout_completed",
            False,
        )
    )

    checkout_status = state.get(
        "checkout_status"
    )

    order_id = state.get(
        "order_id"
    )

    # The authoritative order_created flag is sufficient.
    if order_created:
        return True

    # A persisted order ID means an order already exists.
    if _has_value(order_id):
        return True

    # A terminal completed checkout should not be recreated.
    if (
        isinstance(
            checkout_status,
            str,
        )
        and checkout_status.strip().lower()
        in {
            "completed",
            "complete",
            "success",
            "successful",
        }
    ):
        return True

    if checkout_completed:
        return True

    return False


# =========================================================
# Checkout Readiness
# =========================================================

def _checkout_has_required_state(
    state: GraphState,
) -> tuple[bool, list[str]]:
    """
    Validate that the current GraphState contains the
    transaction fields required before CREATE_ORDER.

    This does NOT validate business facts such as:

        product exists
        stock is sufficient
        address belongs to user
        payment is currently available

    Those are backend responsibilities.
    """

    missing: list[str] = []

    if not _has_value(
        state.get(
            "product_id"
        )
    ):
        missing.append(
            "product_id"
        )

    if not _has_value(
        state.get(
            "quantity"
        )
    ):
        missing.append(
            "quantity"
        )

    address_id = state.get(
        "address_id"
    )

    selected_address_id = state.get(
        "selected_address_id"
    )

    if not (
        _has_value(address_id)
        or _has_value(
            selected_address_id
        )
    ):
        missing.append(
            "address_id"
        )

    payment_method = state.get(
        "selected_payment_method"
    )

    if not _has_value(
        payment_method
    ):
        payment_method = state.get(
            "payment_method"
        )

    if not _has_value(
        payment_method
    ):
        payment_method = state.get(
            "selected_payment_method_normalized"
        )

    if not _has_value(
        payment_method
    ):
        missing.append(
            "payment_method"
        )

    return (
        len(missing) == 0,
        missing,
    )


# =========================================================
# Validate Tool
# =========================================================

def _validate_tool(
    tool: Any,
) -> tuple[bool, str | None]:
    """
    Validate that the planner requested a tool supported by
    the application.

    The planner cannot invent arbitrary tool names.
    """

    if tool is None:
        return (
            True,
            None,
        )

    if not isinstance(
        tool,
        str,
    ):
        return (
            False,
            "invalid_tool",
        )

    tool = tool.strip()

    if not tool:
        return (
            True,
            None,
        )

    if tool not in SUPPORTED_TOOLS:
        return (
            False,
            "unsupported_tool",
        )

    return (
        True,
        tool,
    )


# =========================================================
# Validate CREATE_ORDER
# =========================================================

def _validate_create_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate an AI proposal to create an order.

    Only transaction-state readiness is checked here.

    Product availability, stock, price, payment validity,
    authorization and final billing remain backend
    responsibilities.
    """

    # -----------------------------------------------------
    # Duplicate transaction guard
    # -----------------------------------------------------

    if _transaction_already_completed(
        state
    ):
        return _failure(
            "checkout_already_completed",
            action=action,
            tool=tool,
            retryable=False,
        )

    # -----------------------------------------------------
    # Checkout ID
    # -----------------------------------------------------
    #
    # Durable idempotency requires a checkout ID.
    #
    # The Policy Node does not generate one.
    #
    # -----------------------------------------------------

    checkout_id = state.get(
        "checkout_id"
    )

    if not _has_value(
        checkout_id
    ):
        return _failure(
            "missing_checkout_id",
            action=action,
            tool=tool,
            retryable=True,
        )

    # -----------------------------------------------------
    # Required checkout state
    # -----------------------------------------------------

    ready, missing = (
        _checkout_has_required_state(
            state
        )
    )

    if not ready:
        return {
            "policy_result": {
                "allowed": False,
                "action": action,
                "tool": tool,
                "reason": "checkout_incomplete",
                "missing_fields": missing,
                "retryable": True,
            },
            "policy_error": {
                "allowed": False,
                "action": action,
                "tool": tool,
                "reason": "checkout_incomplete",
                "missing_fields": missing,
                "retryable": True,
            },
            "tool_name": None,
            "missing_fields": missing,
        }

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate TRACK_ORDER
# =========================================================

def _validate_track_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate tracking capability.

    The actual order ownership/status lookup remains a backend
    responsibility.
    """

    order_id = state.get(
        "order_id"
    )

    planned_arguments = state.get(
        "planned_arguments",
        {},
    )

    planned_order_id = None

    if isinstance(
        planned_arguments,
        dict,
    ):
        planned_order_id = (
            planned_arguments.get(
                "order_id"
            )
        )

    if not (
        _has_value(order_id)
        or _has_value(
            planned_order_id
        )
    ):
        return _failure(
            "missing_order_reference",
            action=action,
            tool=tool,
            retryable=True,
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate CANCEL_ORDER
# =========================================================

def _validate_cancel_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate that a cancellation request contains an order
    reference.

    Whether cancellation is actually allowed is determined
    by the backend/order service.
    """

    order_id = state.get(
        "order_id"
    )

    planned_arguments = state.get(
        "planned_arguments",
        {},
    )

    planned_order_id = None

    if isinstance(
        planned_arguments,
        dict,
    ):
        planned_order_id = (
            planned_arguments.get(
                "order_id"
            )
        )

    if not (
        _has_value(order_id)
        or _has_value(
            planned_order_id
        )
    ):
        return _failure(
            "missing_order_reference",
            action=action,
            tool=tool,
            retryable=True,
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate Generic Tool
# =========================================================

def _validate_generic_tool(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a normal backend capability.

    The actual business validation happens in the backend.
    """

    return _success(
        action,
        tool,
    )


# =========================================================
# Policy Node
# =========================================================

def policy_node(
    state: GraphState,
) -> GraphState:
    """
    Validate the AI Planner's proposed action.

    The policy node is deliberately deterministic.

    AI decides:
        What does the user want?

    Policy verifies:
        Is this proposed action permitted by the current
        application/transaction state?

    Backend decides:
        Is the actual operation valid?
    """

    planner_decision = state.get(
        "planner_decision",
        {},
    )

    if not isinstance(
        planner_decision,
        dict,
    ):
        return _failure(
            "missing_planner_decision"
        )

    action = planner_decision.get(
        "action"
    )

    if not isinstance(
        action,
        str,
    ):
        return _failure(
            "invalid_planner_action"
        )

    action = action.strip().upper()

    tool = planner_decision.get(
        "tool"
    )

    # =====================================================
    # Tool Validation
    # =====================================================

    valid_tool, normalized_tool = (
        _validate_tool(
            tool
        )
    )

    if not valid_tool:
        return _failure(
            "unsupported_tool",
            action=action,
            tool=(
                tool
                if isinstance(
                    tool,
                    str,
                )
                else None
            ),
            retryable=False,
        )

    tool = normalized_tool

    # =====================================================
    # Non-tool conversational action
    # =====================================================

    if action in NON_TOOL_ACTIONS:

        # -------------------------------------------------
        # Critical completed-order protection
        # -------------------------------------------------
        #
        # A conversational message after a completed order
        # is allowed to remain conversational.
        #
        # It must never be converted into create_order merely
        # because checkout information remains in state.
        #
        # -------------------------------------------------

        return _success(
            action,
            None,
        )

    # =====================================================
    # CREATE_ORDER
    # =====================================================

    if action == "CREATE_ORDER":

        # The planner must explicitly request the order tool.
        if tool != "create_order":
            return _failure(
                "create_order_requires_create_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_create_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # TRACK_ORDER
    # =====================================================

    if action == "TRACK_ORDER":

        if tool != "track_order":
            return _failure(
                "track_order_requires_track_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_track_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # CANCEL_ORDER
    # =====================================================

    if action == "CANCEL_ORDER":

        if tool != "cancel_order":
            return _failure(
                "cancel_order_requires_cancel_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_cancel_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # All Other Tool Actions
    # =====================================================

    if tool is None:
        return _failure(
            "tool_required_for_action",
            action=action,
            tool=None,
            retryable=False,
        )

    return _validate_generic_tool(
        state,
        action,
        tool,
    )
