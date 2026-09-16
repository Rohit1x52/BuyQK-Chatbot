"""
BuyQK Service Catalog Service

Handles discovery and validation of bookable services.

This service is responsible only for service catalog operations.
Availability, professionals, and bookings are handled by their
respective services.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.models.service import Service


# =========================================================
# Service Search
# =========================================================


def search_services(
    db: Session,
    query: str | None = None,
    category: str | None = None,
    *,
    active_only: bool = True,
    limit: int = 20,
) -> list[Service]:
    """
    Search the service catalog.

    Args:
        db: SQLAlchemy database session.
        query: Optional text to search in service name/description.
        category: Optional service category filter.
        active_only: Return only active services when True.
        limit: Maximum number of results.

    Returns:
        List of matching Service objects.
    """

    if limit <= 0:
        return []

    stmt = select(Service)

    if active_only:
        stmt = stmt.where(
            Service.is_active.is_(True)
        )

    if category:
        stmt = stmt.where(
            Service.category == category
        )

    if query:
        search_term = f"%{query.strip()}%"

        stmt = stmt.where(
            or_(
                Service.name.ilike(search_term),
                Service.description.ilike(search_term),
            )
        )

    stmt = (
        stmt
        .order_by(Service.name.asc())
        .limit(limit)
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Get Service
# =========================================================


def get_service(
    db: Session,
    service_id: int,
) -> Service | None:
    """
    Retrieve a service by ID.

    Returns:
        Service if found, otherwise None.
    """

    if service_id <= 0:
        return None

    return db.get(
        Service,
        service_id,
    )


# =========================================================
# Validate Service
# =========================================================


def validate_service(
    db: Session,
    service_id: int,
    *,
    require_active: bool = True,
) -> Service:
    """
    Validate that a service exists and, by default, is active.

    Raises:
        ValueError: If the service does not exist or is inactive.

    Returns:
        Validated Service object.
    """

    service = get_service(
        db,
        service_id,
    )

    if service is None:
        raise ValueError(
            f"Service {service_id} does not exist."
        )

    if require_active and not service.is_active:
        raise ValueError(
            f"Service {service_id} is currently inactive."
        )

    return service