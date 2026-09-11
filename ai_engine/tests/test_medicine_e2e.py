from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY is required for AI graph E2E tests.",
)


# =========================================================
# Backend
# =========================================================

from backend.database.base import Base
from backend.models import (
    Category,
    Merchant,
    Product,
    User,
)


# =========================================================
# Fixtures
# =========================================================


@pytest.fixture()
def medicine_resources():
    temporary_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temporary_directory.name)
        / "test_medicine_e2e.db"
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
        user = User(
            name="Medicine Test User",
            email="medicine@test.buyqk.com",
            phone="9999999003",
            password_hash="test-password-hash",
        )

        db.add(user)
        db.flush()

        pharmacy = Merchant(
            business_name="Test Pharmacy",
            category="Pharmacy",
            phone="9999999004",
            email="pharmacy@test.buyqk.com",
            address="Test Pharmacy Address",
        )

        db.add(pharmacy)
        db.flush()

        category = Category(
            name="Medicine",
        )

        db.add(category)
        db.flush()

        medicine = Product(
            name="Paracetamol 500mg",
            brand="Test Pharma",
            description="Pain and fever medicine",
            price=30.0,
            stock=50,
            is_available=True,
            merchant_id=pharmacy.id,
            category_id=category.id,
            prescription_required=False,
        )

        db.add(medicine)
        db.commit()

        db.refresh(user)
        db.refresh(medicine)

        yield {
            "db": db,
            "user": user,
            "pharmacy": pharmacy,
            "category": category,
            "medicine": medicine,
        }

    finally:
        db.close()
        engine.dispose()
        temporary_directory.cleanup()


# =========================================================
# Medicine E2E
# =========================================================


def test_medicine_search_and_prescription_metadata(
    medicine_resources,
):
    """
    Validate medicine search through the existing
    product-search execution path.

    The backend remains authoritative for:
        - product ID
        - price
        - stock
        - availability
        - prescription requirement
    """

    from ai_engine.graph.runner import run_chat

    db = medicine_resources["db"]
    user = medicine_resources["user"]
    medicine = medicine_resources["medicine"]

    result = run_chat(
        message="Find Paracetamol 500mg",
        session_id="phase10-medicine-search-001",
        user_id=user.id,
        db=db,
    )

    # -----------------------------------------------------
    # Intent
    # -----------------------------------------------------

    assert result.get(
        "intent"
    ) == "product_search"

    # -----------------------------------------------------
    # Tool
    # -----------------------------------------------------

    assert result.get(
        "tool_name"
    ) == "search_products"

    # -----------------------------------------------------
    # Tool Result
    # -----------------------------------------------------

    tool_result = result.get(
        "tool_result"
    )

    assert tool_result is not None
    assert tool_result.success is True

    products = tool_result.data.get(
        "products",
        [],
    )

    assert products

    returned_product = products[0]

    assert returned_product["id"] == medicine.id
    assert returned_product["name"] == "Paracetamol 500mg"

    # -----------------------------------------------------
    # Medicine-specific metadata
    # -----------------------------------------------------

    assert (
        returned_product.get(
            "prescription_required"
        )
        is False
    )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    response = result.get(
        "response",
        "",
    )

    assert response
    assert "Paracetamol 500mg" in response