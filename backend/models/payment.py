"""
The Payment model will:
Connect a payment to an order.
Store the payment transaction/reference ID.
Store the payment method.
Store the payment status.
Store the amount paid/attempted.
Record when the payment was created.
Record when the payment was last updated.
Support payment failure and refund tracking.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Payment(Base):
    """
    Represents a payment attempt/record for a BuyQK order.
    """

    __tablename__ = "payments"

    # Unique identifier for the payment record
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Order associated with this payment
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Transaction/reference ID returned by the payment system
    transaction_id: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        nullable=True,
        index=True
    )

    # Payment method
    # Examples:
    # UPI, Card, NetBanking, Cash
    payment_method: Mapped[str] = mapped_column(
        String(50),
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

    # Amount associated with this payment
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # Payment creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Payment last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with Order
    order = relationship(
        "Order",
        back_populates="payment"
    )