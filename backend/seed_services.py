"""
BuyQK Service Booking Seeder

Seeds the initial service-booking catalog for Phase 11.

The seed data covers:

    Services
        ↓
    Professionals
        ↓
    Professional-Service mappings
        ↓
    Availability slots

The seeder is intentionally separate from seed_products.py because
product catalog data and service-booking data are different domains.

The seeder is idempotent:
running it multiple times will not create duplicate records.
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select

from backend.database.base import Base
from backend.database.sqlite import SessionLocal, engine
from backend.models import (
    Availability,
    Professional,
    ProfessionalService,
    Service,
)


# =========================================================
# Seed Data
# =========================================================

SERVICES = [
    {
        "name": "AC Repair",
        "description": (
            "Professional air conditioner repair and maintenance "
            "service for home and office AC units."
        ),
        "category": "home_repair",
        "base_price": 499.0,
        "duration_minutes": 60,
    },
    {
        "name": "Plumbing",
        "description": (
            "Professional plumbing service for common household "
            "repairs, leaks, fittings, and installations."
        ),
        "category": "home_repair",
        "base_price": 399.0,
        "duration_minutes": 60,
    },
    {
        "name": "Electrician",
        "description": (
            "Professional electrical repair and installation "
            "service for household electrical work."
        ),
        "category": "electrical",
        "base_price": 349.0,
        "duration_minutes": 60,
    },
    {
        "name": "Home Cleaning",
        "description": (
            "Professional home cleaning service for routine "
            "residential cleaning."
        ),
        "category": "cleaning",
        "base_price": 599.0,
        "duration_minutes": 120,
    },
    {
        "name": "Appliance Repair",
        "description": (
            "Professional repair service for common household "
            "appliances."
        ),
        "category": "appliance_repair",
        "base_price": 449.0,
        "duration_minutes": 60,
    },
    {
        "name": "Car Wash",
        "description": (
            "Professional vehicle cleaning and car wash service."
        ),
        "category": "automotive",
        "base_price": 299.0,
        "duration_minutes": 60,
    },
    {
        "name": "Salon at Home",
        "description": (
            "Professional salon and grooming services delivered "
            "at the customer's home."
        ),
        "category": "beauty",
        "base_price": 699.0,
        "duration_minutes": 90,
    },
]


PROFESSIONALS = [
    {
        "name": "Amit Sharma",
        "phone": "9876500001",
        "email": "amit.sharma@buyqk.example",
        "specialization": "AC Technician",
        "rating": 4.7,
    },
    {
        "name": "Rahul Verma",
        "phone": "9876500002",
        "email": "rahul.verma@buyqk.example",
        "specialization": "Home Appliance Technician",
        "rating": 4.6,
    },
    {
        "name": "Vikram Singh",
        "phone": "9876500003",
        "email": "vikram.singh@buyqk.example",
        "specialization": "Plumber",
        "rating": 4.8,
    },
    {
        "name": "Suresh Kumar",
        "phone": "9876500004",
        "email": "suresh.kumar@buyqk.example",
        "specialization": "Electrician",
        "rating": 4.5,
    },
    {
        "name": "Neha Gupta",
        "phone": "9876500005",
        "email": "neha.gupta@buyqk.example",
        "specialization": "Home Cleaning Specialist",
        "rating": 4.9,
    },
    {
        "name": "Arjun Mehta",
        "phone": "9876500006",
        "email": "arjun.mehta@buyqk.example",
        "specialization": "Automotive Cleaning Specialist",
        "rating": 4.6,
    },
    {
        "name": "Priya Sharma",
        "phone": "9876500007",
        "email": "priya.sharma@buyqk.example",
        "specialization": "Salon Professional",
        "rating": 4.8,
    },
]


# =========================================================
# Professional-Service Relationships
# =========================================================

PROFESSIONAL_SERVICES = {
    "Amit Sharma": [
        "AC Repair",
        "Appliance Repair",
    ],
    "Rahul Verma": [
        "AC Repair",
        "Appliance Repair",
    ],
    "Vikram Singh": [
        "Plumbing",
    ],
    "Suresh Kumar": [
        "Electrician",
    ],
    "Neha Gupta": [
        "Home Cleaning",
    ],
    "Arjun Mehta": [
        "Car Wash",
    ],
    "Priya Sharma": [
        "Salon at Home",
    ],
}


# =========================================================
# Availability
# =========================================================
#
# The dates below are deliberately fixed so that the seeded
# data remains deterministic.
#
# These slots are enough to test:
#
#   - multiple professionals for one service
#   - multiple slots for one professional
#   - unavailable slots
#   - different services
#   - professional selection
#
# =========================================================

AVAILABILITY = [
    # ---------------------------------------------------------
    # AC Repair
    # ---------------------------------------------------------

    {
        "professional": "Amit Sharma",
        "service": "AC Repair",
        "date": date(2026, 9, 15),
        "start_time": time(10, 0),
        "end_time": time(11, 0),
        "is_available": True,
    },
    {
        "professional": "Amit Sharma",
        "service": "AC Repair",
        "date": date(2026, 9, 15),
        "start_time": time(16, 0),
        "end_time": time(17, 0),
        "is_available": True,
    },
    {
        "professional": "Rahul Verma",
        "service": "AC Repair",
        "date": date(2026, 9, 15),
        "start_time": time(16, 0),
        "end_time": time(17, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Appliance Repair
    # ---------------------------------------------------------

    {
        "professional": "Rahul Verma",
        "service": "Appliance Repair",
        "date": date(2026, 9, 15),
        "start_time": time(11, 0),
        "end_time": time(12, 0),
        "is_available": True,
    },
    {
        "professional": "Amit Sharma",
        "service": "Appliance Repair",
        "date": date(2026, 9, 15),
        "start_time": time(14, 0),
        "end_time": time(15, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Plumbing
    # ---------------------------------------------------------

    {
        "professional": "Vikram Singh",
        "service": "Plumbing",
        "date": date(2026, 9, 15),
        "start_time": time(10, 0),
        "end_time": time(11, 0),
        "is_available": True,
    },
    {
        "professional": "Vikram Singh",
        "service": "Plumbing",
        "date": date(2026, 9, 15),
        "start_time": time(15, 0),
        "end_time": time(16, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Electrician
    # ---------------------------------------------------------

    {
        "professional": "Suresh Kumar",
        "service": "Electrician",
        "date": date(2026, 9, 15),
        "start_time": time(9, 0),
        "end_time": time(10, 0),
        "is_available": True,
    },
    {
        "professional": "Suresh Kumar",
        "service": "Electrician",
        "date": date(2026, 9, 15),
        "start_time": time(17, 0),
        "end_time": time(18, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Home Cleaning
    # ---------------------------------------------------------

    {
        "professional": "Neha Gupta",
        "service": "Home Cleaning",
        "date": date(2026, 9, 15),
        "start_time": time(9, 0),
        "end_time": time(11, 0),
        "is_available": True,
    },
    {
        "professional": "Neha Gupta",
        "service": "Home Cleaning",
        "date": date(2026, 9, 15),
        "start_time": time(14, 0),
        "end_time": time(16, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Car Wash
    # ---------------------------------------------------------

    {
        "professional": "Arjun Mehta",
        "service": "Car Wash",
        "date": date(2026, 9, 15),
        "start_time": time(10, 0),
        "end_time": time(11, 0),
        "is_available": True,
    },
    {
        "professional": "Arjun Mehta",
        "service": "Car Wash",
        "date": date(2026, 9, 15),
        "start_time": time(16, 0),
        "end_time": time(17, 0),
        "is_available": True,
    },

    # ---------------------------------------------------------
    # Salon at Home
    # ---------------------------------------------------------

    {
        "professional": "Priya Sharma",
        "service": "Salon at Home",
        "date": date(2026, 9, 15),
        "start_time": time(11, 0),
        "end_time": time(12, 30),
        "is_available": True,
    },
    {
        "professional": "Priya Sharma",
        "service": "Salon at Home",
        "date": date(2026, 9, 15),
        "start_time": time(17, 0),
        "end_time": time(18, 30),
        "is_available": True,
    },
]


# =========================================================
# Seed Helpers
# =========================================================


def _get_or_create_service(
    db,
    data: dict,
) -> Service:
    """
    Get an existing service or create it if it does not exist.
    """

    service = db.scalar(
        select(Service).where(
            Service.name == data["name"]
        )
    )

    if service is not None:
        return service

    service = Service(
        name=data["name"],
        description=data["description"],
        category=data["category"],
        base_price=data["base_price"],
        duration_minutes=data["duration_minutes"],
        is_active=True,
    )

    db.add(service)
    db.flush()

    return service


def _get_or_create_professional(
    db,
    data: dict,
) -> Professional:
    """
    Get an existing professional or create it if it does not exist.
    """

    professional = db.scalar(
        select(Professional).where(
            Professional.email == data["email"]
        )
    )

    if professional is not None:
        return professional

    professional = Professional(
        name=data["name"],
        phone=data["phone"],
        email=data["email"],
        specialization=data["specialization"],
        rating=data["rating"],
        is_active=True,
    )

    db.add(professional)
    db.flush()

    return professional


def _ensure_professional_service(
    db,
    professional: Professional,
    service: Service,
) -> ProfessionalService:
    """
    Ensure a professional-service relationship exists.
    """

    relationship = db.scalar(
        select(ProfessionalService).where(
            ProfessionalService.professional_id
            == professional.id,
            ProfessionalService.service_id
            == service.id,
        )
    )

    if relationship is not None:
        return relationship

    relationship = ProfessionalService(
        professional_id=professional.id,
        service_id=service.id,
    )

    db.add(relationship)
    db.flush()

    return relationship


def _ensure_availability(
    db,
    professional: Professional,
    service: Service,
    data: dict,
) -> Availability:
    """
    Ensure an availability slot exists.

    The combination of professional, service, date, start_time,
    and end_time identifies a seeded availability slot.
    """

    availability = db.scalar(
        select(Availability).where(
            Availability.professional_id
            == professional.id,
            Availability.service_id
            == service.id,
            Availability.date
            == data["date"],
            Availability.start_time
            == data["start_time"],
            Availability.end_time
            == data["end_time"],
        )
    )

    if availability is not None:
        return availability

    availability = Availability(
        professional_id=professional.id,
        service_id=service.id,
        date=data["date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        is_available=data["is_available"],
    )

    db.add(availability)
    db.flush()

    return availability


# =========================================================
# Main Seeder
# =========================================================


def seed_services(
    *,
    auto_init: bool = True,
) -> None:
    """
    Seed BuyQK service-booking data.

    Args:
        auto_init:
            When True, initialize the database before seeding.
            Set to False when the database has already been
            initialized by init_db().
    """

    if auto_init:
        Base.metadata.create_all(
            bind=engine,
        )

    db = SessionLocal()

    try:
        # -----------------------------------------------------
        # Services
        # -----------------------------------------------------

        services_by_name: dict[str, Service] = {}

        for service_data in SERVICES:
            service = _get_or_create_service(
                db,
                service_data,
            )

            services_by_name[
                service.name
            ] = service

        # -----------------------------------------------------
        # Professionals
        # -----------------------------------------------------

        professionals_by_name: dict[str, Professional] = {}

        for professional_data in PROFESSIONALS:
            professional = _get_or_create_professional(
                db,
                professional_data,
            )

            professionals_by_name[
                professional.name
            ] = professional

        # -----------------------------------------------------
        # Professional-Service mappings
        # -----------------------------------------------------

        for professional_name, service_names in (
            PROFESSIONAL_SERVICES.items()
        ):
            professional = professionals_by_name[
                professional_name
            ]

            for service_name in service_names:
                service = services_by_name[
                    service_name
                ]

                _ensure_professional_service(
                    db,
                    professional,
                    service,
                )

        # -----------------------------------------------------
        # Availability
        # -----------------------------------------------------

        for availability_data in AVAILABILITY:
            professional = professionals_by_name[
                availability_data["professional"]
            ]

            service = services_by_name[
                availability_data["service"]
            ]

            _ensure_availability(
                db,
                professional,
                service,
                availability_data,
            )

        db.commit()

        print(
            "[SERVICE SEED] Service catalog seeded successfully."
        )
        print(
            f"[SERVICE SEED] Services: {len(SERVICES)}"
        )
        print(
            f"[SERVICE SEED] Professionals: "
            f"{len(PROFESSIONALS)}"
        )
        print(
            f"[SERVICE SEED] Availability slots: "
            f"{len(AVAILABILITY)}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Standalone Execution
# =========================================================

if __name__ == "__main__":
    seed_services()