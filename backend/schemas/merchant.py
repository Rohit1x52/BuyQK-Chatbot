"""
BuyQK Merchant Onboarding Schemas.

Pydantic request/response contracts for merchant registration,
documents, and onboarding status.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MerchantRegistrationRequest(BaseModel):
    """Initial merchant registration and business details."""

    business_name: str = Field(
        min_length=1,
        max_length=150,
    )

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    phone: str | None = Field(
        default=None,
        max_length=20,
    )

    email: str | None = Field(
        default=None,
        max_length=255,
    )

    address: str | None = Field(
        default=None,
        max_length=500,
    )


class MerchantRegistrationResponse(BaseModel):
    """Backend-created merchant registration."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    business_name: str
    category: str | None
    phone: str | None
    email: str | None
    address: str | None
    verification_status: str
    created_at: datetime
    updated_at: datetime


class MerchantDocumentRequest(BaseModel):
    """Document submitted for merchant verification."""

    document_type: str = Field(
        min_length=1,
        max_length=100,
    )

    document_reference: str = Field(
        min_length=1,
        max_length=500,
    )


class MerchantDocumentResponse(BaseModel):
    """Stored merchant document record."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    merchant_id: int
    document_type: str
    document_reference: str
    verification_status: str
    created_at: datetime
    updated_at: datetime


class MerchantStatusResponse(BaseModel):
    """Merchant onboarding status."""

    merchant_id: int
    verification_status: str
    approval_status: str