"""
Merchant document model.

Stores documents submitted by a merchant during onboarding.
Document verification is handled by the onboarding/verification
service layer.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class MerchantDocument(Base):
    """
    Represents a document submitted by a merchant for onboarding
    and verification.
    """

    __tablename__ = "merchant_documents"

    # Unique identifier for the document
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Merchant that owns this document
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "merchants.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Type of document
    # Examples:
    # - GST
    # - PAN
    # - Business License
    # - Government ID
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    # Reference/identifier for the submitted document.
    #
    # This can represent a document number or an application/storage
    # reference. Actual file-storage handling belongs to the service
    # layer and is intentionally not implemented in this model.
    document_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # Document verification status
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

    # Document creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Document last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with Merchant
    merchant = relationship(
        "Merchant",
        back_populates="documents"
    )