"""
Merchant model.

The Merchant model:
- Stores merchant/business information.
- Stores the merchant's business category.
- Stores contact information.
- Stores the business address.
- Tracks merchant onboarding status.
- Tracks merchant verification status.
- Tracks merchant approval status.
- Allows products to be associated with a merchant.
- Supports merchant onboarding workflows.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Merchant(Base):
    """
    Represents a business/merchant registered on BuyQK.
    """

    __tablename__ = "merchants"

    # Unique identifier for the merchant
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Business/store name
    business_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True
    )

    # Business category
    # Examples: Grocery, Pharmacy, Restaurant, Electronics
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    # Business contact number
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
        index=True
    )

    # Business email
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True
    )

    # Complete business/store address
    address: Mapped[str] = mapped_column(
        String(500),
        nullable=True
    )

    # Merchant onboarding status.
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

    # Merchant verification status.
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

    # Merchant approval status.
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

    # Merchant creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Merchant last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with products
    products = relationship(
        "Product",
        back_populates="merchant"
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="merchant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __init__(self, *args, **kwargs):
        # Backwards-compatibility: allow calling Merchant(name=...)
        # from tests or older code by mapping `name` to
        # `business_name`.
        if "name" in kwargs and "business_name" not in kwargs:
            kwargs["business_name"] = kwargs.pop("name")

        super().__init__(*args, **kwargs)