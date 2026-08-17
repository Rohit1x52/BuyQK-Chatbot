"""
support_ticket_schema.py will:
Validate support-ticket creation requests.
Identify the issue type.
Store the customer's issue description.
Optionally associate the issue with an order.
Accept an optional image/document reference.
Return the ticket ID and status.
Prevent the client/AI from directly controlling the ticket status.
Provide a clean API contract for future human-agent escalation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SupportTicketCreate(BaseModel):
    """
    Schema used when creating a new support ticket.

    The user_id and ticket status are intentionally not accepted
    from the client. They should be determined by the backend.
    """

    # Optional order associated with the support issue
    order_id: int | None = Field(
        default=None,
        gt=0
    )

    # Type of support issue
    #
    # Examples:
    # order_issue
    # payment_issue
    # refund_issue
    # delivery_issue
    # missing_item
    # wrong_item
    # general
    issue_type: str = Field(
        ...,
        min_length=2,
        max_length=50
    )

    # Customer's description of the problem
    description: str = Field(
        ...,
        min_length=5,
        max_length=5000
    )

    # Optional image/document reference
    image_url: str | None = Field(
        default=None,
        max_length=500
    )


class SupportTicketResponse(BaseModel):
    """
    Schema returned by the API after retrieving
    or creating a support ticket.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Support ticket ID
    id: int

    # User who created the ticket
    user_id: int

    # Associated order, if applicable
    order_id: int | None

    # Issue category
    issue_type: str

    # Customer's issue description
    description: str

    # Current ticket status
    status: str

    # Optional supporting image/document
    image_url: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime