"""
BuyQK AI - Chat API Schemas

The schema validates the public HTTP contract only.
It does not contain LangGraph or transaction business logic.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """
    Schema for a message sent to the BuyQK AI assistant.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    user_id: int = Field(
        ...,
        gt=0,
    )

    # --------------------------------------------------------
    # Commerce Vertical
    # --------------------------------------------------------
    #
    # Optional frontend context.
    #
    # The frontend may provide a known commerce vertical,
    # but the API does not infer or validate the business
    # meaning of this value.
    #
    # Examples:
    #
    #     grocery
    #     food
    #     medicine
    #     electronics
    #
    # The graph remains responsible for semantic understanding.
    #
    # --------------------------------------------------------

    commerce_vertical: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    # --------------------------------------------------------
    # Active checkout
    # --------------------------------------------------------
    #
    # This is supplied only when the frontend already has
    # a backend-created checkout.
    #
    # The API/graph remain authoritative.
    # The frontend does not create this value.
    #
    checkout_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    # --------------------------------------------------------
    # Address
    # --------------------------------------------------------

    selected_address_id: int | None = Field(
        default=None,
        gt=0,
    )

    # --------------------------------------------------------
    # Payment
    # --------------------------------------------------------

    payment_method: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class ChatResponse(BaseModel):
    """
    Schema returned by the BuyQK AI assistant.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    response: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )