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


# =========================================================
# Skip real graph E2E tests when Groq is not configured
# =========================================================

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
def food_resources():
    temporary_directory = tempfile.TemporaryDirectory()

    database_path = (
        Path(temporary_directory.name)
        / "test_food_e2e.db"
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
            name="Food Test User",
            email="food@test.buyqk.com",
            phone="9999999001",
            password_hash="test-password-hash",
        )

        db.add(user)
        db.flush()

        merchant = Merchant(
            business_name="Test Food Restaurant",
            category="Restaurant",
            phone="9999999002",
            email="food-merchant@test.buyqk.com",
            address="Test Food Address",
        )

        db.add(merchant)
        db.flush()

        category = Category(
            name="Food",
        )

        db.add(category)
        db.flush()

        product = Product(
            name="Margherita Pizza",
            brand="Test Kitchen",
            description="Fresh vegetarian pizza",
            price=249.0,
            stock=20,
            is_available=True,
            merchant_id=merchant.id,
            category_id=category.id,
        )

        db.add(product)
        db.commit()

        db.refresh(user)
        db.refresh(product)

        yield {
            "db": db,
            "user": user,
            "merchant": merchant,
            "category": category,
            "product": product,
        }

    finally:
        db.close()
        engine.dispose()
        temporary_directory.cleanup()


# =========================================================
# Food E2E
# =========================================================


def test_food_product_search(food_resources):
    """
    Validate:

        User
          ↓
        LangGraph
          ↓
        Intent
          ↓
        Entity
          ↓
        Decision
          ↓
        Tool Node
          ↓
        Product Service
          ↓
        SQLite
          ↓
        Response
    """

    from ai_engine.graph.runner import run_chat

    db = food_resources["db"]
    user = food_resources["user"]
    product = food_resources["product"]

    result = run_chat(
        message="Find Margherita Pizza",
        session_id="phase10-food-search-001",
        user_id=user.id,
        db=db,
    )

    # -----------------------------------------------------
    # Intent
    # -----------------------------------------------------

    assert result.get("intent") == "product_search"

    # -----------------------------------------------------
    # Entity
    # -----------------------------------------------------

    entities = result.get(
        "entities",
        {},
    )

    assert isinstance(
        entities,
        dict,
    )

    assert entities.get(
        "product_name"
    )

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

    # -----------------------------------------------------
    # Backend-authoritative product
    # -----------------------------------------------------

    returned_product = products[0]

    assert returned_product["id"] == product.id
    assert returned_product["name"] == "Margherita Pizza"
    assert returned_product["price"] == 249.0

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    response = result.get(
        "response",
        "",
    )

    assert response
    assert "Margherita Pizza" in response