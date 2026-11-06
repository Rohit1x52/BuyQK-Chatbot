"""
BuyQK Rider Onboarding Schemas.

Pydantic request/response contracts for rider registration,
documents, and onboarding status.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RiderRegistrationRequest(BaseModel):
    """Initial rider registration and personal/vehicle details."""

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    phone: str = Field(
        min_length=1,
        max_length=20,
    )

    vehicle_type: str = Field(
        min_length=1,
        max_length=50,
    )

    license_number: str | None = Field(
        default=None,
        max_length=100,
    )

    government_id: str | None = Field(
        default=None,
        max_length=100,
    )

    bank_account: str | None = Field(
        default=None,
        max_length=100,
    )


class RiderRegistrationResponse(BaseModel):
    """Backend-created rider registration."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    phone: str
    vehicle_type: str
    license_number: str | None
    government_id: str | None
    verification_status: str
    created_at: datetime
    updated_at: datetime


class RiderDocumentRequest(BaseModel):
    """Document submitted for rider verification."""

    document_type: str = Field(
        min_length=1,
        max_length=100,
    )

    document_reference: str = Field(
        min_length=1,
        max_length=500,
    )


class RiderDocumentResponse(BaseModel):
    """Stored rider document record."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    rider_id: int
    document_type: str
    document_reference: str
    verification_status: str
    created_at: datetime
    updated_at: datetime


class RiderStatusResponse(BaseModel):
    """Rider onboarding status."""

    rider_id: int
    verification_status: str
    approval_status: str