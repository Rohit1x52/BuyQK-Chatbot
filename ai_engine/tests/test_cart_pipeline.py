from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend import models  # noqa: F401
from backend.models.user import User
from backend.models.category import Category
from backend.models.merchant import Merchant
from backend.models.product import Product

from ai_engine.nodes.policy_node import policy_node
from ai_engine.nodes.decision_node import decision_node
from ai_engine.nodes.tool_node import tool_node


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
        name="AI Cart User",
        email="ai-cart@buyqk.com",
        phone="6666666666",
        password_hash="test-password",
    )
    session.add(user)
    session.flush()

    category = Category(name="Groceries")
    merchant = Merchant(
        business_name="AI Cart Merchant",
        category="Grocery",
        phone="5555555555",
        email="ai-cart-merchant@buyqk.test",
        address="Test Address",
    )

    session.add_all([category, merchant])
    session.flush()

    milk = Product(
        name="Amul Gold Milk",
        brand="Amul",
        description="Milk",
        price=65,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    bread = Product(
        name="Brown Bread",
        brand="Harvest",
        description="Bread",
        price=45,
        stock=5,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    session.add_all([milk, bread])
    session.commit()

    try:
        yield {
            "db": session,
            "user": user,
            "milk": milk,
            "bread": bread,
        }
    finally:
        session.close()
        engine.dispose()


def run_cart_pipeline(db, user_id, action, arguments, cart_items=None):
    planner = {
        "action": action,
        "tool_name": action,
        "arguments": arguments,
    }

    state = {
        "user_id": user_id,
        "planner": planner,
        "planner_args": arguments,
        "entities": arguments,
        "cart_items": cart_items or [],
    }

    policy_state = policy_node(state)
    decision_state = decision_node({
        **state,
        **policy_state,
    })

    final_state = {
        **state,
        **policy_state,
        **decision_state,
    }

    if decision_state["decision_route"] == "tool":
        tool_state = tool_node(
            final_state,
            db,
        )
        final_state.update(tool_state)

    return final_state


def test_add_to_cart_pipeline(db):
    data = db

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )

    assert result["decision_route"] == "tool"
    assert result["tool_name"] == "add_to_cart"

    tool_result = result["tool_result"]

    assert tool_result["success"] is True
    assert tool_result["type"] == "cart_add"

    cart = tool_result["cart"]
    assert len(cart["items"]) == 1
    assert cart["items"][0]["product_name"] == "Amul Gold Milk"
    assert cart["items"][0]["quantity"] == 2
    assert cart["summary"]["subtotal"] == 130.0


def test_remove_from_cart_pipeline(db):
    data = db

    first = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )

    assert first["tool_result"]["success"] is True

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "remove_from_cart",
        {
            "product_name": "Amul Gold Milk",
        },
        cart_items=first["tool_result"]["cart"]["items"],
    )

    assert result["decision_route"] == "tool"
    assert result["tool_name"] == "remove_from_cart"
    assert result["tool_result"]["success"] is True
    assert result["tool_result"]["cart"]["items"] == []


def test_update_cart_item_pipeline(db):
    data = db

    first = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "update_cart_item",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 5,
        },
        cart_items=first["tool_result"]["cart"]["items"],
    )

    assert result["tool_result"]["success"] is True
    assert result["tool_result"]["cart"]["items"][0]["quantity"] == 5
    assert result["tool_result"]["cart"]["summary"]["subtotal"] == 325.0


def test_clear_cart_pipeline(db):
    data = db

    run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )
    run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Brown Bread",
            "quantity": 1,
        },
    )

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "clear_cart",
        {},
    )

    assert result["tool_result"]["success"] is True
    assert result["tool_result"]["cart"]["items"] == []
    assert result["cart_items"] == []


def test_show_cart_pipeline(db):
    data = db

    add = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "show_cart",
        {},
        cart_items=add["tool_result"]["cart"]["items"],
    )

    assert result["decision_route"] == "tool"
    assert result["tool_name"] == "show_cart"
    assert result["tool_result"]["success"] is True
    assert len(result["tool_result"]["items"]) == 1


def test_checkout_empty_cart_is_blocked_before_tool(db):
    data = db

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "checkout_cart",
        {},
        cart_items=[],
    )

    assert result["decision_route"] == "response"
    assert result["tool_name"] is None
    assert result["policy_error"]["reason"] == "empty_cart"
    assert "tool_result" not in result


def test_checkout_nonempty_cart_reaches_checkout_tool(db):
    data = db

    add = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "add_to_cart",
        {
            "product_name": "Amul Gold Milk",
            "quantity": 2,
        },
    )

    result = run_cart_pipeline(
        data["db"],
        data["user"].id,
        "checkout_cart",
        {},
        cart_items=add["tool_result"]["cart"]["items"],
    )

    assert result["decision_route"] == "tool"
    assert result["tool_name"] == "checkout_cart"
    assert result["tool_result"]["success"] is True
    assert result["tool_result"]["checkout_ready"] is True
    assert result["tool_result"]["next_step"] == "address_selection"