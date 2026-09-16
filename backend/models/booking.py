"""
Booking model for BuyQK service commerce.

A Booking represents a confirmed or lifecycle-tracked appointment
between a user and a professional for a selected service.

The model is intentionally generic and is not tied to a specific
service vertical.

Examples:
    - AC Repair
    - Plumbing
    - Electrician
    - Home Cleaning
    - Appliance Repair
    - Car Wash
    - Salon at Home

Payment is represented by the shared Payment model through a
one-to-one relationship.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Booking(Base):
    """
    Represents a service booking made by a user.
    """

    __tablename__ = "bookings"

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_booking_valid_time_range",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ---------------------------------------------------------
    # Booking ownership
    # ---------------------------------------------------------

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Service assignment
    # ---------------------------------------------------------

    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Scheduled appointment
    # ---------------------------------------------------------

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Booking lifecycle
    # ---------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Pricing / payment
    # ---------------------------------------------------------

    total_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    payment_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Timestamps
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Payment relationship
    # ---------------------------------------------------------

    payment = relationship(
        "Payment",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
    )