from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.database.base import Base


class Cart(Base):
    """
    Represents the active shopping cart of a BuyQK user.

    A Cart is separate from an Order.

    Cart:
        - represents the user's current shopping state
        - can be modified repeatedly
        - contains CartItem records
        - is used to prepare checkout

    Order:
        - represents a completed transactional purchase
        - contains immutable OrderItem price snapshots
        - is created only after checkout succeeds
    """

    __tablename__ = "carts"

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

    # User who owns this cart.
    #
    # A user's cart must belong to an existing user.
    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Cart Status
    # =========================================================

    # Current lifecycle state of the cart.
    #
    # The service layer is responsible for determining valid
    # state transitions.
    #
    # Typical lifecycle:
    #
    #     active
    #       ↓
    #     checkout
    #       ↓
    #     ordered
    #
    # The database stores the current state; conversational
    # AI does not control this value directly.
    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
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

    # User who owns the cart.
    user = relationship(
        "User",
        back_populates="carts",
    )

    # Products currently contained in the cart.
    items = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )