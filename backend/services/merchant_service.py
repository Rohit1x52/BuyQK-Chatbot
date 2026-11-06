"""
BuyQK Merchant Service

Handles merchant registration and merchant onboarding data.

Responsibilities:
- Create merchant registration
- Retrieve merchant
- Update merchant onboarding details
- Validate merchant registration
- Add merchant documents
- Retrieve merchant documents
- Submit merchant for verification
- Retrieve merchant verification status
- Approve/reject merchant

This module contains backend business logic only.
AI orchestration belongs to the AI engine/tool layer.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.merchant import Merchant
from backend.models.merchant_document import MerchantDocument


# =========================================================
# Status Constants
# =========================================================

ONBOARDING_NOT_STARTED = "not_started"
ONBOARDING_IN_PROGRESS = "in_progress"
ONBOARDING_SUBMITTED = "submitted"
ONBOARDING_COMPLETED = "completed"

VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_REJECTED = "rejected"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"


# =========================================================
# Merchant Helpers
# =========================================================


def _clean(value: str | None) -> str | None:
    """Return a stripped string or None."""
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def get_merchant(
    db: Session,
    merchant_id: int,
) -> Merchant | None:
    """
    Retrieve a merchant by ID.

    Returns:
        Merchant if found, otherwise None.
    """

    if merchant_id <= 0:
        return None

    return db.get(
        Merchant,
        merchant_id,
    )


# =========================================================
# Create Merchant Registration
# =========================================================


def create_merchant(
    db: Session,
    *,
    business_name: str,
    category: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
) -> Merchant:
    """
    Create a new merchant registration.

    The merchant starts in the onboarding state:
        onboarding_status = in_progress
        verification_status = pending
        approval_status = pending
    """

    business_name = _clean(business_name)

    if not business_name:
        raise ValueError(
            "Business name is required."
        )

    category = _clean(category)
    phone = _clean(phone)
    email = _clean(email)
    address = _clean(address)

    if email:
        existing = (
            db.query(Merchant)
            .filter(Merchant.email == email)
            .first()
        )

        if existing is not None:
            raise ValueError(
                "A merchant with this email already exists."
            )

    merchant = Merchant(
        business_name=business_name,
        category=category,
        phone=phone,
        email=email,
        address=address,
        onboarding_status=ONBOARDING_IN_PROGRESS,
        verification_status=VERIFICATION_PENDING,
        approval_status=APPROVAL_PENDING,
    )

    try:
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    except IntegrityError as exc:
        db.rollback()

        raise ValueError(
            "Unable to create merchant registration because "
            "the merchant information conflicts with an existing record."
        ) from exc

    return merchant


# =========================================================
# Update Merchant Onboarding Details
# =========================================================


def update_merchant(
    db: Session,
    merchant_id: int,
    *,
    business_name: str | None = None,
    category: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
) -> Merchant:
    """
    Update merchant onboarding information.

    Only supplied fields are updated.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    if merchant.approval_status == APPROVAL_APPROVED:
        raise ValueError(
            "Approved merchant details cannot be changed through onboarding."
        )

    if business_name is not None:
        business_name = _clean(business_name)

        if not business_name:
            raise ValueError(
                "Business name cannot be empty."
            )

        merchant.business_name = business_name

    if category is not None:
        merchant.category = _clean(category)

    if phone is not None:
        merchant.phone = _clean(phone)

    if email is not None:
        email = _clean(email)

        if email:
            existing = (
                db.query(Merchant)
                .filter(
                    Merchant.email == email,
                    Merchant.id != merchant_id,
                )
                .first()
            )

            if existing is not None:
                raise ValueError(
                    "A merchant with this email already exists."
                )

        merchant.email = email

    if address is not None:
        merchant.address = _clean(address)

    merchant.onboarding_status = ONBOARDING_IN_PROGRESS

    db.commit()
    db.refresh(merchant)

    return merchant


# =========================================================
# Validate Merchant Registration
# =========================================================


def validate_merchant_registration(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Validate that all mandatory merchant registration
    information has been collected.

    This function does not verify document authenticity.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    missing_fields: list[str] = []

    if not _clean(merchant.business_name):
        missing_fields.append("business_name")

    if not _clean(merchant.category):
        missing_fields.append("category")

    if not _clean(merchant.phone):
        missing_fields.append("phone")

    if not _clean(merchant.address):
        missing_fields.append("address")

    if missing_fields:
        raise ValueError(
            "Merchant registration is incomplete. "
            f"Missing fields: {', '.join(missing_fields)}."
        )

    return merchant


# =========================================================
# Merchant Documents
# =========================================================


def add_merchant_document(
    db: Session,
    merchant_id: int,
    *,
    document_type: str,
    document_reference: str | None = None,
) -> MerchantDocument:
    """
    Add a document to a merchant's onboarding profile.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    document_type = _clean(document_type)

    if not document_type:
        raise ValueError(
            "Document type is required."
        )

    document_reference = _clean(
        document_reference
    )

    document = MerchantDocument(
        merchant_id=merchant_id,
        document_type=document_type,
        document_reference=document_reference,
        verification_status=VERIFICATION_PENDING,
    )

    db.add(document)

    merchant.onboarding_status = ONBOARDING_IN_PROGRESS

    db.commit()
    db.refresh(document)

    return document


def get_merchant_documents(
    db: Session,
    merchant_id: int,
) -> list[MerchantDocument]:
    """
    Return all documents belonging to a merchant.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    stmt = (
        select(MerchantDocument)
        .where(
            MerchantDocument.merchant_id == merchant_id
        )
        .order_by(
            MerchantDocument.id.asc()
        )
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Submit Merchant Verification
# =========================================================


def submit_merchant_verification(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Submit a merchant for backend verification.

    The merchant must have all mandatory profile information
    and at least one submitted document.
    """

    merchant = validate_merchant_registration(
        db,
        merchant_id,
    )

    documents = get_merchant_documents(
        db,
        merchant_id,
    )

    if not documents:
        raise ValueError(
            "At least one verification document is required."
        )

    merchant.onboarding_status = ONBOARDING_SUBMITTED
    merchant.verification_status = VERIFICATION_PENDING
    merchant.approval_status = APPROVAL_PENDING

    db.commit()
    db.refresh(merchant)

    return merchant


# =========================================================
# Merchant Verification Status
# =========================================================


def get_merchant_verification_status(
    db: Session,
    merchant_id: int,
) -> dict[str, str | int]:
    """
    Return the current merchant onboarding,
    verification, and approval status.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    return {
        "merchant_id": merchant.id,
        "onboarding_status": merchant.onboarding_status,
        "verification_status": merchant.verification_status,
        "approval_status": merchant.approval_status,
    }


# =========================================================
# Merchant Approval
# =========================================================


def approve_merchant(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Approve a merchant after successful verification.

    Approval is backend-controlled and can only happen
    after verification_status == verified.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    if merchant.verification_status != VERIFICATION_VERIFIED:
        raise ValueError(
            "Merchant must be verified before approval."
        )

    merchant.approval_status = APPROVAL_APPROVED
    merchant.onboarding_status = ONBOARDING_COMPLETED

    db.commit()
    db.refresh(merchant)

    return merchant


def reject_merchant(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Reject a merchant application.
    """

    merchant = get_merchant(
        db,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    merchant.approval_status = APPROVAL_REJECTED

    db.commit()
    db.refresh(merchant)

    return merchant