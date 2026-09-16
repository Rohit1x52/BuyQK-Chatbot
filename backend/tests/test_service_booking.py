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
from backend.services.booking_service import (
    BOOKING_STATUS_CANCELLED,
    BOOKING_STATUS_CONFIRMED,
    create_booking,
    cancel_booking,
    get_booking,
)
from backend.services.professional_service import (
    get_professional,
    get_professionals_for_service,
)
from backend.services.service_service import get_service, search_services


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    user = User(
        name="Service Booking Test User",
        email="service-booking-test@example.com",
        phone="9999999999",
        password_hash="test-only",
    )
    session.add(user)
    session.flush()

    address = Address(
        user_id=user.id,
        address="123 Test Street",
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
    professional = Professional(
        name="Test Technician",
        phone="8888888888",
        email="technician@example.com",
        specialization="AC Repair",
        rating=4.8,
        is_active=True,
    )
    session.add_all([address, service, professional])
    session.flush()

    mapping = ProfessionalService(
        professional_id=professional.id,
        service_id=service.id,
    )
    availability = Availability(
        professional_id=professional.id,
        service_id=service.id,
        date=date(2026, 9, 20),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_available=True,
    )
    session.add_all([mapping, availability])
    session.commit()

    try:
        yield {
            "db": session,
            "user": user,
            "address": address,
            "service": service,
            "professional": professional,
        }
    finally:
        session.close()
        engine.dispose()


def test_service_lookup(db):
    data = db
    service = get_service(data["db"], data["service"].id)

    assert service is not None
    assert service.id == data["service"].id
    assert service.name == "AC Repair"

    results = search_services(data["db"], query="AC")
    assert any(item.id == data["service"].id for item in results)


def test_professional_lookup(db):
    data = db
    professional = get_professional(data["db"], data["professional"].id)

    assert professional is not None
    assert professional.name == "Test Technician"


def test_professional_service_relationship(db):
    data = db
    professionals = get_professionals_for_service(
        data["db"],
        data["service"].id,
    )

    assert [professional.id for professional in professionals] == [
        data["professional"].id
    ]


def test_booking_creation(db):
    data = db
    booking_date = date(2026, 9, 20)
    start_time = time(16, 0)
    end_time = time(17, 0)

    booking = create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=booking_date,
        start_time=start_time,
        end_time=end_time,
    )

    assert booking.id is not None
    assert booking.user_id == data["user"].id
    assert booking.service_id == data["service"].id
    assert booking.professional_id == data["professional"].id
    assert booking.address_id == data["address"].id
    assert booking.status == BOOKING_STATUS_CONFIRMED


def test_booking_retrieval(db):
    data = db
    booking = create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=date(2026, 9, 20),
        start_time=time(16, 0),
        end_time=time(17, 0),
    )

    retrieved = get_booking(
        data["db"],
        booking.id,
        user_id=data["user"].id,
    )

    assert retrieved is not None
    assert retrieved.id == booking.id


def test_booking_cancellation(db):
    data = db
    booking = create_booking(
        db=data["db"],
        user_id=data["user"].id,
        service_id=data["service"].id,
        professional_id=data["professional"].id,
        address_id=data["address"].id,
        requested_date=date(2026, 9, 20),
        start_time=time(16, 0),
        end_time=time(17, 0),
    )

    cancelled = cancel_booking(
        db=data["db"],
        booking_id=booking.id,
        user_id=data["user"].id,
    )

    assert cancelled is not None
    assert cancelled.status == BOOKING_STATUS_CANCELLED

    retrieved = get_booking(
        data["db"],
        booking.id,
        user_id=data["user"].id,
    )
    assert retrieved is not None
    assert retrieved.status == BOOKING_STATUS_CANCELLED
