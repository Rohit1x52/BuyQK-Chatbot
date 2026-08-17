"""
The SupportTicket model will:
Identify the customer who created the ticket.
Optionally associate the ticket with an order.
Store the type of issue.
Store the customer's description.
Track ticket status.
Store an optional image/document reference.
Track when the ticket was created and updated.
Provide the foundation for human-agent escalation.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class SupportTicket(Base):
    """
    Represents a customer-support ticket created on BuyQK.
    """

    __tablename__ = "support_tickets"

    # Unique identifier for the support ticket
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # User who created the support ticket
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Optional order associated with the issue
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Type/category of support issue
    #
    # Examples:
    # order_issue
    # payment_issue
    # refund_issue
    # delivery_issue
    # missing_item
    # wrong_item
    # general
    issue_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    # Detailed description of the customer's issue
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Current support ticket status
    #
    # Possible MVP values:
    # open
    # in_progress
    # resolved
    # closed
    status: Mapped[str] = mapped_column(
        String(30),
        default="open",
        nullable=False,
        index=True
    )

    # Optional reference to an uploaded image/document
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    # Ticket creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Ticket last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with User
    user = relationship(
        "User",
        back_populates="support_tickets"
    )

    # Relationship with Order
    order = relationship(
        "Order",
        back_populates="support_tickets"
    )