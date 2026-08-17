"""
chat_schema.py will:
Validate incoming chat messages.
Identify the user/session associated with the conversation.
Carry optional conversation context.
Return the assistant's response.
Return the session ID so the frontend can continue the same conversation.
Return detected intent when available.
Return structured metadata that the frontend can optionally use.
Keep the API contract independent of the internal LangGraph state.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """
    Schema for a message sent by the user to the BuyQK AI assistant.
    """

    # User's message
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000
    )

    # Existing conversation session.
    session_id: str = Field(
        max_length=100
    )

    # ID of the user sending the message
    user_id: int

    # Optional saved address selected by the frontend.
    # When provided, the graph can deterministically use
    # this value as entities["address_id"].
    selected_address_id: int | None = None

    # Optional payment method selected by the frontend.
    payment_method: str | None = None


class ChatResponse(BaseModel):
    """
    Schema returned by the BuyQK AI assistant.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # AI-generated response
    response: str

    # Optional structured metadata.
    #
    # Examples:
    # {
    #     "products": [...],
    #     "order_id": 101,
    #     "ticket_id": 501
    # }
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )