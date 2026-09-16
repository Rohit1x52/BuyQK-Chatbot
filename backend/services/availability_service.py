"""
BuyQK Availability Service

Backend-authoritative scheduling logic for Phase 11.

This service determines whether a requested service slot can
actually be booked.

The AI/LLM layer must never determine availability itself.
It may request an availability check, but the result must come
from this service and the database.

Responsibilities:

    - Check requested slot
    - Find available slots
    - Find available professionals
    - Validate professional availability
    - Detect booking conflicts
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.models.availability import Availability
from backend.models.booking import Booking
from backend.models.professional import Professional
from backend.models.professional_service import ProfessionalService


# =========================================================
# Time Validation
# =========================================================


def _validate_time_range(
    start_time: time,
    end_time: time,
) -> None:
    """
    Validate a requested time range.
    """

    if start_time >= end_time:
        raise ValueError(
            "start_time must be earlier than end_time."
        )


# =========================================================
# Availability Slot Query
# =========================================================


def get_available_slots(
    db: Session,
    service_id: int,
    requested_date: date,
    *,
    professional_id: int | None = None,
) -> list[Availability]:
    """
    Find availability windows for a service on a specific date.

    Args:
        db: SQLAlchemy database session.
        service_id: Requested service ID.
        requested_date: Requested service date.
        professional_id: Optional professional filter.

    Returns:
        Availability records currently marked as available.
    """

    stmt = (
        select(Availability)
        .join(
            Professional,
            Professional.id
            == Availability.professional_id,
        )
        .join(
            ProfessionalService,
            and_(
                ProfessionalService.professional_id
                == Availability.professional_id,
                ProfessionalService.service_id
                == Availability.service_id,
            ),
        )
        .where(
            Availability.service_id == service_id,
            Availability.date == requested_date,
            Availability.is_available.is_(True),
            Professional.is_active.is_(True),
        )
    )

    if professional_id is not None:
        stmt = stmt.where(
            Availability.professional_id
            == professional_id
        )

    stmt = stmt.order_by(
        Availability.start_time.asc(),
        Availability.end_time.asc(),
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Booking Conflict Detection
# =========================================================


def _has_booking_conflict(
    db: Session,
    professional_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    """
    Determine whether an existing active booking overlaps
    the requested time range for a professional.

    Two time ranges overlap when:

        existing_start < requested_end
        AND
        existing_end > requested_start

    Cancelled bookings do not block availability.
    """

    stmt = select(Booking.id).where(
        Booking.professional_id == professional_id,
        Booking.date == requested_date,
        Booking.status != "cancelled",
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )

    return db.scalar(stmt) is not None


# =========================================================
# Check Requested Slot
# =========================================================


def check_availability(
    db: Session,
    service_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
    professional_id: int | None = None,
) -> bool:
    """
    Check whether a requested service slot is available.

    If professional_id is provided, the check is performed for
    that specific professional.

    If professional_id is omitted, the function returns True when
    at least one suitable professional is available.

    Availability requires:

        1. Availability record exists.
        2. Availability is marked available.
        3. Professional is active.
        4. Professional provides the requested service.
        5. Requested interval fits inside the availability window.
        6. No conflicting active booking exists.

    Returns:
        True if the requested slot is available, otherwise False.
    """

    _validate_time_range(
        start_time,
        end_time,
    )

    slots = get_available_slots(
        db,
        service_id,
        requested_date,
        professional_id=professional_id,
    )

    for slot in slots:
        if (
            slot.start_time <= start_time
            and slot.end_time >= end_time
        ):
            if _has_booking_conflict(
                db,
                slot.professional_id,
                requested_date,
                start_time,
                end_time,
            ):
                continue

            return True

    return False


# =========================================================
# Find Available Professionals
# =========================================================


def get_available_professionals(
    db: Session,
    service_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
) -> list[Professional]:
    """
    Find professionals who can provide the requested service
    during the requested date/time.

    The returned professionals have:

        - active professional status
        - valid ProfessionalService relationship
        - matching availability
        - no conflicting active booking
    """

    _validate_time_range(
        start_time,
        end_time,
    )

    slots = get_available_slots(
        db,
        service_id,
        requested_date,
    )

    professional_ids: list[int] = []

    for slot in slots:
        if not (
            slot.start_time <= start_time
            and slot.end_time >= end_time
        ):
            continue

        if _has_booking_conflict(
            db,
            slot.professional_id,
            requested_date,
            start_time,
            end_time,
        ):
            continue

        if slot.professional_id not in professional_ids:
            professional_ids.append(
                slot.professional_id
            )

    if not professional_ids:
        return []

    stmt = (
        select(Professional)
        .where(
            Professional.id.in_(professional_ids),
            Professional.is_active.is_(True),
        )
        .order_by(
            Professional.rating.desc(),
            Professional.name.asc(),
        )
    )

    return list(
        db.scalars(stmt).all()
    )


# =========================================================
# Validate Professional Availability
# =========================================================


def validate_professional_availability(
    db: Session,
    professional_id: int,
    service_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    """
    Validate that a specific professional can provide a service
    at the requested date/time.

    This is intended for the final validation immediately before
    booking creation.
    """

    return check_availability(
        db,
        service_id=service_id,
        requested_date=requested_date,
        start_time=start_time,
        end_time=end_time,
        professional_id=professional_id,
    )


# =========================================================
# Detailed Availability Result
# =========================================================


def get_availability_details(
    db: Session,
    service_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
    professional_id: int | None = None,
) -> dict:
    """
    Return a structured backend availability result.

    This is useful for the AI Tool Node because the AI layer can
    consume a deterministic result without implementing scheduling
    logic itself.
    """

    available = check_availability(
        db,
        service_id=service_id,
        requested_date=requested_date,
        start_time=start_time,
        end_time=end_time,
        professional_id=professional_id,
    )

    if professional_id is not None:
        professionals = []

        if available:
            professional = db.get(
                Professional,
                professional_id,
            )

            if professional is not None:
                professionals.append(
                    professional
                )

    else:
        professionals = get_available_professionals(
            db,
            service_id=service_id,
            requested_date=requested_date,
            start_time=start_time,
            end_time=end_time,
        )

    return {
        "available": available,
        "service_id": service_id,
        "date": requested_date.isoformat(),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "professional_id": professional_id,
        "available_professionals": [
            {
                "id": professional.id,
                "name": professional.name,
                "specialization": professional.specialization,
                "rating": professional.rating,
            }
            for professional in professionals
        ],
    }