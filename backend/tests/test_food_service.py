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


from backend.database.base import Base
from backend.models import (
    Category,
    Merchant,
    Product,
)
from backend.services.product_service import (
    search_products,
)


# =========================================================
# Fixtures
# =========================================================


@pytest.fixture()
def db():
    temporary_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temporary_directory.name)
        / "test_food_service.db"
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

    session = SessionLocal()

    try:
        merchant = Merchant(
            business_name="Test Food Restaurant",
            category="Restaurant",
            phone="9999999010",
            email="food-service@test.buyqk.com",
            address="Food Test Address",
        )

        db_category = Category(
            name="Food",
        )

        session.add(
            merchant
        )
        session.add(
            db_category
        )

        session.flush()

        pizza = Product(
            name="Margherita Pizza",
            brand="Test Kitchen",
            description="Fresh vegetarian pizza",
            price=249.0,
            stock=20,
            is_available=True,
            merchant_id=merchant.id,
            category_id=db_category.id,
        )

        burger = Product(
            name="Veg Burger",
            brand="Test Kitchen",
            description="Fresh vegetarian burger",
            price=149.0,
            stock=15,
            is_available=True,
            merchant_id=merchant.id,
            category_id=db_category.id,
        )

        session.add_all(
            [
                pizza,
                burger,
            ]
        )

        session.commit()

        yield session

    finally:
        session.close()
        engine.dispose()
        temporary_directory.cleanup()


# =========================================================
# Food Service Tests
# =========================================================


def test_search_food_product(
    db,
):
    results = search_products(
        db=db,
        query="Margherita Pizza",
    )

    assert results

    assert results[0].name == (
        "Margherita Pizza"
    )

    assert results[0].price == 249.0


def test_search_food_by_description(
    db,
):
    results = search_products(
        db=db,
        query="vegetarian",
    )

    assert len(results) >= 2

    names = {
        product.name
        for product in results
    }

    assert "Margherita Pizza" in names
    assert "Veg Burger" in names