"""
BuyQK Merchant & Rider Onboarding API.

This router exposes the onboarding endpoints for merchant and rider
registration, document submission, verification, and approval flows.
The business logic remains inside the backend service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.schemas.merchant import (
    MerchantDocumentRequest,
    MerchantDocumentResponse,
    MerchantRegistrationRequest,
    MerchantRegistrationResponse,
)
from backend.schemas.onboarding import (
    OnboardingDecisionRequest,
    OnboardingStatusResponse,
    OnboardingVerificationResponse,
)
from backend.schemas.rider import (
    RiderDocumentRequest,
    RiderDocumentResponse,
    RiderRegistrationRequest,
    RiderRegistrationResponse,
)
from backend.services.merchant_service import (
    add_merchant_document,
    approve_merchant,
    create_merchant,
    get_merchant,
    get_merchant_documents,
    get_merchant_verification_status,
    reject_merchant,
    submit_merchant_verification,
    update_merchant,
)
from backend.services.rider_service import (
    add_rider_document,
    approve_rider,
    create_rider,
    get_rider,
    get_rider_documents,
    get_rider_verification_status,
    reject_rider,
    submit_rider_verification,
    update_rider,
)

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
)


def _handle_service_error(exc: Exception) -> HTTPException:
    """Convert service-layer validation errors into API errors."""

    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return HTTPException(
        status_code=500,
        detail="An onboarding service error occurred.",
    )


def _commit_or_raise(db: Session) -> None:
    """Commit the current transaction or roll back on failure."""

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


# =========================================================
# Merchant endpoints
# =========================================================

@router.post(
    "/merchants",
    response_model=MerchantRegistrationResponse,
)
def register_merchant(
    request: MerchantRegistrationRequest,
    db: Session = Depends(get_db),
):
    """Register a merchant onboarding profile."""

    try:
        merchant = create_merchant(
            db=db,
            business_name=request.business_name,
            category=request.category,
            phone=request.phone,
            email=request.email,
            address=request.address,
        )
        _commit_or_raise(db)
        return merchant
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/merchants/{merchant_id}",
    response_model=MerchantRegistrationResponse,
)
def get_merchant_endpoint(
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Retrieve an existing merchant profile."""

    try:
        merchant = get_merchant(db=db, merchant_id=merchant_id)
        if merchant is None:
            raise HTTPException(
                status_code=404,
                detail="Merchant not found.",
            )
        return merchant
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.patch(
    "/merchants/{merchant_id}",
    response_model=MerchantRegistrationResponse,
)
def update_merchant_endpoint(
    request: MerchantRegistrationRequest,
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Update merchant onboarding information."""

    try:
        merchant = update_merchant(
            db=db,
            merchant_id=merchant_id,
            business_name=request.business_name,
            category=request.category,
            phone=request.phone,
            email=request.email,
            address=request.address,
        )
        _commit_or_raise(db)
        return merchant
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.post(
    "/merchants/{merchant_id}/documents",
    response_model=MerchantDocumentResponse,
)
def add_merchant_document_endpoint(
    request: MerchantDocumentRequest,
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Add a merchant verification document."""

    try:
        document = add_merchant_document(
            db=db,
            merchant_id=merchant_id,
            document_type=request.document_type,
            document_reference=request.document_reference,
        )
        _commit_or_raise(db)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/merchants/{merchant_id}/documents",
    response_model=list[MerchantDocumentResponse],
)
def get_merchant_documents_endpoint(
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Return all documents associated with a merchant."""

    try:
        return get_merchant_documents(db=db, merchant_id=merchant_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.post(
    "/merchants/{merchant_id}/submit",
    response_model=OnboardingVerificationResponse,
)
def submit_merchant_onboarding(
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Submit a merchant for verification."""

    try:
        submit_merchant_verification(db=db, merchant_id=merchant_id)
        status = get_merchant_verification_status(db=db, merchant_id=merchant_id)
        _commit_or_raise(db)
        return {
            "entity_type": "merchant",
            "entity_id": merchant_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
            "missing_information": [],
            "missing_documents": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/merchants/{merchant_id}/status",
    response_model=OnboardingStatusResponse,
)
def get_merchant_status(
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Return the current merchant onboarding status."""

    try:
        status = get_merchant_verification_status(db=db, merchant_id=merchant_id)
        return {
            "entity_type": "merchant",
            "entity_id": merchant_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.post(
    "/merchants/{merchant_id}/approve",
    response_model=OnboardingStatusResponse,
)
def approve_merchant_endpoint(
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Approve a merchant after verification succeeds."""

    try:
        approve_merchant(db=db, merchant_id=merchant_id)
        status = get_merchant_verification_status(db=db, merchant_id=merchant_id)
        _commit_or_raise(db)
        return {
            "entity_type": "merchant",
            "entity_id": merchant_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.post(
    "/merchants/{merchant_id}/reject",
    response_model=OnboardingStatusResponse,
)
def reject_merchant_endpoint(
    request: OnboardingDecisionRequest,
    merchant_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Reject a merchant onboarding application."""

    try:
        reject_merchant(db=db, merchant_id=merchant_id)
        status = get_merchant_verification_status(db=db, merchant_id=merchant_id)
        _commit_or_raise(db)
        return {
            "entity_type": "merchant",
            "entity_id": merchant_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


# =========================================================
# Rider endpoints
# =========================================================

@router.post(
    "/riders",
    response_model=RiderRegistrationResponse,
)
def register_rider(
    request: RiderRegistrationRequest,
    db: Session = Depends(get_db),
):
    """Register a rider onboarding profile."""

    try:
        rider = create_rider(
            db=db,
            name=request.name,
            phone=request.phone,
            vehicle_type=request.vehicle_type,
            license_number=request.license_number,
            government_id=request.government_id,
            bank_account=request.bank_account,
        )
        _commit_or_raise(db)
        return rider
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/riders/{rider_id}",
    response_model=RiderRegistrationResponse,
)
def get_rider_endpoint(
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Retrieve an existing rider profile."""

    try:
        rider = get_rider(db=db, rider_id=rider_id)
        if rider is None:
            raise HTTPException(
                status_code=404,
                detail="Rider not found.",
            )
        return rider
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.patch(
    "/riders/{rider_id}",
    response_model=RiderRegistrationResponse,
)
def update_rider_endpoint(
    request: RiderRegistrationRequest,
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Update rider onboarding information."""

    try:
        rider = update_rider(
            db=db,
            rider_id=rider_id,
            name=request.name,
            phone=request.phone,
            vehicle_type=request.vehicle_type,
            license_number=request.license_number,
            government_id=request.government_id,
            bank_account=request.bank_account,
        )
        _commit_or_raise(db)
        return rider
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.post(
    "/riders/{rider_id}/documents",
    response_model=RiderDocumentResponse,
)
def add_rider_document_endpoint(
    request: RiderDocumentRequest,
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Add a rider verification document."""

    try:
        document = add_rider_document(
            db=db,
            rider_id=rider_id,
            document_type=request.document_type,
            document_reference=request.document_reference,
        )
        _commit_or_raise(db)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/riders/{rider_id}/documents",
    response_model=list[RiderDocumentResponse],
)
def get_rider_documents_endpoint(
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Return all documents associated with a rider."""

    try:
        return get_rider_documents(db=db, rider_id=rider_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.post(
    "/riders/{rider_id}/submit",
    response_model=OnboardingVerificationResponse,
)
def submit_rider_onboarding(
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Submit a rider for verification."""

    try:
        submit_rider_verification(db=db, rider_id=rider_id)
        status = get_rider_verification_status(db=db, rider_id=rider_id)
        _commit_or_raise(db)
        return {
            "entity_type": "rider",
            "entity_id": rider_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
            "missing_information": [],
            "missing_documents": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.get(
    "/riders/{rider_id}/status",
    response_model=OnboardingStatusResponse,
)
def get_rider_status(
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Return the current rider onboarding status."""

    try:
        status = get_rider_verification_status(db=db, rider_id=rider_id)
        return {
            "entity_type": "rider",
            "entity_id": rider_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@router.post(
    "/riders/{rider_id}/approve",
    response_model=OnboardingStatusResponse,
)
def approve_rider_endpoint(
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Approve a rider after verification succeeds."""

    try:
        approve_rider(db=db, rider_id=rider_id)
        status = get_rider_verification_status(db=db, rider_id=rider_id)
        _commit_or_raise(db)
        return {
            "entity_type": "rider",
            "entity_id": rider_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


@router.post(
    "/riders/{rider_id}/reject",
    response_model=OnboardingStatusResponse,
)
def reject_rider_endpoint(
    request: OnboardingDecisionRequest,
    rider_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Reject a rider onboarding application."""

    try:
        reject_rider(db=db, rider_id=rider_id)
        status = get_rider_verification_status(db=db, rider_id=rider_id)
        _commit_or_raise(db)
        return {
            "entity_type": "rider",
            "entity_id": rider_id,
            "verification_status": status["verification_status"],
            "approval_status": status["approval_status"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise _handle_service_error(exc) from exc


__all__ = ["router"]
