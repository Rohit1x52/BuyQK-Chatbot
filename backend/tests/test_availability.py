from __future__ import annotations

from datetime import date, time
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import models  # noqa: F401
from backend.database.base import Base
from backend.models.address import Address
from backend.models.availability import Availability
from backend.models.professional import Professional
from backend.models.professional_service import ProfessionalService
from backend.models.service import Service
from backend.models.user import User
from backend.services.availability_service import (
    check_availability,
    get_available_professionals,
    get_available_slots,
)
from backend.services.booking_service import create_booking

TEST_DATE = date(2026, 9, 20)
SLOT_START = time(16, 0)
SLOT_END = time(17, 0)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    user = User(
        name="Availability Test User",
        email="availability-test@example.com",
        phone="9999999998",
        password_hash="test-only",
    )
    session.add(user)
    session.flush()

    address = Address(
        user_id=user.id,
        address="123 Availability Street",
        city="Jaipur",
        state="Rajasthan",
        postal_code="302001",
    )
    service = Service(
        name="AC Repair",
        description="Air conditioner repair",
        category="Home Services",
        base_price=499.0,
        duration_minutes=60,
        is_active=True,
    )
    other_service = Service(
        name="Plumbing",
        description="Plumbing service",
        category="Home Services",
        base_price=399.0,
        duration_minutes=60,
        is_active=True,
    )
    professional = Professional(
        name="Availability Technician",
        specialization="AC Repair",
        rating=4.7,
        is_active=True,
    )
    other_professional = Professional(
        name="Other Technician",
        specialization="Plumbing",
        rating=4.4,
        is_active=True,
    )
    session.add_all([
        address,
        service,
        other_service,
        professional,
        other_professional,
    ])
    session.flush()

    session.add_all([
        ProfessionalService(
            professional_id=professional.id,
            service_id=service.id,
        ),
        ProfessionalService(
            professional_id=other_professional.id,
            service_id=other_service.id,
        ),
        Availability(
            professional_id=professional.id,
            service_id=service.id,
            date=TEST_DATE,
            start_time=SLOT_START,
            end_time=SLOT_END,
            is_available=True,
        ),
        Availability(
            professional_id=professional.id,
            service_id=service.id,
            date=TEST_DATE,
            start_time=time(18, 0),
            end_time=time(19, 0),
            is_available=False,
        ),
    ])
    session.commit()

    try:
        yield {
            "db": session,
            "user": user,
            "address": address,
            "service": service,
            "other_service": other_service,
            "professional": professional,
            "other_professional": other_professional,
        }
    finally:
        session.close()
        engine.dispose()


def test_available_slot(db):
    data = db

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
        professional_id=data["professional"].id,
    ) is True

    slots = get_available_slots(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        professional_id=data["professional"].id,
    )
    assert any(
        slot.start_time == SLOT_START and slot.end_time == SLOT_END
        for slot in slots
    )


def test_unavailable_slot(db):
    data = db

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=time(18, 0),
        end_time=time(19, 0),
        professional_id=data["professional"].id,
    ) is False


def test_wrong_service(db):
    data = db

    assert check_availability(
        db=data["db"],
        service_id=data["other_service"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
        professional_id=data["professional"].id,
    ) is False


def test_wrong_professional(db):
    data = db

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
        professional_id=data["other_professional"].id,
    ) is False


def test_outside_working_hours(db):
    data = db

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=time(8, 0),
        end_time=time(9, 0),
        professional_id=data["professional"].id,
    ) is False


def test_already_booked(db):
    data = db

    create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
    )

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
        professional_id=data["professional"].id,
    ) is False


def test_overlapping_booking(db):
    data = db

    create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
    )

    assert check_availability(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=time(16, 30),
        end_time=time(17, 30),
        professional_id=data["professional"].id,
    ) is False


def test_available_professionals_are_backend_derived(db):
    data = db

    professionals = get_available_professionals(
        db=data["db"],
        service_id=data["service"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
    )

    assert [professional.id for professional in professionals] == [
        data["professional"].id
    ]


def test_final_availability_check_rejects_stale_slot(db):
    data = db

    first_booking = create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=TEST_DATE,
        start_time=SLOT_START,
        end_time=SLOT_END,
    )
    assert first_booking.id is not None

    with pytest.raises(ValueError):
        create_booking(
            db=data["db"],
            user_id=data["user"].id,
            service_id=data["service"].id,
            professional_id=data["professional"].id,
            address_id=data["address"].id,
            requested_date=TEST_DATE,
            start_time=SLOT_START,
            end_time=SLOT_END,
        )
