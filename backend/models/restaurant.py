"""
Restaurant model for BuyQK food commerce.

A Restaurant is a food-specific business entity associated with
an existing Merchant.

Merchant remains the authoritative business identity.
Restaurant stores only restaurant-specific information.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Restaurant(Base):
    """
    Represents a restaurant operating on BuyQK.

    A restaurant belongs to exactly one existing Merchant.
    """

    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Existing merchant/business identity.
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Restaurant-specific information.
    cuisine_type: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Whether the restaurant currently accepts food orders.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Whether delivery is currently supported.
    delivery_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

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

    merchant = relationship(
        "Merchant",
        back_populates="restaurant",
    )

    menus = relationship(
        "Menu",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )