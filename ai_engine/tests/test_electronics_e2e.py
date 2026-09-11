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
def electronics_resources():
    temporary_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temporary_directory.name)
        / "test_electronics_e2e.db"
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
            name="Electronics Test User",
            email="electronics@test.buyqk.com",
            phone="9999999005",
            password_hash="test-password-hash",
        )

        db.add(user)
        db.flush()

        merchant = Merchant(
            business_name="Test Electronics Store",
            category="Electronics",
            phone="9999999006",
            email="electronics-store@test.buyqk.com",
            address="Test Electronics Address",
        )

        db.add(merchant)
        db.flush()

        category = Category(
            name="Smartphones",
        )

        db.add(category)
        db.flush()

        phone = Product(
            name="TestPhone X",
            brand="TestBrand",
            description="5G smartphone",
            price=29999.0,
            stock=10,
            is_available=True,
            merchant_id=merchant.id,
            category_id=category.id,
            model_number="TPX-500",
            specifications={
                "ram": "8GB",
                "storage": "128GB",
                "display": "6.5 inch",
                "network": "5G",
            },
        )

        db.add(phone)
        db.commit()

        db.refresh(user)
        db.refresh(phone)

        yield {
            "db": db,
            "user": user,
            "merchant": merchant,
            "category": category,
            "phone": phone,
        }

    finally:
        db.close()
        engine.dispose()
        temporary_directory.cleanup()


# =========================================================
# Electronics E2E
# =========================================================


def test_electronics_search_with_specifications(
    electronics_resources,
):
    """
    Validate that electronics products can travel through
    the existing generic product-search path while retaining
    model/specification metadata.
    """

    from ai_engine.graph.runner import run_chat

    db = electronics_resources["db"]
    user = electronics_resources["user"]
    phone = electronics_resources["phone"]

    result = run_chat(
        message="Find TestPhone X",
        session_id="phase10-electronics-search-001",
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

    # -----------------------------------------------------
    # Authoritative product identity
    # -----------------------------------------------------

    assert returned_product["id"] == phone.id
    assert returned_product["name"] == "TestPhone X"

    # -----------------------------------------------------
    # Electronics metadata
    # -----------------------------------------------------

    assert (
        returned_product.get(
            "model_number"
        )
        == "TPX-500"
    )

    specifications = returned_product.get(
        "specifications"
    )

    assert isinstance(
        specifications,
        dict,
    )

    assert specifications["ram"] == "8GB"
    assert specifications["storage"] == "128GB"
    assert specifications["network"] == "5G"