"""
The Order model will:

- Identify which user placed the order.
- Store the delivery address.
- Store the assigned rider.
- Track the order status.
- Store the total order amount.
- Track payment status.
- Store creation/update timestamps.
- Identify the checkout transaction that created the order.
- Connect the order to its OrderItem records.
- Connect the order to its payment record.
- Provide the database foundation for tracking and cancellation.

IMPORTANT:

checkout_id is the transaction/idempotency identifier.

One user + one checkout_id = one order.

This prevents the same checkout from accidentally creating
multiple orders when the same request is processed more than once.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.database.base import Base


class Order(Base):
    """
    Represents a customer order placed through BuyQK.
    """

    __tablename__ = "orders"

    # =========================================================
    # Database Constraints
    # =========================================================

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "checkout_id",
            name="uq_orders_user_checkout",
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
    # User
    # =========================================================

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Checkout / Idempotency
    # =========================================================

    # Unique transaction identifier for the checkout flow.
    #
    # Existing legacy orders may have NULL here.
    # New checkout-created orders should always provide it.

    checkout_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Delivery Address
    # =========================================================

    address_id: Mapped[int] = mapped_column(
        ForeignKey(
            "addresses.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Rider
    # =========================================================

    rider_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "riders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Order Status
    # =========================================================

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )

    # =========================================================
    # Order Total
    # =========================================================

    total_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =========================================================
    # Payment Status
    # =========================================================

    payment_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
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

    user = relationship(
        "User",
        back_populates="orders",
    )

    address = relationship(
        "Address",
        back_populates="orders",
    )

    rider = relationship(
        "Rider",
        back_populates="orders",
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    payment = relationship(
        "Payment",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )

    support_tickets = relationship(
        "SupportTicket",
        back_populates="order",
        cascade="all, delete-orphan",
    )