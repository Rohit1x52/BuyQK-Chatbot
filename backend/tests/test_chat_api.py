# Purpose:
# End-to-end API test for the BuyQK MVP.
#
# This test intentionally uses the REAL LLM.
#
# Flow:
#
# TestClient
#     ↓
# POST /chat
#     ↓
# FastAPI
#     ↓
# run_chat()
#     ↓
# LangGraph
#     ↓
# Groq / Llama
#     ↓
# Backend Tool
#     ↓
# SQLite
#     ↓
# Groq / Llama
#     ↓
# API Response
#
# Run from project root:
#
#     python -m backend.tests.test_chat_api
#
# IMPORTANT:
# This test consumes Groq API calls because it uses the
# real LLM-powered graph.


from __future__ import annotations

import os
import sys
import tempfile


# =========================================================
# Project Root
# =========================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../..",
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )


# =========================================================
# SQLAlchemy
# =========================================================

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker


# =========================================================
# FastAPI
# =========================================================

from fastapi.testclient import TestClient


# =========================================================
# Backend
# =========================================================

from backend.main import app

from backend.database.base import Base

from backend.database.dependencies import get_db

from backend.models import (
    User,
    Merchant,
    Category,
    Product,
)


# =========================================================
# Test Database
# =========================================================

def create_test_database():
    """
    Create a temporary isolated SQLite database.
    """

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".db",
        delete=False,
    )

    temp_file.close()

    database_url = (
        f"sqlite:///{temp_file.name}"
    )

    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        bind=engine
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    return (
        engine,
        SessionLocal,
        temp_file.name,
    )


# =========================================================
# Seed Test Data
# =========================================================

def seed_test_data(
    SessionLocal,
):
    """
    Insert the minimum records required by the
    LLM-backed API tests.
    """

    db = SessionLocal()

    try:

        # -------------------------------------------------
        # User
        # -------------------------------------------------

        user = User(
            name="API Test User",
            email="api-test@buyqk.com",
        )

        db.add(user)

        # -------------------------------------------------
        # Merchant
        # -------------------------------------------------

        merchant = Merchant(
            name="API Test Merchant",
        )

        db.add(merchant)

        # -------------------------------------------------
        # Category
        # -------------------------------------------------

        category = Category(
            name="Dairy",
        )

        db.add(category)

        db.flush()

        # -------------------------------------------------
        # Product
        # -------------------------------------------------

        product = Product(
            name="Amul Milk",
            brand="Amul",
            price=65.0,
            stock=20,
            merchant_id=merchant.id,
            category_id=category.id,
        )

        db.add(product)

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


# =========================================================
# API Dependency Override
# =========================================================

def create_db_override(
    SessionLocal,
):
    """
    Create the FastAPI database dependency override.
    """

    def override_get_db():

        db = SessionLocal()

        try:

            yield db

        finally:

            db.close()

    return override_get_db


# =========================================================
# Response Helpers
# =========================================================

def assert_success_response(
    response,
):
    """
    Verify that the chat endpoint returned a successful
    HTTP response with the expected response structure.
    """

    assert response.status_code == 200, (
        f"Expected HTTP 200, got "
        f"{response.status_code}\n"
        f"Response: {response.text}"
    )

    data = response.json()

    assert isinstance(
        data,
        dict,
    )

    assert "message" in data

    assert data["message"]

    return data


# =========================================================
# Main Test
# =========================================================

def main():

    print()
    print("=" * 60)
    print(
        "BUYQK MVP FULL-STACK AI CHAT API TEST"
    )
    print("=" * 60)

    print()
    print(
        "⚠ This test uses the REAL Groq LLM."
    )

    print(
        "⚠ LLM API calls will be generated."
    )

    engine = None
    database_file = None

    passed = 0
    total = 5

    try:

        # =================================================
        # Temporary Database
        # =================================================

        (
            engine,
            SessionLocal,
            database_file,
        ) = create_test_database()

        print()
        print(
            "✓ Temporary SQLite database created"
        )

        # =================================================
        # Seed Data
        # =================================================

        user = seed_test_data(
            SessionLocal
        )

        print(
            "✓ Test data seeded"
        )

        # =================================================
        # Override DB Dependency
        # =================================================

        app.dependency_overrides[
            get_db
        ] = create_db_override(
            SessionLocal
        )

        print(
            "✓ FastAPI database dependency overridden"
        )

        # =================================================
        # Test Client
        # =================================================

        client = TestClient(
            app
        )

        print(
            "✓ FastAPI test client created"
        )

        # =================================================
        # TEST 1 — Health
        # =================================================

        print()
        print("=" * 60)
        print(
            "TEST 1: Health Endpoint"
        )
        print("=" * 60)

        response = client.get(
            "/health"
        )

        assert response.status_code == 200

        print(
            "✓ GET /health"
        )

        print(
            f"✓ Status: "
            f"{response.status_code}"
        )

        passed += 1

        # =================================================
        # TEST 2 — LLM General Conversation
        # =================================================

        print()
        print("=" * 60)
        print(
            "TEST 2: LLM General Conversation"
        )
        print("=" * 60)

        response = client.post(
            "/chat",
            json={
                "message": "Hello",
                "session_id": (
                    "fullstack-test-general"
                ),
                "user_id": user.id,
            },
        )

        data = assert_success_response(
            response
        )

        print(
            "✓ POST /chat"
        )

        print(
            f"✓ Intent returned: "
            f"{data.get('intent')}"
        )

        print(
            f"✓ LLM Response: "
            f"{data['message']}"
        )

        passed += 1

        # =================================================
        # TEST 3 — LLM Product Search
        # =================================================

        print()
        print("=" * 60)
        print(
            "TEST 3: LLM Product Search"
        )
        print("=" * 60)

        response = client.post(
            "/chat",
            json={
                "message": "Find Amul milk",
                "session_id": (
                    "fullstack-test-product"
                ),
                "user_id": user.id,
            },
        )

        data = assert_success_response(
            response
        )

        print(
            "✓ POST /chat"
        )

        print(
            f"✓ LLM Intent: "
            f"{data.get('intent')}"
        )

        # -------------------------------------------------
        # Verify intent
        # -------------------------------------------------

        assert data.get(
            "intent"
        ) == "product_search", (
            f"Expected product_search, "
            f"got {data.get('intent')}"
        )

        print(
            "✓ Intent = product_search"
        )

        # -------------------------------------------------
        # Verify product result
        # -------------------------------------------------

        metadata = data.get(
            "metadata",
            {},
        )

        products = metadata.get(
            "products",
            [],
        )

        assert products, (
            "Expected product results "
            "from backend."
        )

        product_names = [
            product.get("name")
            for product in products
        ]

        assert "Amul Milk" in product_names, (
            f"Amul Milk not found. "
            f"Products: {products}"
        )

        print(
            "✓ Backend returned Amul Milk"
        )

        print(
            f"✓ LLM Response: "
            f"{data['message']}"
        )

        passed += 1

        # =================================================
        # TEST 4 — LLM Entity Extraction
        # =================================================

        print()
        print("=" * 60)
        print(
            "TEST 4: LLM Entity + Missing Information"
        )
        print("=" * 60)

        response = client.post(
            "/chat",
            json={
                "message": "I want Amul milk",
                "session_id": (
                    "fullstack-test-missing"
                ),
                "user_id": user.id,
            },
        )

        data = assert_success_response(
            response
        )

        print(
            "✓ POST /chat"
        )

        print(
            f"✓ LLM Intent: "
            f"{data.get('intent')}"
        )

        assert data.get(
            "intent"
        ) == "order_create", (
            f"Expected order_create, "
            f"got {data.get('intent')}"
        )

        print(
            "✓ Intent = order_create"
        )

        metadata = data.get(
            "metadata",
            {},
        )

        missing_fields = metadata.get(
            "missing_fields",
            [],
        )

        assert "quantity" in missing_fields, (
            f"Expected quantity to be missing. "
            f"Got: {missing_fields}"
        )

        print(
            "✓ Entity extraction detected "
            "missing quantity"
        )

        print(
            f"✓ LLM Response: "
            f"{data['message']}"
        )

        passed += 1

        # =================================================
        # TEST 5 — LLM + Backend Full Path
        # =================================================

        print()
        print("=" * 60)
        print(
            "TEST 5: Complete LLM → Backend Flow"
        )
        print("=" * 60)

        response = client.post(
            "/chat",
            json={
                "message": (
                    "Please find Amul milk "
                    "for me"
                ),
                "session_id": (
                    "fullstack-test-complete"
                ),
                "user_id": user.id,
            },
        )

        data = assert_success_response(
            response
        )

        # -------------------------------------------------
        # Verify Intent
        # -------------------------------------------------

        assert data.get(
            "intent"
        ) == "product_search"

        print(
            "✓ Intent LLM"
        )

        # -------------------------------------------------
        # Verify Backend Result
        # -------------------------------------------------

        metadata = data.get(
            "metadata",
            {},
        )

        products = metadata.get(
            "products",
            [],
        )

        assert len(products) >= 1

        print(
            "✓ Entity LLM"
        )

        print(
            "✓ Decision Node"
        )

        print(
            "✓ Tool Node"
        )

        print(
            "✓ Product Service"
        )

        print(
            "✓ SQLite"
        )

        # -------------------------------------------------
        # Verify Response LLM
        # -------------------------------------------------

        assert data["message"]

        print(
            "✓ Response LLM"
        )

        print()
        print(
            f"✓ Final Response: "
            f"{data['message']}"
        )

        passed += 1

        # =================================================
        # Final Result
        # =================================================

        print()
        print("=" * 60)
        print(
            "✅ ALL LLM-BACKED CHAT API TESTS PASSED"
        )
        print("=" * 60)

        print()
        print(
            f"Passed: {passed}/{total}"
        )

        print()
        print(
            "Full-stack AI status:"
        )

        print(
            "  ✓ FastAPI"
        )

        print(
            "  ✓ Pydantic validation"
        )

        print(
            "  ✓ Groq / Llama"
        )

        print(
            "  ✓ Intent LLM"
        )

        print(
            "  ✓ Entity LLM"
        )

        print(
            "  ✓ LangGraph"
        )

        print(
            "  ✓ Decision Node"
        )

        print(
            "  ✓ Tool Node"
        )

        print(
            "  ✓ Product Service"
        )

        print(
            "  ✓ SQLite"
        )

        print(
            "  ✓ Response LLM"
        )

    except Exception as exc:

        print()
        print("=" * 60)
        print(
            "❌ LLM-BACKED CHAT API TEST FAILED"
        )
        print("=" * 60)

        print()
        print(
            f"Error:\n{exc}"
        )

        raise

    finally:

        # -------------------------------------------------
        # Remove FastAPI override
        # -------------------------------------------------

        app.dependency_overrides.clear()

        # -------------------------------------------------
        # Dispose SQLAlchemy engine
        # -------------------------------------------------

        if engine is not None:

            engine.dispose()

        # -------------------------------------------------
        # Delete temporary DB
        # -------------------------------------------------

        if (
            database_file
            and os.path.exists(
                database_file
            )
        ):

            os.remove(
                database_file
            )

            print()
            print(
                "✓ Temporary database removed"
            )


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":

    main()