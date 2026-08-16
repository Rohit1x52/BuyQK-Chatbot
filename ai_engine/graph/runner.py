# Purpose:
# Public entry point for executing the BuyQK AI graph.
#
# FastAPI
#    ↓
# run_chat()
#    ↓
# Load conversation memory
#    ↓
# LangGraph
#    ↓
# LLM + Tools + Backend
#    ↓
# Save conversation memory
#    ↓
# Response
#
# Conversation memory:
# Redis / in-memory fallback
#    ↓
# Short-term session context
#
# SQLite remains the persistent transactional database.


from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ai_engine.graph.builder import app
from ai_engine.memory.redis_memory import conversation_memory


# =========================================================
# Configuration
# =========================================================

# Number of previous messages provided to the graph.
#
# This prevents the LLM context from growing indefinitely
# during a long conversation.

MEMORY_MESSAGE_LIMIT = 10


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
) -> dict[str, Any]:
    """
    Execute the BuyQK AI graph with conversation memory.

    Args:
        message:
            User's natural-language message.

        session_id:
            Conversation/session identifier.

        user_id:
            Current BuyQK user ID.

        db:
            SQLAlchemy database session.

    Returns:
        Full GraphState dict containing intent, entities, response, and metadata.
    """

    # -----------------------------------------------------
    # Validate input
    # -----------------------------------------------------

    if not message or not message.strip():

        raise ValueError(
            "message is required."
        )

    if not session_id:

        raise ValueError(
            "session_id is required."
        )

    if user_id is None:

        raise ValueError(
            "user_id is required."
        )


    clean_message = message.strip()


    # =====================================================
    # Load Conversation History
    # =====================================================
    #
    # IMPORTANT:
    #
    # The current message is NOT added to history yet.
    #
    # The graph receives:
    #
    #     previous conversation
    #              +
    #        current message
    #
    # This allows the Entity Node to resolve references such
    # as:
    #
    # User: "I want Amul milk"
    # AI:   "How many packets?"
    # User: "3 packets"
    #
    # The graph can then understand:
    #
    # product_name = "Amul milk"
    # quantity     = 3
    # =====================================================

    conversation_history = (
        conversation_memory.get_recent_messages(
            session_id=session_id,
            limit=MEMORY_MESSAGE_LIMIT,
        )
    )


    # =====================================================
    # Restore Previous Entities
    # =====================================================
    #
    # Because GraphState is recreated on every request, we
    # restore the entity state from the last assistant message.
    # =====================================================

    previous_entities = {}

    if conversation_history:
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                previous_entities = msg.get("metadata", {}).get("entities", {})
                break


    # =====================================================
    # Initial Graph State
    # =====================================================

    initial_state: dict[str, Any] = {

        # -------------------------------------------------
        # Current user input
        # -------------------------------------------------

        "message": clean_message,

        "session_id": session_id,

        "user_id": user_id,

        "selected_address_id": (
            selected_address_id
        ),

        "payment_method": (
            payment_method
        ),


        # -------------------------------------------------
        # Previous conversation
        # -------------------------------------------------

        "conversation_history": conversation_history,


        # -------------------------------------------------
        # Database
        # -------------------------------------------------

        "db": db,


        # -------------------------------------------------
        # AI state
        # -------------------------------------------------

        "intent": None,

        "entities": previous_entities,

        "missing_fields": [],


        # -------------------------------------------------
        # Tool state
        # -------------------------------------------------

        "tool_name": None,

        "tool_result": None,


        # -------------------------------------------------
        # Final response
        # -------------------------------------------------

        "response": None,


        # -------------------------------------------------
        # Optional metadata
        # -------------------------------------------------

        "metadata": {},
    }


    # =====================================================
    # Execute LangGraph
    # =====================================================

    result = app.invoke(
        initial_state
    )


    # =====================================================
    # Extract Final Response
    # =====================================================

    response = result.get(
        "response"
    )


    if not response:

        raise RuntimeError(
            "BuyQK AI graph completed without a response."
        )


    # =====================================================
    # Save Current User Message
    # =====================================================
    #
    # We save AFTER successful graph execution.
    #
    # This prevents an incomplete/failed request from being
    # stored as a successful conversation turn.
    # =====================================================

    conversation_memory.add_message(
        session_id=session_id,
        role="user",
        content=clean_message,
    )


    # =====================================================
    # Save Assistant Response
    # =====================================================

    metadata = dict(result.get("metadata") or {})
    metadata["entities"] = result.get("entities", {})

    conversation_memory.add_message(
        session_id=session_id,
        role="assistant",
        content=response,
        metadata=metadata,
    )


    # =====================================================
    # Return Full GraphState
    # =====================================================

    return result