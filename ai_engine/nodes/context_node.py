# =========================================================
# BuyQK AI - Context Loader Node
# =========================================================
#
# Purpose:
# Build the contextual input required by the Phase 2 AI
# understanding/planning layer.
#
# Responsibilities:
#
#   - Collect current user message
#   - Collect relevant conversation history
#   - Collect current checkout state
#   - Collect current transaction state
#   - Collect resolved product information
#   - Collect address/payment selections
#   - Collect previous backend/tool results
#   - Collect order/billing state
#   - Collect Phase 1 task/memory state
#
# IMPORTANT:
#
# This node does NOT:
#
#   - decide intent
#   - select a tool
#   - create an order
#   - calculate billing
#   - modify database state
#   - invent missing information
#
# It only prepares context.
#
# The AI Understander and AI Planner consume this context.
#
# Authoritative backend values remain authoritative.
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Safe Value Helpers
# =========================================================


def _copy_dict(
    value: Any,
) -> dict[str, Any]:
    """
    Return a shallow copy of a dictionary.

    Prevents the context builder from accidentally mutating
    the original GraphState dictionary.
    """

    if not isinstance(
        value,
        dict,
    ):

        return {}

    return dict(
        value
    )


def _copy_list(
    value: Any,
) -> list[Any]:
    """
    Return a shallow copy of a list.
    """

    if not isinstance(
        value,
        list,
    ):

        return []

    return list(
        value
    )


# =========================================================
# Conversation Context
# =========================================================


def _build_conversation_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build conversational context.

    Conversation history is preserved because the AI may need
    it to resolve references such as:

        "that one"
        "make it five"
        "same address"
        "the other order"
    """

    return {
        "history": _copy_list(
            state.get(
                "conversation_history",
                [],
            )
        ),
    }


# =========================================================
# Phase 1 Task / Memory Context
# =========================================================


def _build_task_memory_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build the short-term conversational task state.

    This is the key Phase 1 addition.

    Example:

        active_task = "order_create"
        task_status = "collecting"

    This allows the AI to understand that:

        "Three"

    is likely a continuation of the active checkout rather
    than a brand-new unrelated request.
    """

    return {
        # -------------------------------------------------
        # Current conversational task
        # -------------------------------------------------

        "active_task": state.get(
            "active_task"
        ),

        # -------------------------------------------------
        # Task lifecycle
        # -------------------------------------------------

        "task_status": state.get(
            "task_status"
        ),

        # -------------------------------------------------
        # Missing information
        # -------------------------------------------------

        "missing_fields": _copy_list(
            state.get(
                "missing_fields",
                [],
            )
        ),

        # -------------------------------------------------
        # Selected product
        # -------------------------------------------------

        "selected_product": _copy_dict(
            state.get(
                "selected_product",
                {},
            )
        ),

        # -------------------------------------------------
        # Last execution result
        # -------------------------------------------------

        "execution_result": state.get(
            "execution_result"
        ),
    }


# =========================================================
# AI Understanding Context
# =========================================================


def _build_understanding_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Collect information already understood by previous AI
    processing.

    This allows later planner stages to use accumulated
    semantic information without reconstructing everything
    from the latest user message.
    """

    return {
        "intent": state.get(
            "intent"
        ),

        "user_goal": state.get(
            "user_goal"
        ),

        "detected_language": state.get(
            "detected_language"
        ),

        "entities": _copy_dict(
            state.get(
                "entities",
                {},
            )
        ),

        "references": _copy_dict(
            state.get(
                "references",
                {},
            )
        ),

        "missing_fields": _copy_list(
            state.get(
                "missing_fields",
                [],
            )
        ),

        # Phase 1 state
        "active_task": state.get(
            "active_task"
        ),

        "task_status": state.get(
            "task_status"
        ),

        "selected_product": _copy_dict(
            state.get(
                "selected_product",
                {},
            )
        ),

        "execution_result": state.get(
            "execution_result"
        ),
    }


# =========================================================
# Checkout Context
# =========================================================


def _build_checkout_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build the current checkout context.

    These values are already present in GraphState and should
    be treated as the current transaction state.

    The AI can understand these values but must not fabricate
    or override authoritative backend values.
    """

    return {
        "checkout_id": state.get(
            "checkout_id"
        ),

        "checkout_status": state.get(
            "checkout_status"
        ),

        "product_id": state.get(
            "product_id"
        ),

        "product_name": state.get(
            "product_name"
        ),

        "quantity": state.get(
            "quantity"
        ),

        "address_id": state.get(
            "address_id"
        ),

        "selected_address_id": state.get(
            "selected_address_id"
        ),

        "selected_payment_method": state.get(
            "selected_payment_method"
        ),

        "payment_method": state.get(
            "payment_method"
        ),

        "order_created": state.get(
            "order_created",
            False,
        ),

        "order_creation_attempted": state.get(
            "order_creation_attempted",
            False,
        ),

        "checkout_completed": state.get(
            "checkout_completed",
            False,
        ),

        "order_id": state.get(
            "order_id"
        ),

        "awaiting_order_tracking_confirmation": state.get(
            "awaiting_order_tracking_confirmation",
            False,
        ),
    }


# =========================================================
# Cart Context
# =========================================================


def _build_cart_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build backend-authoritative cart context.

    Cart values are copied from GraphState.

    No cart calculations are performed here.
    """

    return {
        "cart_id": state.get(
            "cart_id"
        ),

        "cart_status": state.get(
            "cart_status"
        ),

        "cart_items": _copy_list(
            state.get(
                "cart_items",
                [],
            )
        ),

        "cart_summary": _copy_dict(
            state.get(
                "cart_summary",
                {},
            )
        ),

        "cart_action": state.get(
            "cart_action"
        ),

        "cart_result": _copy_dict(
            state.get(
                "cart_result",
                {},
            )
        ),

        "cart_checkout_ready": state.get(
            "cart_checkout_ready",
            False,
        ),
    }


# =========================================================
# Backend / Tool Context
# =========================================================


def _build_backend_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build context from the latest backend/tool result.

    The tool result is authoritative when it represents a
    backend operation.

    The AI may interpret it but must not replace it with a
    generated value.
    """

    return {
        "tool_name": state.get(
            "tool_name"
        ),

        "tool_result": state.get(
            "tool_result"
        ),

        "execution_result": state.get(
            "execution_result"
        ),

        "transaction_error": _copy_dict(
            state.get(
                "transaction_error",
                {},
            )
        ),

        "policy_result": _copy_dict(
            state.get(
                "policy_result",
                {},
            )
        ),

        "policy_error": _copy_dict(
            state.get(
                "policy_error",
                {},
            )
        ),
    }


# =========================================================
# Billing Context
# =========================================================


def _build_billing_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build billing context from backend-authoritative state.

    No calculations are performed here.

    The values are copied exactly from GraphState.
    """

    billing = state.get(
        "billing",
        {},
    )

    bill = state.get(
        "bill",
        {},
    )

    return {
        "billing": _copy_dict(
            billing
        ),

        "bill": _copy_dict(
            bill
        ),

        "billing_items": _copy_list(
            state.get(
                "billing_items",
                [],
            )
        ),

        "subtotal": state.get(
            "subtotal"
        ),

        "delivery_charge": state.get(
            "delivery_charge"
        ),

        "discount": state.get(
            "discount"
        ),

        "tax": state.get(
            "tax"
        ),

        "total_amount": state.get(
            "total_amount"
        ),

        "currency": state.get(
            "currency"
        ),

        "billing_payment_method": state.get(
            "billing_payment_method"
        ),
    }


# =========================================================
# Build Complete Context
# =========================================================


def build_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Build the complete context object consumed by the
    Phase 2 AI Understander / Planner.

    The context is intentionally structured into separate
    domains so the AI can distinguish:

        conversational information
        task/memory state
        semantic understanding
        checkout state
        cart state
        backend results
        billing state

    No business decision is made here.
    """

    return {

        # -------------------------------------------------
        # Current user request
        # -------------------------------------------------

        "user": {
            "user_id": state.get(
                "user_id"
            ),

            "session_id": state.get(
                "session_id"
            ),

            "message": state.get(
                "message",
                "",
            ),
        },

        # -------------------------------------------------
        # Conversation
        # -------------------------------------------------

        "conversation": _build_conversation_context(
            state
        ),

        # -------------------------------------------------
        # Phase 1 task/memory
        # -------------------------------------------------

        "task_memory": _build_task_memory_context(
            state
        ),

        # -------------------------------------------------
        # AI understanding
        # -------------------------------------------------

        "understanding": _build_understanding_context(
            state
        ),

        # -------------------------------------------------
        # Checkout / transaction
        # -------------------------------------------------

        "checkout": _build_checkout_context(
            state
        ),

        # -------------------------------------------------
        # Cart
        # -------------------------------------------------

        "cart": _build_cart_context(
            state
        ),

        # -------------------------------------------------
        # Backend/tool information
        # -------------------------------------------------

        "backend": _build_backend_context(
            state
        ),

        # -------------------------------------------------
        # Billing
        # -------------------------------------------------

        "billing": _build_billing_context(
            state
        ),
    }


# =========================================================
# Context Node
# =========================================================


def context_node(
    state: GraphState,
) -> GraphState:
    """
    LangGraph node responsible for preparing contextual
    information.

    Input:
        GraphState

    Output:
        GraphState with `context` populated.

    This node deliberately performs no AI reasoning and no
    database mutation.
    """

    context = build_context(
        state
    )

    return {
        "context": context,
    }