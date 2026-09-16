"""
BuyQK Professional Service

Handles professional discovery and validation.

A professional can provide multiple services through the
ProfessionalService association model.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.professional import Professional
from backend.models.professional_service import ProfessionalService


# =========================================================
# Get Professional
# =========================================================


def get_professional(
    db: Session,
    professional_id: int,
) -> Professional | None:
    """
    Retrieve a professional by ID.

    Returns:
        Professional if found, otherwise None.
    """

    if professional_id <= 0:
        return None

    return db.get(
        Professional,
        professional_id,
    )


# =========================================================
# Validate Professional
# =========================================================


def validate_professional(
    db: Session,
    professional_id: int,
    *,
    require_active: bool = True,
) -> Professional:
    """
    Validate that a professional exists and is active.

    Raises:
        ValueError: If the professional does not exist or is inactive.
    """

    professional = get_professional(
        db,
        professional_id,
    )

    if professional is None:
        raise ValueError(
            f"Professional {professional_id} does not exist."
        )

    if require_active and not professional.is_active:
        raise ValueError(
            f"Professional {professional_id} is currently inactive."
        )

    return professional


# =========================================================
# Validate Professional / Service Relationship
# =========================================================


def validate_professional_service(
    db: Session,
    professional_id: int,
    service_id: int,
) -> ProfessionalService:
    """
    Validate that a professional is assigned to a service.

    This checks the many-to-many ProfessionalService relationship.

    Raises:
        ValueError: If the relationship does not exist.
    """

    relationship = db.scalar(
        select(ProfessionalService).where(
            ProfessionalService.professional_id
            == professional_id,
            ProfessionalService.service_id
            == service_id,
        )
    )

    if relationship is None:
        raise ValueError(
            f"Professional {professional_id} does not provide "
            f"service {service_id}."
        )

    return relationship


# =========================================================
# Find Professionals for Service
# =========================================================


def get_professionals_for_service(
    db: Session,
    service_id: int,
    *,
    active_only: bool = True,
) -> list[Professional]:
    """
    Find professionals who provide a specific service.

    This function checks the ProfessionalService relationship,
    not availability.

    AvailabilityService should be used when a specific date/time
    must also be considered.
    """

    stmt = (
        select(Professional)
        .join(
            ProfessionalService,
            ProfessionalService.professional_id
            == Professional.id,
        )
        .where(
            ProfessionalService.service_id
            == service_id,
        )
    )

    if active_only:
        stmt = stmt.where(
            Professional.is_active.is_(True)
        )

    stmt = stmt.order_by(
        Professional.rating.desc(),
        Professional.name.asc(),
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Backward-Compatible / Phase API Alias
# =========================================================


def get_available_professionals(
    db: Session,
    service_id: int,
    *,
    active_only: bool = True,
) -> list[Professional]:
    """
    Return active professionals capable of providing a service.

    Note:
        This function checks service capability only.

        For professionals available at a specific date/time,
        use availability_service.get_available_professionals().
    """

    return get_professionals_for_service(
        db,
        service_id,
        active_only=active_only,
    )