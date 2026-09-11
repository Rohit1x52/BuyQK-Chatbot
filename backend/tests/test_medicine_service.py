from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


medicine_service = pytest.importorskip(
    "backend.services.medicine_service"
)


from backend.database.base import Base
from backend.models import (
    Category,
    Merchant,
    Product,
)


@pytest.fixture()
def medicine_resources():
    temporary_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temporary_directory.name)
        / "test_medicine_service.db"
    )

    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={
            "check_same_thread": False,
        },
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:
        pharmacy = Merchant(
            business_name="Test Pharmacy",
            category="Pharmacy",
            phone="9999999011",
            email="medicine-service@test.buyqk.com",
            address="Medicine Test Address",
        )

        medicine_category = Category(
            name="Medicine",
        )

        db.add(pharmacy)
        db.add(medicine_category)
        db.flush()

        otc_medicine = Product(
            name="Paracetamol 500mg",
            brand="Test Pharma",
            description="Pain and fever medicine",
            price=30.0,
            stock=50,
            is_available=True,
            merchant_id=pharmacy.id,
            category_id=medicine_category.id,
            prescription_required=False,
        )

        prescription_medicine = Product(
            name="Test Prescription Medicine",
            brand="Test Pharma",
            description="Prescription medicine",
            price=120.0,
            stock=10,
            is_available=True,
            merchant_id=pharmacy.id,
            category_id=medicine_category.id,
            prescription_required=True,
        )

        db.add_all(
            [
                otc_medicine,
                prescription_medicine,
            ]
        )

        db.commit()

        db.refresh(otc_medicine)
        db.refresh(prescription_medicine)

        yield {
            "db": db,
            "otc": otc_medicine,
            "prescription": prescription_medicine,
            "pharmacy": pharmacy,
        }

    finally:
        db.close()
        engine.dispose()
        temporary_directory.cleanup()


def test_search_medicines(
    medicine_resources,
):
    search_medicines = (
        medicine_service.search_medicines
    )

    results = search_medicines(
        db=medicine_resources["db"],
        query="Paracetamol",
    )

    assert results

    assert results[0].name == (
        "Paracetamol 500mg"
    )


def test_search_pharmacies(
    medicine_resources,
):
    search_pharmacies = (
        medicine_service.search_pharmacies
    )

    results = search_pharmacies(
        db=medicine_resources["db"],
    )

    assert results

    assert results[0].business_name == (
        "Test Pharmacy"
    )


def test_prescription_requirement(
    medicine_resources,
):
    check_prescription_requirement = (
        medicine_service.check_prescription_requirement
    )

    db = medicine_resources["db"]

    otc_result = check_prescription_requirement(
        db=db,
        product_id=medicine_resources["otc"].id,
    )

    prescription_result = (
        check_prescription_requirement(
            db=db,
            product_id=medicine_resources["prescription"].id,
        )
    )

    assert otc_result is False
    assert prescription_result is True