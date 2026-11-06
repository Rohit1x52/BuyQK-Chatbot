"""
BuyQK Onboarding Verification Service

Provides shared verification logic for merchant and rider
onboarding.

Important:
This service performs backend validation of submitted
onboarding information and document records.

It does NOT claim to perform external KYC, GST, bank,
government, or document-authenticity verification.

External/manual verification systems can update the
verification status later.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.merchant import Merchant
from backend.models.merchant_document import MerchantDocument
from backend.models.rider import Rider
from backend.models.rider_document import RiderDocument


# =========================================================
# Status Constants
# =========================================================

VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_REJECTED = "rejected"


# =========================================================
# Merchant Verification
# =========================================================


def verify_merchant(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Mark a merchant as verified after backend validation.

    Validation includes:
    - Required merchant profile information
    - Presence of onboarding documents
    - Document references where supplied

    This does not perform external document authenticity checks.
    """

    merchant = db.get(
        Merchant,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    missing_fields: list[str] = []

    if not merchant.business_name or not merchant.business_name.strip():
        missing_fields.append("business_name")

    if not merchant.category or not merchant.category.strip():
        missing_fields.append("category")

    if not merchant.phone or not merchant.phone.strip():
        missing_fields.append("phone")

    if not merchant.address or not merchant.address.strip():
        missing_fields.append("address")

    if missing_fields:
        raise ValueError(
            "Merchant verification cannot proceed. "
            f"Missing fields: {', '.join(missing_fields)}."
        )

    documents = (
        db.query(MerchantDocument)
        .filter(
            MerchantDocument.merchant_id == merchant_id
        )
        .all()
    )

    if not documents:
        raise ValueError(
            "Merchant verification documents are required."
        )

    invalid_documents = [
        document.id
        for document in documents
        if not document.document_type
        or not document.document_type.strip()
        or not document.document_reference
        or not document.document_reference.strip()
    ]

    if invalid_documents:
        raise ValueError(
            "Merchant contains incomplete document records: "
            f"{invalid_documents}."
        )

    for document in documents:
        document.verification_status = VERIFICATION_VERIFIED

    merchant.verification_status = VERIFICATION_VERIFIED

    db.commit()
    db.refresh(merchant)

    return merchant


def reject_merchant_verification(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Mark merchant verification as rejected.
    """

    merchant = db.get(
        Merchant,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    merchant.verification_status = VERIFICATION_REJECTED

    documents = (
        db.query(MerchantDocument)
        .filter(
            MerchantDocument.merchant_id == merchant_id
        )
        .all()
    )

    for document in documents:
        document.verification_status = VERIFICATION_REJECTED

    db.commit()
    db.refresh(merchant)

    return merchant


# =========================================================
# Rider Verification
# =========================================================


def verify_rider(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Mark a rider as verified after backend validation.

    Validation includes:
    - Required rider profile information
    - Driving License document
    - Government ID document
    - Document references

    This does not perform external document authenticity checks.
    """

    rider = db.get(
        Rider,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    missing_fields: list[str] = []

    if not rider.name or not rider.name.strip():
        missing_fields.append("name")

    if not rider.phone or not rider.phone.strip():
        missing_fields.append("phone")

    if not rider.vehicle_type or not rider.vehicle_type.strip():
        missing_fields.append("vehicle_type")

    if not rider.license_number or not rider.license_number.strip():
        missing_fields.append("license_number")

    if not rider.government_id or not rider.government_id.strip():
        missing_fields.append("government_id")

    if not rider.bank_account or not rider.bank_account.strip():
        missing_fields.append("bank_account")

    if missing_fields:
        raise ValueError(
            "Rider verification cannot proceed. "
            f"Missing fields: {', '.join(missing_fields)}."
        )

    documents = (
        db.query(RiderDocument)
        .filter(
            RiderDocument.rider_id == rider_id
        )
        .all()
    )

    if not documents:
        raise ValueError(
            "Rider verification documents are required."
        )

    normalized_types = {
        document.document_type.strip().lower()
        for document in documents
        if document.document_type
    }

    has_license_document = any(
        value in normalized_types
        for value in {
            "driving license",
            "driving licence",
            "license",
            "licence",
        }
    )

    has_government_id = any(
        value in normalized_types
        for value in {
            "government id",
            "government-id",
            "government identification",
            "id",
        }
    )

    if not has_license_document:
        raise ValueError(
            "Driving License document is required."
        )

    if not has_government_id:
        raise ValueError(
            "Government ID document is required."
        )

    invalid_documents = [
        document.id
        for document in documents
        if not document.document_type
        or not document.document_type.strip()
        or not document.document_reference
        or not document.document_reference.strip()
    ]

    if invalid_documents:
        raise ValueError(
            "Rider contains incomplete document records: "
            f"{invalid_documents}."
        )

    for document in documents:
        document.verification_status = VERIFICATION_VERIFIED

    rider.verification_status = VERIFICATION_VERIFIED

    db.commit()
    db.refresh(rider)

    return rider


def reject_rider_verification(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Mark rider verification as rejected.
    """

    rider = db.get(
        Rider,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    rider.verification_status = VERIFICATION_REJECTED

    documents = (
        db.query(RiderDocument)
        .filter(
            RiderDocument.rider_id == rider_id
        )
        .all()
    )

    for document in documents:
        document.verification_status = VERIFICATION_REJECTED

    db.commit()
    db.refresh(rider)

    return rider