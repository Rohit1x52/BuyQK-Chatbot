"""
The Rider model will:
Store delivery partner information.
Store the rider's vehicle type.
Store driving-license information.
Track government-ID verification.
Store bank details needed for payouts.
Track rider verification status.
Support different vehicle types such as bike and bicycle.
Later connect riders to assigned orders.
Support rider onboarding and approval workflows.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Rider(Base):
    """
    Represents a delivery partner registered on BuyQK.
    """

    __tablename__ = "riders"

    # Unique identifier for the rider
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Rider's full name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # Rider's mobile number
    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    # Vehicle used for delivery
    # Examples: Bike, Bicycle, Scooter, Car
    vehicle_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    # Driving license number
    license_number: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True
    )

    # Government ID reference
    government_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    # Bank account details/reference
    bank_account: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    # Rider verification status
    # Possible values:
    # pending, verified, rejected
    verification_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True
    )

    # Rider registration timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Rider profile last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with orders
    orders = relationship(
        "Order",
        back_populates="rider"
    )