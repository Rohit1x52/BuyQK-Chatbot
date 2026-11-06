"""
BuyQK Rider Service

Handles rider registration and rider onboarding data.

Responsibilities:
- Create rider registration
- Retrieve rider
- Update rider onboarding details
- Validate rider registration
- Add rider documents
- Retrieve rider documents
- Submit rider for verification
- Retrieve rider verification status
- Approve/reject rider

This module contains backend business logic only.
AI orchestration belongs to the AI engine/tool layer.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.rider import Rider
from backend.models.rider_document import RiderDocument


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
# Helpers
# =========================================================


def _clean(value: str | None) -> str | None:
    """Return a stripped string or None."""
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def get_rider(
    db: Session,
    rider_id: int,
) -> Rider | None:
    """
    Retrieve a rider by ID.

    Returns:
        Rider if found, otherwise None.
    """

    if rider_id <= 0:
        return None

    return db.get(
        Rider,
        rider_id,
    )


# =========================================================
# Create Rider Registration
# =========================================================


def create_rider(
    db: Session,
    *,
    name: str,
    phone: str,
    vehicle_type: str,
    license_number: str | None = None,
    government_id: str | None = None,
    bank_account: str | None = None,
) -> Rider:
    """
    Create a new rider registration.

    The rider starts in the onboarding state:
        onboarding_status = in_progress
        verification_status = pending
        approval_status = pending
    """

    name = _clean(name)
    phone = _clean(phone)
    vehicle_type = _clean(vehicle_type)
    license_number = _clean(license_number)
    government_id = _clean(government_id)
    bank_account = _clean(bank_account)

    if not name:
        raise ValueError(
            "Rider name is required."
        )

    if not phone:
        raise ValueError(
            "Rider phone number is required."
        )

    if not vehicle_type:
        raise ValueError(
            "Vehicle type is required."
        )

    existing_phone = (
        db.query(Rider)
        .filter(Rider.phone == phone)
        .first()
    )

    if existing_phone is not None:
        raise ValueError(
            "A rider with this phone number already exists."
        )

    if license_number:
        existing_license = (
            db.query(Rider)
            .filter(
                Rider.license_number == license_number
            )
            .first()
        )

        if existing_license is not None:
            raise ValueError(
                "A rider with this license number already exists."
            )

    rider = Rider(
        name=name,
        phone=phone,
        vehicle_type=vehicle_type,
        license_number=license_number,
        government_id=government_id,
        bank_account=bank_account,
        onboarding_status=ONBOARDING_IN_PROGRESS,
        verification_status=VERIFICATION_PENDING,
        approval_status=APPROVAL_PENDING,
    )

    try:
        db.add(rider)
        db.commit()
        db.refresh(rider)
    except IntegrityError as exc:
        db.rollback()

        raise ValueError(
            "Unable to create rider registration because "
            "the rider information conflicts with an existing record."
        ) from exc

    return rider


# =========================================================
# Update Rider Details
# =========================================================


def update_rider(
    db: Session,
    rider_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    vehicle_type: str | None = None,
    license_number: str | None = None,
    government_id: str | None = None,
    bank_account: str | None = None,
) -> Rider:
    """
    Update rider onboarding information.

    Only supplied fields are updated.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    if rider.approval_status == APPROVAL_APPROVED:
        raise ValueError(
            "Approved rider details cannot be changed through onboarding."
        )

    if name is not None:
        name = _clean(name)

        if not name:
            raise ValueError(
                "Rider name cannot be empty."
            )

        rider.name = name

    if phone is not None:
        phone = _clean(phone)

        if not phone:
            raise ValueError(
                "Rider phone number cannot be empty."
            )

        existing = (
            db.query(Rider)
            .filter(
                Rider.phone == phone,
                Rider.id != rider_id,
            )
            .first()
        )

        if existing is not None:
            raise ValueError(
                "A rider with this phone number already exists."
            )

        rider.phone = phone

    if vehicle_type is not None:
        vehicle_type = _clean(vehicle_type)

        if not vehicle_type:
            raise ValueError(
                "Vehicle type cannot be empty."
            )

        rider.vehicle_type = vehicle_type

    if license_number is not None:
        license_number = _clean(
            license_number
        )

        if license_number:
            existing = (
                db.query(Rider)
                .filter(
                    Rider.license_number == license_number,
                    Rider.id != rider_id,
                )
                .first()
            )

            if existing is not None:
                raise ValueError(
                    "A rider with this license number already exists."
                )

        rider.license_number = license_number

    if government_id is not None:
        rider.government_id = _clean(
            government_id
        )

    if bank_account is not None:
        rider.bank_account = _clean(
            bank_account
        )

    rider.onboarding_status = ONBOARDING_IN_PROGRESS

    db.commit()
    db.refresh(rider)

    return rider


# =========================================================
# Validate Rider Registration
# =========================================================


def validate_rider_registration(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Validate that all mandatory rider registration
    information has been collected.

    This function does not verify document authenticity.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    missing_fields: list[str] = []

    if not _clean(rider.name):
        missing_fields.append("name")

    if not _clean(rider.phone):
        missing_fields.append("phone")

    if not _clean(rider.vehicle_type):
        missing_fields.append("vehicle_type")

    if not _clean(rider.license_number):
        missing_fields.append("license_number")

    if not _clean(rider.government_id):
        missing_fields.append("government_id")

    if not _clean(rider.bank_account):
        missing_fields.append("bank_account")

    if missing_fields:
        raise ValueError(
            "Rider registration is incomplete. "
            f"Missing fields: {', '.join(missing_fields)}."
        )

    return rider


# =========================================================
# Rider Documents
# =========================================================


def add_rider_document(
    db: Session,
    rider_id: int,
    *,
    document_type: str,
    document_reference: str | None = None,
) -> RiderDocument:
    """
    Add a document to a rider's onboarding profile.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    document_type = _clean(document_type)

    if not document_type:
        raise ValueError(
            "Document type is required."
        )

    document_reference = _clean(
        document_reference
    )

    document = RiderDocument(
        rider_id=rider_id,
        document_type=document_type,
        document_reference=document_reference,
        verification_status=VERIFICATION_PENDING,
    )

    db.add(document)

    rider.onboarding_status = ONBOARDING_IN_PROGRESS

    db.commit()
    db.refresh(document)

    return document


def get_rider_documents(
    db: Session,
    rider_id: int,
) -> list[RiderDocument]:
    """
    Return all documents belonging to a rider.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    stmt = (
        select(RiderDocument)
        .where(
            RiderDocument.rider_id == rider_id
        )
        .order_by(
            RiderDocument.id.asc()
        )
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Submit Rider Verification
# =========================================================


def submit_rider_verification(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Submit a rider for backend verification.

    The rider must have all mandatory profile information
    and both required onboarding document types.
    """

    rider = validate_rider_registration(
        db,
        rider_id,
    )

    documents = get_rider_documents(
        db,
        rider_id,
    )

    if not documents:
        raise ValueError(
            "Required rider verification documents are missing."
        )

    document_types = {
        document.document_type.strip().lower()
        for document in documents
        if document.document_type
    }

    has_license_document = any(
        value in document_types
        for value in {
            "driving license",
            "driving licence",
            "license",
            "licence",
        }
    )

    has_government_id = any(
        value in document_types
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

    rider.onboarding_status = ONBOARDING_SUBMITTED
    rider.verification_status = VERIFICATION_PENDING
    rider.approval_status = APPROVAL_PENDING

    db.commit()
    db.refresh(rider)

    return rider


# =========================================================
# Rider Verification Status
# =========================================================


def get_rider_verification_status(
    db: Session,
    rider_id: int,
) -> dict[str, str | int]:
    """
    Return the current rider onboarding,
    verification, and approval status.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    return {
        "rider_id": rider.id,
        "onboarding_status": rider.onboarding_status,
        "verification_status": rider.verification_status,
        "approval_status": rider.approval_status,
    }


# =========================================================
# Rider Approval
# =========================================================


def approve_rider(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Approve a rider after successful verification.

    Approval is backend-controlled and can only happen
    after verification_status == verified.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    if rider.verification_status != VERIFICATION_VERIFIED:
        raise ValueError(
            "Rider must be verified before approval."
        )

    rider.approval_status = APPROVAL_APPROVED
    rider.onboarding_status = ONBOARDING_COMPLETED

    db.commit()
    db.refresh(rider)

    return rider


def reject_rider(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Reject a rider application.
    """

    rider = get_rider(
        db,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    rider.approval_status = APPROVAL_REJECTED

    db.commit()
    db.refresh(rider)

    return rider