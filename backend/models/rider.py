"""
Rider model.

The Rider model:
- Stores delivery partner information.
- Stores the rider's vehicle type.
- Stores driving-license information.
- Stores government-ID information.
- Stores bank details needed for payouts.
- Tracks rider onboarding status.
- Tracks rider verification status.
- Tracks rider approval status.
- Supports different vehicle types such as bike and bicycle.
- Later connects riders to assigned orders.
- Supports rider onboarding and approval workflows.
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

    # Rider onboarding status.
    #
    # Expected values:
    # - not_started
    # - in_progress
    # - submitted
    # - completed
    onboarding_status: Mapped[str] = mapped_column(
        String(30),
        default="not_started",
        nullable=False,
        index=True
    )

    # Rider verification status.
    #
    # Expected values:
    # - pending
    # - verified
    # - rejected
    verification_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True
    )

    # Rider approval status.
    #
    # Expected values:
    # - pending
    # - approved
    # - rejected
    #
    # Approval is separate from document/information verification.
    approval_status: Mapped[str] = mapped_column(
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