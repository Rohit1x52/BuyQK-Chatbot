"""
BuyQK Payment Model

The Payment model represents a payment attempt/record associated
with either an Order or a service Booking.

A payment must belong to exactly one commerce transaction:

    Order
       OR
    Booking

The model is intentionally shared between product commerce and
service commerce so that BuyQK does not maintain two independent
payment architectures.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Payment(Base):
    """
    Represents a payment attempt/record for a BuyQK transaction.

    A Payment may belong to:

        - an Order
        - a Booking

    but never both and never neither.
    """

    __tablename__ = "payments"

    # =========================================================
    # Database Constraints
    # =========================================================

    __table_args__ = (
        CheckConstraint(
            """
            (
                order_id IS NOT NULL
                AND booking_id IS NULL
            )
            OR
            (
                order_id IS NULL
                AND booking_id IS NOT NULL
            )
            """,
            name="ck_payment_exactly_one_parent",
        ),
    )

    # =========================================================
    # Primary Key
    # =========================================================

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # =========================================================
    # Order
    # =========================================================

    # Existing product-commerce payment relationship.
    #
    # Nullable because a payment may now belong to a Booking
    # instead of an Order.

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        unique=True,
        index=True,
    )

    # =========================================================
    # Booking
    # =========================================================

    # Service-commerce payment relationship.
    #
    # Nullable because a payment may belong to an Order instead.

    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "bookings.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        unique=True,
        index=True,
    )

    # =========================================================
    # Transaction
    # =========================================================

    # Transaction/reference ID returned by the payment system.

    transaction_id: Mapped[str | None] = mapped_column(
        String(150),
        unique=True,
        nullable=True,
        index=True,
    )

    # =========================================================
    # Payment Method
    # =========================================================

    # Examples:
    #
    #     UPI
    #     Card
    #     NetBanking
    #     Cash

    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # =========================================================
    # Payment Status
    # =========================================================

    # MVP values:
    #
    #     pending
    #     success
    #     failed
    #     refunded
    #
    # Existing order-payment semantics are preserved.

    payment_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )

    # =========================================================
    # Amount
    # =========================================================

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # =========================================================
    # Timestamps
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # =========================================================
    # Relationships
    # =========================================================

    order = relationship(
        "Order",
        back_populates="payment",
    )

    booking = relationship(
        "Booking",
        back_populates="payment",
    )