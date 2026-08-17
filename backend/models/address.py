"""
The Address model is responsible for storing delivery/service addresses belonging to a BuyQK user.
It will:
Store the user's address.
Link the address to users.id.
Store city/state/pincode information.
Store latitude/longitude for location-based services.
Mark one address as the user's default address.
Provide the address that can later be used by:
   -Grocery delivery
   -Food delivery
   -Medicine delivery
   -Electronics delivery
   -Service booking
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

    # Unique identifier for the address
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # ID of the user who owns this address
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Address label (e.g., Home, Office)
    label: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    # First line of the address
    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Optional second line of the address
    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # City
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # State
    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Postal/PIN code
    postal_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # Latitude for location-based services
    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    # Longitude for location-based services
    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    # Whether this is the user's default address
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # Address creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship back to the User model
    user = relationship(
        "User",
        back_populates="addresses"
    )

    # Orders delivered to this address
    orders = relationship(
        "Order",
        back_populates="address",
        cascade="all, delete-orphan"
    )