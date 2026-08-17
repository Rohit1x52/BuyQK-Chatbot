"""
The Order model will:
Identify which user placed the order.
Store the delivery address.
Store the assigned rider.
Track the order status.
Store the total order amount.
Track payment status.
Store creation/update timestamps.
Connect the order to its OrderItem records.
Connect the order to its payment record.
Provide the database foundation for tracking and cancellation.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Order(Base):
    """
    Represents a customer order placed through BuyQK.
    """

    __tablename__ = "orders"

    # Unique identifier for the order
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # User who placed the order
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Delivery address selected for the order
    address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Rider assigned to deliver the order
    # Nullable because a newly created order
    # may not have a rider assigned yet.
    rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Current order status
    #
    # Possible MVP values:
    # pending
    # confirmed
    # packed
    # shipped
    # out_for_delivery
    # delivered
    # cancelled
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True
    )

    # Total monetary value of the order
    total_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )

    # Current payment status
    #
    # Possible MVP values:
    # pending
    # success
    # failed
    # refunded
    payment_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True
    )

    # Order creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Order last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with User
    user = relationship(
        "User",
        back_populates="orders"
    )

    # Relationship with Address
    address = relationship(
        "Address",
        back_populates="orders"
    )

    # Relationship with Rider
    rider = relationship(
        "Rider",
        back_populates="orders"
    )

    # Relationship with OrderItem
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    # Relationship with Payment
    payment = relationship(
        "Payment",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Support tickets linked to this order
    support_tickets = relationship(
        "SupportTicket",
        back_populates="order",
        cascade="all, delete-orphan"
    )