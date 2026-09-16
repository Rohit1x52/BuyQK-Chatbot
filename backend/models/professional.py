"""
Professional model for BuyQK service commerce.

A Professional represents an individual who can provide one or more
bookable services on the BuyQK platform.

The relationship between professionals and services is handled separately
through the ProfessionalService model.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class Professional(Base):
    """
    Represents a service professional available on BuyQK.
    """

    __tablename__ = "professionals"

    # Unique identifier for the professional.
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Professional's display name.
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    # Contact phone number.
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Contact email address.
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Primary specialization of the professional.
    #
    # Examples:
    #   AC Technician
    #   Plumber
    #   Electrician
    #   Home Cleaning Specialist
    #   Salon Professional
    specialization: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # Average professional rating.
    #
    # Kept as a simple numeric value for the MVP.
    rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Whether the professional is currently active.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Professional creation timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Professional last update timestamp.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )