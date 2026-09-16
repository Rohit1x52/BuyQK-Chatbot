"""
Service model for BuyQK service commerce.

A Service represents a bookable service offered on the BuyQK platform.

The model is intentionally generic and is not tied to a specific
service vertical such as plumbing, cleaning, salon, or appliance repair.

Examples:
    - AC Repair
    - Plumbing
    - Electrician
    - Home Cleaning
    - Appliance Repair
    - Car Wash
    - Salon at Home

Service-specific availability, professionals, and bookings are handled
by separate models.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class Service(Base):
    """
    Represents a bookable service available on BuyQK.
    """

    __tablename__ = "services"

    # Unique identifier for the service.
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Display name of the service.
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    # Description of what the service includes.
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Generic service category.
    #
    # Examples:
    #   home_repair
    #   cleaning
    #   automotive
    #   beauty
    #   electrical
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Base price of the service.
    #
    # This is the starting/reference price. Final pricing rules can
    # be handled by the booking/business logic later.
    base_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Expected service duration in minutes.
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Whether the service is currently available for booking.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Service creation timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Service last update timestamp.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
