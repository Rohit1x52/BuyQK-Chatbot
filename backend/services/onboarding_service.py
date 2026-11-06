"""
BuyQK Onboarding Service

Provides shared onboarding workflow operations for merchants
and riders.

Responsibilities:
- Submit onboarding
- Retrieve onboarding status
- Approve onboarding
- Reject onboarding

Verification itself is handled by
onboarding_verification_service.py.

This module does not contain AI logic.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.merchant import Merchant
from backend.models.rider import Rider


# =========================================================
# Status Constants
# =========================================================

ONBOARDING_SUBMITTED = "submitted"
ONBOARDING_COMPLETED = "completed"

VERIFICATION_VERIFIED = "verified"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"


# =========================================================
# Merchant Onboarding
# =========================================================


def submit_merchant_onboarding(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Mark a merchant onboarding application as submitted.

    Required information and documents should be validated
    by merchant_service.submit_merchant_verification().
    """

    merchant = db.get(
        Merchant,
        merchant_id,
    )

    if merchant is None:
        raise ValueError(
            f"Merchant {merchant_id} does not exist."
        )

    merchant.onboarding_status = ONBOARDING_SUBMITTED
    merchant.approval_status = APPROVAL_PENDING

    db.commit()
    db.refresh(merchant)

    return merchant


def get_merchant_onboarding_status(
    db: Session,
    merchant_id: int,
) -> dict[str, str | int]:
    """
    Return complete merchant onboarding status.
    """

    merchant = db.get(
        Merchant,
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


def approve_merchant_onboarding(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Approve merchant onboarding.

    Verification must already be successful.
    """

    merchant = db.get(
        Merchant,
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


def reject_merchant_onboarding(
    db: Session,
    merchant_id: int,
) -> Merchant:
    """
    Reject merchant onboarding.
    """

    merchant = db.get(
        Merchant,
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


# =========================================================
# Rider Onboarding
# =========================================================


def submit_rider_onboarding(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Mark a rider onboarding application as submitted.

    Required information and documents should be validated
    by rider_service.submit_rider_verification().
    """

    rider = db.get(
        Rider,
        rider_id,
    )

    if rider is None:
        raise ValueError(
            f"Rider {rider_id} does not exist."
        )

    rider.onboarding_status = ONBOARDING_SUBMITTED
    rider.approval_status = APPROVAL_PENDING

    db.commit()
    db.refresh(rider)

    return rider


def get_rider_onboarding_status(
    db: Session,
    rider_id: int,
) -> dict[str, str | int]:
    """
    Return complete rider onboarding status.
    """

    rider = db.get(
        Rider,
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


def approve_rider_onboarding(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Approve rider onboarding.

    Verification must already be successful.
    """

    rider = db.get(
        Rider,
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


def reject_rider_onboarding(
    db: Session,
    rider_id: int,
) -> Rider:
    """
    Reject rider onboarding.
    """

    rider = db.get(
        Rider,
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