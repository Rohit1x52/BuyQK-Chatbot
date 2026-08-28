# =========================================================
# BuyQK AI - Graph Runner
# =========================================================
#
# Purpose:
# Public entry point for executing the BuyQK AI graph.
#
#
# FastAPI
#    ↓
# run_chat()
#    ↓
# Load conversation memory
#    ↓
# Restore persistent conversation state
#    ↓
# Build GraphState
#    ↓
# LangGraph
#    ↓
# Context
#    ↓
# Intent
#    ↓
# Entity
#    ↓
# Planner
#    ↓
# Policy
#    ↓
# Decision
#    ↓
# Tool
#    ↓
# Response
#    ↓
# Save conversation state
#    ↓
# Response
#
# =========================================================
#
# MEMORY ARCHITECTURE
#
# Redis / in-memory memory:
#
#     Short-term conversational state
#
# SQLite:
#
#     Authoritative transactional state
#
# =========================================================


from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from ai_engine.graph.builder import app
from ai_engine.memory.redis_memory import conversation_memory
from ai_engine.tools.results import ToolResult


# =========================================================
# Configuration
# =========================================================

MEMORY_MESSAGE_LIMIT = 10


# =========================================================
# Persisted Graph State
# =========================================================
#
# These fields survive between HTTP requests.
#
# The runner does not calculate them.
# It only restores values that the graph previously produced.
#
# =========================================================

PERSISTED_STATE_FIELDS = (
    # -----------------------------------------------------
    # Checkout
    # -----------------------------------------------------

    "checkout_id",
    "checkout_status",
    "order_created",
    "order_creation_attempted",
    "checkout_completed",
    "order_id",

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    "product_id",
    "product_name",
    "quantity",
    "selected_product",

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    "address_id",
    "selected_address_id",

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    "selected_payment_method",
    "payment_method",
    "billing_payment_method",

    # -----------------------------------------------------
    # Billing
    # -----------------------------------------------------

    "bill",
    "billing",
    "billing_items",

    "subtotal",
    "delivery_charge",
    "discount",
    "tax",
    "total_amount",
    "currency",

    # -----------------------------------------------------
    # Transaction / Tool
    # -----------------------------------------------------

    "tool_name",
    "execution_result",

    # -----------------------------------------------------
    # Planner / Context
    # -----------------------------------------------------

    "context",
    "planner",
    "planner_args",
    "planner_decision",
    "planned_action",
    "planned_tool",
    "planned_arguments",
    "planner_confidence",

    # -----------------------------------------------------
    # Policy / Decision
    # -----------------------------------------------------

    "policy_result",
    "policy_error",
    "policy",
    "decision",
    "decision_route",

    # -----------------------------------------------------
    # Tool arguments
    # -----------------------------------------------------

    "tool_args",

    # -----------------------------------------------------
    # Tracking
    # -----------------------------------------------------

    "awaiting_order_tracking_confirmation",

    # -----------------------------------------------------
    # Phase 1 conversation/task memory
    # -----------------------------------------------------

    "active_task",
    "task_status",

    # -----------------------------------------------------
    # Phase 2 follow-up state
    # -----------------------------------------------------

    "current_missing_field",
    "follow_up_question",
    "awaiting_user_input",
    "next_missing",

    # -----------------------------------------------------
    # AI understanding
    # -----------------------------------------------------

    "user_goal",
    "detected_language",
    "references",

    # -----------------------------------------------------
    # Order request
    # -----------------------------------------------------

    "order_items",

    # -----------------------------------------------------
    # Cart state
    # -----------------------------------------------------

    "cart_id",
    "cart_status",
    "cart_items",
    "cart_summary",
    "cart_action",
    "cart_result",
    "cart_checkout_ready",

    # -----------------------------------------------------
    # Transaction error
    # -----------------------------------------------------

    "transaction_error",
)


# =========================================================
# Utility Functions
# =========================================================


def _safe_dict(
    value: Any,
) -> dict[str, Any]:
    """
    Return a defensive dictionary copy.

    Prevents accidental mutation of memory objects.
    """

    if not isinstance(
        value,
        dict,
    ):
        return {}

    return deepcopy(
        value
    )


def _safe_list(
    value: Any,
) -> list[Any]:
    """
    Return a defensive list copy.
    """

    if not isinstance(
        value,
        list,
    ):
        return []

    return deepcopy(
        value
    )


def _extract_message_metadata(
    message: Any,
) -> dict[str, Any]:
    """
    Extract metadata from a stored conversation message.
    """

    if not isinstance(
        message,
        dict,
    ):
        return {}

    metadata = message.get(
        "metadata"
    )

    return _safe_dict(
        metadata
    )


# =========================================================
# Restore Previous Graph State
# =========================================================


def _restore_previous_state(
    conversation_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Restore the most recent graph state stored in conversation
    memory.

    The assistant message metadata is used as the short-term
    graph-state snapshot.

    SQLite remains authoritative for transactional facts.

    This function does NOT calculate or infer state.
    """

    if not conversation_history:
        return {}

    # -----------------------------------------------------
    # Find the most recent assistant message.
    # -----------------------------------------------------

    for message in reversed(
        conversation_history
    ):

        if not isinstance(
            message,
            dict,
        ):
            continue

        if message.get(
            "role"
        ) != "assistant":
            continue

        metadata = _extract_message_metadata(
            message
        )

        if not metadata:
            continue

        restored: dict[str, Any] = {}

        # -------------------------------------------------
        # Direct persisted fields
        # -------------------------------------------------

        for field in PERSISTED_STATE_FIELDS:

            if field in metadata:

                restored[field] = deepcopy(
                    metadata[field]
                )

        # -------------------------------------------------
        # Entity state
        # -------------------------------------------------

        entities = metadata.get(
            "entities"
        )

        if isinstance(
            entities,
            dict,
        ):

            restored[
                "entities"
            ] = deepcopy(
                entities
            )

        # -------------------------------------------------
        # Missing fields
        # -------------------------------------------------

        missing_fields = metadata.get(
            "missing_fields"
        )

        if isinstance(
            missing_fields,
            list,
        ):

            restored[
                "missing_fields"
            ] = deepcopy(
                missing_fields
            )

        # -------------------------------------------------
        # Next missing field
        # -------------------------------------------------

        if (
            "next_missing"
            in metadata
        ):

            restored[
                "next_missing"
            ] = metadata[
                "next_missing"
            ]

        # -------------------------------------------------
        # Frontend metadata
        # -------------------------------------------------

        frontend_metadata = metadata.get(
            "frontend_metadata"
        )

        if isinstance(
            frontend_metadata,
            dict,
        ):

            restored[
                "frontend_metadata"
            ] = deepcopy(
                frontend_metadata
            )

        return restored

    return {}


# =========================================================
# Build Initial State
# =========================================================


def _build_initial_state(
    *,
    message: str,
    session_id: str,
    user_id: int,
    db: Session,
    conversation_history: list[dict[str, Any]],
    previous_state: dict[str, Any],
    selected_address_id: int | None,
    payment_method: str | None,
    checkout_id: str | None,
) -> dict[str, Any]:
    """
    Build the GraphState for the current request.

    Previous state is restored first.

    Current request data is then applied on top.

    Frontend-authoritative selections override previous
    selections only when explicitly supplied.
    """

    # =====================================================
    # Start with restored state
    # =====================================================

    state: dict[str, Any] = deepcopy(
        previous_state
    )

    # =====================================================
    # Current Checkout ID
    # =====================================================

    if (
        checkout_id is not None
        and str(checkout_id).strip()
    ):

        state[
            "checkout_id"
        ] = str(
            checkout_id
        ).strip()

    # =====================================================
    # Current User Input
    # =====================================================

    state[
        "message"
    ] = message

    state[
        "session_id"
    ] = session_id

    state[
        "user_id"
    ] = user_id

    # =====================================================
    # Database
    # =====================================================

    state[
        "db"
    ] = db

    # =====================================================
    # Conversation History
    # =====================================================

    state[
        "conversation_history"
    ] = conversation_history

    # =====================================================
    # Entity State
    # =====================================================

    state[
        "entities"
    ] = _safe_dict(
        state.get(
            "entities",
            {},
        )
    )

    # =====================================================
    # Current Frontend Address Selection
    # =====================================================
    #
    # None means the frontend did not provide a new selection.
    #
    # Therefore an existing address is not erased.
    #
    # =====================================================

    if selected_address_id is not None:

        state[
            "selected_address_id"
        ] = selected_address_id

        state[
            "address_id"
        ] = selected_address_id

    # =====================================================
    # Current Frontend Payment Selection
    # =====================================================

    if (
        payment_method is not None
        and str(
            payment_method
        ).strip()
    ):

        clean_payment_method = str(
            payment_method
        ).strip()

        state[
            "payment_method"
        ] = clean_payment_method

        state[
            "selected_payment_method"
        ] = clean_payment_method

    # =====================================================
    # Current Request Tool State
    # =====================================================
    #
    # A previous tool result is still available through
    # execution_result.
    #
    # But the current request starts without pretending that
    # a new tool has already executed.
    #
    # =====================================================

    state[
        "tool_name"
    ] = None

    state[
        "tool_args"
    ] = {}

    state[
        "tool_result"
    ] = None

    state[
        "response"
    ] = None

    # =====================================================
    # Current Graph Metadata
    # =====================================================

    state[
        "metadata"
    ] = {}

    # =====================================================
    # Phase 1 defaults
    # =====================================================
    #
    # setdefault() is intentional.
    #
    # Existing state is preserved.
    # New sessions receive sensible defaults.
    #
    # =====================================================

    state.setdefault(
        "active_task",
        None,
    )

    state.setdefault(
        "task_status",
        "idle",
    )

    state.setdefault(
        "execution_result",
        None,
    )

    state.setdefault(
        "selected_product",
        None,
    )

    state.setdefault(
        "missing_fields",
        [],
    )

    state.setdefault(
        "current_missing_field",
        None,
    )

    state.setdefault(
        "follow_up_question",
        None,
    )

    state.setdefault(
        "awaiting_user_input",
        False,
    )

    state.setdefault(
        "next_missing",
        None,
    )

    state.setdefault(
        "entities",
        {},
    )

    state.setdefault(
        "order_created",
        False,
    )

    state.setdefault(
        "order_creation_attempted",
        False,
    )

    state.setdefault(
        "checkout_completed",
        False,
    )

    state.setdefault(
        "cart_items",
        [],
    )

    state.setdefault(
        "order_items",
        [],
    )

    state.setdefault(
        "references",
        {},
    )

    return state


# =========================================================
# Build Memory Metadata
# =========================================================


def _build_memory_metadata(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert final graph state into serializable short-term
    conversation memory metadata.

    Only conversational/serializable graph information is stored.

    Database session objects are never persisted.
    """

    metadata: dict[str, Any] = {}

    # =====================================================
    # Persist Graph State
    # =====================================================

    for field in PERSISTED_STATE_FIELDS:

        if field not in result:
            continue

        value = result.get(
            field
        )

        # -------------------------------------------------
        # Never persist DB sessions.
        # -------------------------------------------------

        if field == "db":
            continue

        try:
            # ToolResult is the canonical in-graph contract, but conversation
            # memory must receive JSON-safe data.
            if isinstance(value, ToolResult):
                metadata[
                    field
                ] = value.to_dict()
            else:
                metadata[
                    field
                ] = deepcopy(
                    value
                )

        except Exception:

            # A single unserializable optional field must not
            # prevent the entire conversational state from
            # being persisted.
            continue

    # =====================================================
    # Entity State
    # =====================================================

    metadata[
        "entities"
    ] = _safe_dict(
        result.get(
            "entities",
            {},
        )
    )

    # =====================================================
    # Missing Fields
    # =====================================================

    metadata[
        "missing_fields"
    ] = _safe_list(
        result.get(
            "missing_fields",
            [],
        )
    )

    # =====================================================
    # Next Missing
    # =====================================================

    if (
        "next_missing"
        in result
    ):

        metadata[
            "next_missing"
        ] = result.get(
            "next_missing"
        )

    # =====================================================
    # Frontend Metadata
    # =====================================================

    frontend_metadata = result.get(
        "metadata"
    )

    if isinstance(
        frontend_metadata,
        dict,
    ):

        metadata[
            "frontend_metadata"
        ] = deepcopy(
            frontend_metadata
        )

    return metadata


# =========================================================
# Phase 1 Conversation-State Bookkeeping
# =========================================================


def _update_conversation_state(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Update short-term task state from the already-produced
    graph result.

    IMPORTANT:

    This function does NOT run another intent classifier.

    It only records the outcome of the graph so the next
    HTTP turn can resume from the same conversational state.
    """

    # GraphState can contain request-scoped infrastructure objects such as
    # a live SQLAlchemy Session.  Do not deepcopy the whole graph state.
    # Copy only the top-level mapping; individual serializable values are
    # copied when they are actually persisted or reused below.
    updated = dict(result)

    # =====================================================
    # Read Graph Output
    # =====================================================

    intent = str(
        updated.get(
            "intent"
        )
        or ""
    ).strip().lower()

    planner = updated.get(
        "planner"
    )

    if not isinstance(
        planner,
        dict,
    ):

        planner = {}

    action = str(
        planner.get(
            "action"
        )
        or ""
    ).strip().lower()

    missing = updated.get(
        "missing_fields"
    )

    if not isinstance(
        missing,
        list,
    ):

        missing = []

    order_created = bool(
        updated.get(
            "order_created",
            False,
        )
    )

    checkout_completed = bool(
        updated.get(
            "checkout_completed",
            False,
        )
    )

    tool_result = updated.get(
        "tool_result"
    )

    transaction_error = updated.get(
        "transaction_error"
    )

    # =====================================================
    # Active Task
    # =====================================================
    #
    # The graph's current intent is authoritative.
    #
    # We do not independently classify the message here.
    #
    # =====================================================

    if (
        intent
        and intent != "general"
    ):

        updated[
            "active_task"
        ] = intent

    elif action in {
        "answer",
        "end_conversation",
    }:

        # Preserve an already active task unless the graph
        # explicitly finished it.
        if (
            not updated.get(
                "active_task"
            )
        ):

            updated[
                "active_task"
            ] = None

    # =====================================================
    # Task Status
    # =====================================================

    if (
        order_created
        or checkout_completed
    ):

        updated[
            "task_status"
        ] = "completed"

    elif transaction_error:

        updated[
            "task_status"
        ] = "failed"

    elif missing:

        updated[
            "task_status"
        ] = "collecting"

    elif (
        tool_result is not None
        or action
        not in {
            "",
            "answer",
            "ask_clarification",
        }
    ):

        updated[
            "task_status"
        ] = "executing"

    elif (
        intent
        and intent != "general"
    ):

        updated[
            "task_status"
        ] = "active"

    else:

        updated[
            "task_status"
        ] = "idle"

    # =====================================================
    # Execution Result
    # =====================================================
    #
    # This is the latest result from actual graph execution.
    #
    # It is not an LLM-generated replacement for backend
    # authority.
    #
    # =====================================================

    try:
        updated[
            "execution_result"
        ] = deepcopy(tool_result)
    except Exception:
        updated[
            "execution_result"
        ] = tool_result

    # =====================================================
    # Selected Product
    # =====================================================
    #
    # Keep a convenient conversational product reference.
    #
    # Never invent a product ID.
    #
    # =====================================================

    product_id = updated.get(
        "product_id"
    )

    product_name = updated.get(
        "product_name"
    )

    if (
        product_id is not None
        or (
            isinstance(
                product_name,
                str,
            )
            and product_name.strip()
        )
    ):

        selected_product: dict[str, Any] = {}

        if product_id is not None:

            try:
                selected_product[
                    "product_id"
                ] = deepcopy(product_id)
            except Exception:
                selected_product[
                    "product_id"
                ] = product_id

        if (
            isinstance(
                product_name,
                str,
            )
            and product_name.strip()
        ):

            selected_product[
                "product_name"
            ] = product_name.strip()

        updated[
            "selected_product"
        ] = selected_product

    # =====================================================
    # Keep Missing Fields Canonical
    # =====================================================

    updated[
        "missing_fields"
    ] = list(
        missing
    )

    return updated


# =========================================================
# Run Chat
# =========================================================


def run_chat(
    message: str,
    session_id: str,
    user_id: int,
    db: Session,
    selected_address_id: int | None = None,
    payment_method: str | None = None,
    checkout_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute the BuyQK AI graph.

    ========================================================
    INPUT
    ========================================================

    Current user message plus optional frontend-authoritative
    checkout selections.

    ========================================================
    MEMORY
    ========================================================

    Previous short-term conversation context is loaded from
    conversation_memory.

    ========================================================
    GRAPH
    ========================================================

    Context
        ↓
    Intent
        ↓
    Entity
        ↓
    Planner
        ↓
    Policy
        ↓
    Decision
        ↓
    Tool
        ↓
    Response

    ========================================================
    OUTPUT
    ========================================================

    Full resulting GraphState.

    ========================================================
    """

    # =====================================================
    # Validate Message
    # =====================================================

    if (
        not isinstance(
            message,
            str,
        )
        or not message.strip()
    ):

        raise ValueError(
            "message is required."
        )

    # =====================================================
    # Validate Session
    # =====================================================

    if (
        not isinstance(
            session_id,
            str,
        )
        or not session_id.strip()
    ):

        raise ValueError(
            "session_id is required."
        )

    # =====================================================
    # Validate User
    # =====================================================

    if user_id is None:

        raise ValueError(
            "user_id is required."
        )

    # =====================================================
    # Clean Input
    # =====================================================

    clean_message = message.strip()

    clean_session_id = (
        session_id.strip()
    )

    # =====================================================
    # Load Conversation History
    # =====================================================
    #
    # IMPORTANT:
    #
    # Current user message is NOT saved before graph
    # execution.
    #
    # Therefore the graph receives:
    #
    #     previous history
    #             +
    #     current message
    #
    # This prevents the current message from being duplicated
    # inside the graph's conversation history.
    #
    # =====================================================

    conversation_history = (
        conversation_memory.get_recent_messages(
            session_id=clean_session_id,
            limit=MEMORY_MESSAGE_LIMIT,
        )
    )

    conversation_history = _safe_list(
        conversation_history
    )

    # =====================================================
    # Restore Previous State
    # =====================================================

    previous_state = (
        _restore_previous_state(
            conversation_history
        )
    )

    # =====================================================
    # Build Current Graph State
    # =====================================================

    initial_state = _build_initial_state(
        message=clean_message,
        session_id=clean_session_id,
        user_id=user_id,
        db=db,
        conversation_history=conversation_history,
        previous_state=previous_state,
        selected_address_id=selected_address_id,
        payment_method=payment_method,
        checkout_id=checkout_id,
    )

    # =====================================================
    # Execute Graph
    # =====================================================

    result = app.invoke(
        initial_state
    )

    # =====================================================
    # Validate ToolResult Contract
    # =====================================================

    tool_result = (
        result.get("tool_result")
        if isinstance(result, dict)
        else None
    )

    if (
        tool_result is not None
        and not isinstance(tool_result, ToolResult)
    ):
        raise RuntimeError(
            "Graph produced an invalid tool_result. "
            "Expected ToolResult, got "
            f"{type(tool_result).__name__}."
        )

    # =====================================================
    # Validate Result
    # =====================================================

    if not isinstance(
        result,
        dict,
    ):

        raise RuntimeError(
            "BuyQK AI graph returned an invalid state."
        )

    # =====================================================
    # Phase 1 Conversation-State Update
    # =====================================================

    result = _update_conversation_state(
        result
    )

    # =====================================================
    # Extract Response
    # =====================================================

    response = result.get(
        "response"
    )

    if (
        not isinstance(
            response,
            str,
        )
        or not response.strip()
    ):

        raise RuntimeError(
            "BuyQK AI graph completed without a response."
        )

    response = response.strip()

    # =====================================================
    # Build Memory Metadata
    # =====================================================

    memory_metadata = (
        _build_memory_metadata(
            result
        )
    )

    # =====================================================
    # Save User Message
    # =====================================================
    #
    # Only save after successful graph execution.
    #
    # =====================================================

    conversation_memory.add_message(
        session_id=clean_session_id,
        role="user",
        content=clean_message,
    )

    # =====================================================
    # Save Assistant Message
    # =====================================================
    #
    # The assistant message contains:
    #
    #     response
    #     +
    #     complete short-term state snapshot
    #
    # The next request restores this metadata.
    #
    # =====================================================

    conversation_memory.add_message(
        session_id=clean_session_id,
        role="assistant",
        content=response,
        metadata=memory_metadata,
    )

    # =====================================================
    # Return Graph State
    # =====================================================

    return result