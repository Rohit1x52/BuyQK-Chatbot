"""
The Address model is responsible for storing delivery/service addresses
belonging to a BuyQK user.

It will:
- Store the user's address.
- Link the address to users.id.
- Store city/state/pincode information.
- Store latitude/longitude for location-based services.
- Mark one address as the user's default address.
- Provide the address that can later be used by:
    - Grocery delivery
    - Food delivery
    - Medicine delivery
    - Electronics delivery
    - Service booking
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Address(Base):
    """
    Represents an address belonging to a BuyQK user.
    """

    __tablename__ = "addresses"

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
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Address Information
    # =========================================================

    label: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    postal_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # =========================================================
    # Location
    # =========================================================

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # =========================================================
    # Default Address
    # =========================================================

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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

    # =========================================================
    # Relationships
    # =========================================================

    user = relationship(
        "User",
        back_populates="addresses",
    )

    # IMPORTANT:
    #
    # Orders are historical records.
    # Deleting an address must NOT delete orders.
    #
    orders = relationship(
        "Order",
        back_populates="address",
    )