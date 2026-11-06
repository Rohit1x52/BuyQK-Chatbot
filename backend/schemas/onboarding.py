"""
BuyQK Shared Onboarding Schemas.

Shared request/response contracts for merchant and rider
verification and approval workflows.
"""

from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    """Current onboarding state."""

    entity_type: str
    entity_id: int
    verification_status: str
    approval_status: str


class OnboardingVerificationResponse(BaseModel):
    """Result of backend onboarding verification checks."""

    entity_type: str
    entity_id: int
    verification_status: str
    approval_status: str
    missing_information: list[str] = []
    missing_documents: list[str] = []


class OnboardingDecisionRequest(BaseModel):
    """Administrative approval/rejection decision."""

    approved: bool
    reason: str | None = None