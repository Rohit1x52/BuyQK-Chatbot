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
#
# IMPORTANT
#
# The runner must NOT make business decisions.
#
# It only:
#
#     - loads conversation context
#     - restores graph state
#     - injects current request data
#     - executes LangGraph
#     - persists resulting conversational state
#
#
# The AI/nodes decide:
#
#     - intent
#     - entities
#     - user's goal
#     - next conversational action
#
#
# The backend decides:
#
#     - prices
#     - stock
#     - payment validity
#     - order ID
#     - order status
#     - billing
#     - transaction success/failure
#
# =========================================================


from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from ai_engine.graph.builder import app
from ai_engine.memory.redis_memory import conversation_memory


# =========================================================
# Configuration
# =========================================================

MEMORY_MESSAGE_LIMIT = 10


# =========================================================
# State Fields
# =========================================================
#
# These fields represent conversational/transaction state
# that may need to survive between requests.
#
# The runner does NOT decide their values.
#
# It merely restores values that were previously produced by
# the graph/backend.
#
# =========================================================

PERSISTED_STATE_FIELDS = (
    # -----------------------------------------------------
    # Checkout
    # -----------------------------------------------------

    "checkout_id",
    "checkout_status",
    "order_created",
    "order_id",

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    "product_id",
    "product_name",
    "quantity",

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    "address_id",

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    "selected_payment_method",
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
    # Transaction/tool state
    # -----------------------------------------------------

    "tool_name",
    "tool_result",

    # -----------------------------------------------------
    # Planner/context state
    # -----------------------------------------------------

    "context",
    "planner",
    "planner_args",
    "policy",
    "decision",
    "tool_args",

    # -----------------------------------------------------
    # Tracking
    # -----------------------------------------------------

    "awaiting_order_tracking_confirmation",
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
        # Entities
        # -------------------------------------------------
        #
        # Entity state is separately persisted because it is
        # the accumulated conversational understanding.
        #
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

    The previous state is restored first.

    Current request data is then applied on top.

    Frontend-authoritative selections always belong to the
    current request and therefore override the corresponding
    previous selection when explicitly provided.
    """

    # =====================================================
    # Start with restored state
    # =====================================================

    state: dict[str, Any] = deepcopy(
        previous_state
    )

    # =====================================================
    # Current Frontend Checkout Selection
    # =====================================================

    if checkout_id is not None and str(checkout_id).strip():
        state["checkout_id"] = str(checkout_id).strip()

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
    # Conversation
    # =====================================================

    state[
        "conversation_history"
    ] = conversation_history

    # =====================================================
    # Entities
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
    # None means the frontend did not provide a new
    # selection.
    #
    # We therefore do not erase the existing conversational
    # value.
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
    # These fields describe the current graph execution.
    #
    # The previous transaction result remains available in
    # the restored state, but the current execution starts
    # without assuming that a tool has already run.
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
    # Metadata
    # =====================================================

    state[
        "metadata"
    ] = {}

    return state


# =========================================================
# Persistable State
# =========================================================


def _build_memory_metadata(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert the final graph state into short-term conversation
    memory metadata.

    Only serializable graph information should be stored.

    The database remains the source of truth for durable
    transactional information.
    """

    metadata: dict[str, Any] = {}

    # =====================================================
    # Graph State
    # =====================================================

    for field in PERSISTED_STATE_FIELDS:

        if field not in result:
            continue

        value = result.get(
            field
        )

        # -------------------------------------------------
        # Skip database session objects.
        # -------------------------------------------------

        if field == "db":
            continue

        metadata[
            field
        ] = deepcopy(
            value
        )

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

    if "next_missing" in result:

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
    Execute the BuyQK Phase-2 AI graph.

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

    if not isinstance(
        message,
        str,
    ) or not message.strip():

        raise ValueError(
            "message is required."
        )

    # =====================================================
    # Validate Session
    # =====================================================

    if not isinstance(
        session_id,
        str,
    ) or not session_id.strip():

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
    # Current message is deliberately NOT stored before the
    # graph executes.
    #
    # The graph therefore receives:
    #
    #     previous conversation
    #             +
    #        current message
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
    # Extract Response
    # =====================================================

    response = result.get(
        "response"
    )

    if not isinstance(
        response,
        str,
    ) or not response.strip():

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