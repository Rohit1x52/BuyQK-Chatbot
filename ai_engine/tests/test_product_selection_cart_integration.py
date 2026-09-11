"""
BuyQK AI - Phase 6C Product Selection -> Cart Integration Tests

Flow covered:
    Product search
        -> backend-derived candidate set
        -> conversational candidate selection
        -> backend product_id resolution
        -> Cart planner
        -> Policy
        -> Decision
        -> Cart Tool
        -> CartService
        -> SQLite

These tests use synthetic database/catalog data only. They do not call the
real LLM and do not invent product IDs.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend import models  # noqa: F401
from backend.models.category import Category
from backend.models.merchant import Merchant
from backend.models.product import Product
from backend.models.user import User

from ai_engine.nodes import entity_node as entity_node_module
from ai_engine.nodes import tool_node as tool_node_module
from ai_engine.nodes.decision_node import decision_node
from ai_engine.nodes.planner_node import _deterministic_plan_fallback
from ai_engine.nodes.policy_node import policy_node


# =========================================================
# Test Database
# =========================================================

@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    session = SessionLocal()

    user = User(
        name="Phase 6C User",
        email="phase6c@buyqk.test",
        phone="6666666666",
        password_hash="test-password",
    )

    category = Category(name="Phase 6C Category")

    merchant = Merchant(
        business_name="Phase 6C Merchant",
        category="Grocery",
        phone="5555555555",
        email="phase6c-merchant@buyqk.test",
        address="Synthetic Test Address",
    )

    session.add_all([user, category, merchant])
    session.flush()

    first_product = Product(
        name="Synthetic Product A",
        brand="Test Brand",
        description="Synthetic candidate A",
        price=100,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    second_product = Product(
        name="Synthetic Product B",
        brand="Test Brand",
        description="Synthetic candidate B",
        price=120,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    third_product = Product(
        name="Synthetic Product C",
        brand="Test Brand",
        description="Synthetic candidate C",
        price=140,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    session.add_all(
        [
            first_product,
            second_product,
            third_product,
        ]
    )
    session.commit()

    try:
        yield {
            "db": session,
            "user": user,
            "products": [
                first_product,
                second_product,
                third_product,
            ],
        }
    finally:
        session.close()
        engine.dispose()


# =========================================================
# Helpers
# =========================================================

def search_state() -> dict[str, Any]:
    return {
        "message": "Find synthetic product",
        "intent": "product_search",
        "tool_name": "search_products",
        "entities": {
            "product_name": "synthetic product",
        },
        "missing_fields": [],
        "next_missing": None,
        "product_search_results": [],
        "selected_product": None,
    }


def test_product_search_then_select_then_add_to_cart(
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = db
    products = data["products"]

    # -----------------------------------------------------
    # 1. Search returns multiple backend-derived candidates.
    # -----------------------------------------------------

    backend_candidates = [
        {
            "id": products[0].id,
            "name": products[0].name,
            "price": float(products[0].price),
            "stock": products[0].stock,
            "is_available": products[0].is_available,
        },
        {
            "id": products[1].id,
            "name": products[1].name,
            "price": float(products[1].price),
            "stock": products[1].stock,
            "is_available": products[1].is_available,
        },
        {
            "id": products[2].id,
            "name": products[2].name,
            "price": float(products[2].price),
            "stock": products[2].stock,
            "is_available": products[2].is_available,
        },
    ]

    def fake_search_products(
        *,
        db: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        assert query == "synthetic product"
        return backend_candidates

    monkeypatch.setattr(
        tool_node_module,
        "search_products",
        fake_search_products,
    )

    search_result = tool_node_module.tool_node(
        search_state(),
        db=data["db"],
    )

    search_tool_result = search_result["tool_result"]

    assert search_tool_result.success is True
    assert search_tool_result.tool == "search_products"

    candidates = search_result["product_search_results"]

    assert len(candidates) == 3
    assert candidates[1]["id"] == products[1].id
    assert search_result["selected_product"] is None

    # -----------------------------------------------------
    # 2. User selects "second one".
    # -----------------------------------------------------

    # Avoid the real LLM. This turn is testing deterministic candidate
    # selection, not semantic entity extraction.
    monkeypatch.setattr(
        entity_node_module,
        "extract_entities",
        lambda *args, **kwargs: entity_node_module.LLMEntityOutput(),
    )

    selection_state = {
        "message": "second one",
        "intent": "cart",
        "entities": {
            "cart_action": "add_item",
            "quantity": 2,
        },
        "product_search_results": candidates,
        "conversation_history": [],
        "cart_items": [],
    }

    selected_state = entity_node_module.entity_node(
        selection_state,
    )

    entities = selected_state["entities"]

    # The ID and name must come from the second backend candidate.
    assert entities["product_id"] == products[1].id
    assert entities["product_name"] == products[1].name
    assert entities["quantity"] == 2

    # -----------------------------------------------------
    # 3. Planner uses the resolved backend product ID.
    # -----------------------------------------------------

    plan = _deterministic_plan_fallback(
        {
            **selected_state,
            "intent": "cart",
        }
    )

    assert plan["action"] == "add_to_cart"
    assert plan["arguments"]["product_id"] == products[1].id
    assert plan["arguments"]["product_name"] == products[1].name
    assert plan["arguments"]["quantity"] == 2

    # -----------------------------------------------------
    # 4. Policy + decision.
    # -----------------------------------------------------

    policy_state = policy_node(
        {
            **selected_state,
            "planner": plan,
            "planner_args": plan["arguments"],
        }
    )

    assert policy_state["policy_result"]["allowed"] is True
    assert policy_state["policy_result"]["tool"] == "add_to_cart"

    decision_state = decision_node(
        {
            **selected_state,
            **policy_state,
            "planner": plan,
            "planner_args": plan["arguments"],
        }
    )

    assert decision_state["decision_route"] == "tool"
    assert decision_state["tool_name"] == "add_to_cart"

    # -----------------------------------------------------
    # 5. Cart Tool -> CartService -> SQLite.
    # -----------------------------------------------------

    final_state = {
        **selected_state,
        **policy_state,
        **decision_state,
        "planner": plan,
        "planner_args": plan["arguments"],
        "user_id": data["user"].id,
        "entities": entities,
    }

    cart_result = tool_node_module.tool_node(
        final_state,
        db=data["db"],
    )

    tool_result = cart_result["tool_result"]

    assert tool_result.success is True
    assert tool_result.tool == "add_to_cart"
    assert tool_result.data["type"] == "cart_add"

    cart = tool_result.data["cart"]

    assert len(cart["items"]) == 1
    assert cart["items"][0]["product_id"] == products[1].id
    assert cart["items"][0]["product_name"] == products[1].name
    assert cart["items"][0]["quantity"] == 2


def test_new_search_clears_stale_candidates_on_backend_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = search_state()
    state["product_search_results"] = [
        {
            "id": 901,
            "name": "Stale Candidate",
        }
    ]
    state["selected_product"] = {
        "id": 901,
        "name": "Stale Candidate",
    }

    def failing_search_products(
        *,
        db: Any,
        query: str,
    ) -> list[dict[str, Any]]:
        raise RuntimeError("synthetic search failure")

    monkeypatch.setattr(
        tool_node_module,
        "search_products",
        failing_search_products,
    )

    result = tool_node_module.tool_node(
        state,
        db=object(),
    )

    assert result["product_search_results"] == []
    assert result["selected_product"] is None


def test_invalid_quantity_is_rejected_before_cart_mutation() -> None:
    state = {
        "intent": "cart",
        "entities": {
            "cart_action": "add_item",
            "product_id": 1001,
            "product_name": "Synthetic Product",
            "quantity": 0,
        },
        "cart_items": [],
        "missing_fields": [],
    }

    plan = _deterministic_plan_fallback(state)

    assert plan["action"] == "ask_clarification"
    assert "quantity" in plan["missing_fields"]

    policy_state = policy_node(
        {
            **state,
            "planner": plan,
            "planner_args": plan["arguments"],
        }
    )

    assert policy_state["policy_result"]["allowed"] is False


def test_backend_cart_failure_does_not_report_success(
    db,
) -> None:
    data = db
    product = data["products"][0]

    # Stock is 10 in the fixture; requesting more than that must be rejected
    # by the backend/cart service rather than by the AI layer.
    plan = {
        "action": "add_to_cart",
        "tool_name": "add_to_cart",
        "arguments": {
            "product_id": product.id,
            "product_name": product.name,
            "quantity": product.stock + 1,
        },
        "missing_fields": [],
        "confidence": 0.0,
        "reason": "synthetic backend failure case",
    }

    result = tool_node_module.tool_node(
        {
            "user_id": data["user"].id,
            "intent": "cart",
            "tool_name": "add_to_cart",
            "planner": plan,
            "planner_args": plan["arguments"],
            "entities": plan["arguments"],
            "cart_items": [],
        },
        db=data["db"],
    )

    tool_result = result["tool_result"]

    assert tool_result.success is False
    assert tool_result.tool == "add_to_cart"
    assert tool_result.error is not None


def test_invalid_candidate_selection_does_not_invent_product_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        {
            "id": 101,
            "name": "Synthetic Candidate A",
        },
        {
            "id": 102,
            "name": "Synthetic Candidate B",
        },
    ]

    monkeypatch.setattr(
        entity_node_module,
        "extract_entities",
        lambda *args, **kwargs: entity_node_module.LLMEntityOutput(),
    )

    result = entity_node_module.entity_node(
        {
            "message": "option 9",
            "intent": "cart",
            "entities": {
                "cart_action": "add_item",
                "quantity": 1,
            },
            "product_search_results": candidates,
            "conversation_history": [],
        }
    )

    assert "product_id" not in result["entities"]
    assert result["entities"]["quantity"] == 1
    assert result["entities"]["cart_action"] == "add_item"


def test_single_candidate_selection_remains_backend_derived() -> None:
    candidates = [
        {
            "id": 777,
            "name": "Synthetic Single Candidate",
        }
    ]

    result = entity_node_module.entity_node(
        {
            "message": "option 1",
            "intent": "cart",
            "entities": {
                "cart_action": "add_item",
                "quantity": 1,
            },
            "product_search_results": candidates,
            "conversation_history": [],
        }
    )

    assert result["entities"]["product_id"] == 777
    assert (
        result["entities"]["product_name"]
        == "Synthetic Single Candidate"
    )
