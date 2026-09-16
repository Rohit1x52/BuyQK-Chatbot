"""
BuyQK Booking Service

Handles the transactional lifecycle of service bookings.

Responsibilities:

    - Create booking
    - Get booking
    - Cancel booking
    - Validate booking
    - Prevent double booking

Important:

    Booking availability is backend-authoritative.

    create_booking() performs a FINAL availability check inside
    the same database transaction immediately before creating
    the booking.

The AI/LLM layer must never create or confirm a booking directly.
It may request a booking operation, but this service is responsible
for validating and committing the transaction.
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.booking import Booking
from backend.models.service import Service

from backend.services.address_service import get_address
from backend.services.availability_service import (
    check_availability,
)
from backend.services.professional_service import (
    validate_professional,
    validate_professional_service,
)
from backend.services.service_service import validate_service


# =========================================================
# Booking Statuses
# =========================================================

BOOKING_STATUS_PENDING = "pending"
BOOKING_STATUS_CONFIRMED = "confirmed"
BOOKING_STATUS_CANCELLED = "cancelled"
BOOKING_STATUS_COMPLETED = "completed"


# =========================================================
# Payment Statuses
# =========================================================

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_SUCCESS = "success"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"


# =========================================================
# Booking Validation
# =========================================================


def validate_booking(
    db: Session,
    *,
    user_id: int,
    service_id: int,
    professional_id: int,
    address_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
) -> None:
    """
    Validate the structural requirements for a booking.

    This function does not create or commit anything.

    Availability is checked separately and again inside
    create_booking() immediately before insertion.
    """

    if user_id <= 0:
        raise ValueError(
            "A valid user_id is required."
        )

    if address_id <= 0:
        raise ValueError(
            "A valid address_id is required."
        )

    if requested_date is None:
        raise ValueError(
            "A booking date is required."
        )

    if start_time is None or end_time is None:
        raise ValueError(
            "Booking start and end times are required."
        )

    if start_time >= end_time:
        raise ValueError(
            "start_time must be earlier than end_time."
        )

    # ---------------------------------------------------------
    # Validate service.
    # ---------------------------------------------------------

    validate_service(
        db,
        service_id,
        require_active=True,
    )

    # ---------------------------------------------------------
    # Validate professional.
    # ---------------------------------------------------------

    validate_professional(
        db,
        professional_id,
        require_active=True,
    )

    # ---------------------------------------------------------
    # Validate professional/service relationship.
    # ---------------------------------------------------------

    validate_professional_service(
        db,
        professional_id,
        service_id,
    )

    # ---------------------------------------------------------
    # Validate address ownership.
    # ---------------------------------------------------------

    address = get_address(
        db,
        address_id,
        user_id=user_id,
    )

    if address is None:
        raise ValueError(
            "The selected address does not belong to the user "
            "or does not exist."
        )


# =========================================================
# Create Booking
# =========================================================


def create_booking(
    db: Session,
    *,
    user_id: int,
    service_id: int,
    professional_id: int,
    address_id: int,
    requested_date: date,
    start_time: time,
    end_time: time,
    payment_status: str = PAYMENT_STATUS_PENDING,
) -> Booking:
    """
    Create a service booking transactionally.

    Transaction flow:

        BEGIN TRANSACTION
              ↓
        Validate booking data
              ↓
        FINAL availability check
              ↓
        If unavailable → raise / rollback
              ↓
        Create booking
              ↓
        Flush
              ↓
        Commit
              ↓
        Return booking

    The caller should pass a normal SQLAlchemy Session. This function
    owns the commit/rollback boundary for the booking operation.

    Raises:
        ValueError:
            If booking data is invalid or the requested slot is no
            longer available.

    Returns:
        The newly created Booking.
    """

    try:
        # -----------------------------------------------------
        # Validate structural booking requirements.
        # -----------------------------------------------------

        validate_booking(
            db,
            user_id=user_id,
            service_id=service_id,
            professional_id=professional_id,
            address_id=address_id,
            requested_date=requested_date,
            start_time=start_time,
            end_time=end_time,
        )

        # -----------------------------------------------------
        # FINAL AVAILABILITY CHECK
        #
        # This is intentionally performed immediately before
        # creating the booking.
        # -----------------------------------------------------

        is_available = check_availability(
            db,
            service_id=service_id,
            requested_date=requested_date,
            start_time=start_time,
            end_time=end_time,
            professional_id=professional_id,
        )

        if not is_available:
            raise ValueError(
                "The requested time slot is no longer available."
            )

        service = validate_service(
            db,
            service_id,
            require_active=True,
        )

        # -----------------------------------------------------
        # Create booking.
        # -----------------------------------------------------

        booking = Booking(
            user_id=user_id,
            service_id=service_id,
            professional_id=professional_id,
            address_id=address_id,
            date=requested_date,
            start_time=start_time,
            end_time=end_time,
            status=BOOKING_STATUS_CONFIRMED,
            total_amount=service.base_price,
            payment_status=payment_status,
        )

        db.add(booking)

        # -----------------------------------------------------
        # Flush so SQLAlchemy sends INSERT before commit.
        #
        # This also ensures generated fields such as booking.id
        # are available before returning.
        # -----------------------------------------------------

        db.flush()

        # -----------------------------------------------------
        # Commit transaction.
        # -----------------------------------------------------

        db.commit()

        # Refresh the object after commit.
        db.refresh(booking)

        return booking

    except Exception:
        # -----------------------------------------------------
        # Any failure, including availability failure, rolls
        # the transaction back.
        # -----------------------------------------------------

        db.rollback()
        raise


# =========================================================
# Get Booking
# =========================================================


def get_booking(
    db: Session,
    booking_id: int,
    *,
    user_id: int | None = None,
) -> Booking | None:
    """
    Retrieve a booking.

    If user_id is supplied, only a booking belonging to that
    user is returned.
    """

    if booking_id <= 0:
        return None

    stmt = select(Booking).where(
        Booking.id == booking_id,
    )

    if user_id is not None:
        stmt = stmt.where(
            Booking.user_id == user_id,
        )

    return db.scalar(stmt)


# =========================================================
# Cancel Booking
# =========================================================


def cancel_booking(
    db: Session,
    booking_id: int,
    *,
    user_id: int,
) -> Booking:
    """
    Cancel a user's booking.

    A booking can only be cancelled by its owner.

    Completed and already-cancelled bookings cannot be cancelled.

    Raises:
        ValueError: If the booking does not exist, does not belong
                    to the user, or cannot be cancelled.

    Returns:
        The cancelled Booking.
    """

    booking = get_booking(
        db,
        booking_id,
        user_id=user_id,
    )

    if booking is None:
        raise ValueError(
            "Booking not found."
        )

    if booking.status == BOOKING_STATUS_CANCELLED:
        raise ValueError(
            "Booking is already cancelled."
        )

    if booking.status == BOOKING_STATUS_COMPLETED:
        raise ValueError(
            "A completed booking cannot be cancelled."
        )

    try:
        booking.status = BOOKING_STATUS_CANCELLED

        db.commit()
        db.refresh(booking)

        return booking

    except Exception:
        db.rollback()
        raise