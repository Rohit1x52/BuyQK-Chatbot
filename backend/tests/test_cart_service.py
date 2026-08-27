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
from backend.services.cart_service import (
    get_cart,
    add_item,
    update_quantity,
    update_item_quantity,
    remove_item,
    remove_product,
    clear_cart,
    calculate_cart,
    CartServiceError,
    ProductNotFoundError,
    ProductUnavailableError,
    InsufficientStockError,
    CartItemNotFoundError,
    InvalidQuantityError,
)


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
        name="Cart Test User",
        email="cart-test@buyqk.com",
        phone="9999999999",
        password_hash="test-password",
    )
    session.add(user)
    session.flush()

    category = Category(name="Groceries")
    session.add(category)
    session.flush()

    merchant = Merchant(
        business_name="Cart Test Merchant",
        category="Grocery",
        phone="8888888888",
        email="merchant-cart@buyqk.test",
        address="Test Address",
    )
    session.add(merchant)
    session.flush()

    milk = Product(
        name="Amul Gold Milk",
        brand="Amul",
        description="Full cream milk",
        price=65,
        stock=10,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    bread = Product(
        name="Brown Bread",
        brand="Harvest",
        description="Fresh brown bread",
        price=45,
        stock=5,
        is_available=True,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    unavailable = Product(
        name="Unavailable Milk",
        brand="TestBrand",
        description="Unavailable",
        price=50,
        stock=0,
        is_available=False,
        category_id=category.id,
        merchant_id=merchant.id,
    )

    session.add_all([milk, bread, unavailable])
    session.commit()

    try:
        yield {
            "db": session,
            "user": user,
            "milk": milk,
            "bread": bread,
            "unavailable": unavailable,
        }
    finally:
        session.close()
        engine.dispose()


def test_get_cart_creates_empty_active_cart(db):
    data = db
    cart = get_cart(data["db"], data["user"].id)

    assert cart["cart_id"] is not None
    assert cart["status"] == "active"
    assert cart["items"] == []
    assert cart["summary"]["item_count"] == 0
    assert cart["summary"]["total_quantity"] == 0
    assert cart["summary"]["subtotal"] == 0.0
    assert cart["summary"]["total"] == 0.0


def test_add_item_creates_cart_item_and_calculates_totals(db):
    data = db

    cart = add_item(
        data["db"],
        data["user"].id,
        data["milk"].id,
        2,
    )

    assert len(cart["items"]) == 1
    assert cart["items"][0]["product_id"] == data["milk"].id
    assert cart["items"][0]["quantity"] == 2
    assert cart["items"][0]["unit_price"] == 65.0
    assert cart["items"][0]["line_total"] == 130.0

    assert cart["summary"]["item_count"] == 1
    assert cart["summary"]["total_quantity"] == 2
    assert cart["summary"]["subtotal"] == 130.0
    assert cart["summary"]["total"] == 130.0


def test_add_same_product_increases_quantity_instead_of_duplicate_row(db):
    data = db

    first = add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    second = add_item(
        data["db"], data["user"].id, data["milk"].id, 3
    )

    assert len(second["items"]) == 1
    assert second["items"][0]["quantity"] == 5
    assert second["summary"]["total_quantity"] == 5
    assert second["summary"]["subtotal"] == 325.0


@pytest.mark.parametrize("quantity", [0, -1, True, False, "abc", None])
def test_add_rejects_invalid_quantity(db, quantity):
    data = db

    with pytest.raises(InvalidQuantityError):
        add_item(
            data["db"],
            data["user"].id,
            data["milk"].id,
            quantity,
        )


def test_add_rejects_missing_product(db):
    data = db

    with pytest.raises(ProductNotFoundError):
        add_item(
            data["db"],
            data["user"].id,
            999999,
            1,
        )


def test_add_rejects_unavailable_product(db):
    data = db

    with pytest.raises(ProductUnavailableError):
        add_item(
            data["db"],
            data["user"].id,
            data["unavailable"].id,
            1,
        )


def test_add_rejects_insufficient_stock(db):
    data = db

    with pytest.raises(InsufficientStockError):
        add_item(
            data["db"],
            data["user"].id,
            data["milk"].id,
            11,
        )


def test_add_existing_item_rejects_resulting_quantity_above_stock(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 8
    )

    with pytest.raises(InsufficientStockError):
        add_item(
            data["db"], data["user"].id, data["milk"].id, 3
        )


def test_update_quantity_by_cart_item_id(db):
    data = db

    cart = add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    item_id = cart["items"][0]["id"]

    updated = update_quantity(
        data["db"],
        data["user"].id,
        item_id,
        5,
    )

    assert updated["items"][0]["quantity"] == 5
    assert updated["summary"]["total_quantity"] == 5
    assert updated["summary"]["subtotal"] == 325.0


def test_update_quantity_by_product_id(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )

    updated = update_item_quantity(
        data["db"],
        data["user"].id,
        data["milk"].id,
        4,
    )

    assert updated["items"][0]["quantity"] == 4
    assert updated["summary"]["subtotal"] == 260.0


def test_update_missing_cart_item_rejected(db):
    data = db

    with pytest.raises(CartItemNotFoundError):
        update_quantity(
            data["db"],
            data["user"].id,
            999999,
            2,
        )


def test_update_missing_product_item_rejected(db):
    data = db

    with pytest.raises(CartItemNotFoundError):
        update_item_quantity(
            data["db"],
            data["user"].id,
            999999,
            2,
        )


def test_update_rejects_quantity_above_stock(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )

    with pytest.raises(InsufficientStockError):
        update_item_quantity(
            data["db"],
            data["user"].id,
            data["milk"].id,
            11,
        )


def test_remove_item_by_cart_item_id(db):
    data = db

    cart = add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    item_id = cart["items"][0]["id"]

    updated = remove_item(
        data["db"],
        data["user"].id,
        item_id,
    )

    assert updated["items"] == []
    assert updated["summary"]["item_count"] == 0
    assert updated["summary"]["total_quantity"] == 0
    assert updated["summary"]["total"] == 0.0


def test_remove_product_by_product_id(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    add_item(
        data["db"], data["user"].id, data["bread"].id, 1
    )

    updated = remove_product(
        data["db"],
        data["user"].id,
        data["milk"].id,
    )

    assert len(updated["items"]) == 1
    assert updated["items"][0]["product_id"] == data["bread"].id


def test_remove_missing_item_rejected(db):
    data = db

    with pytest.raises(CartItemNotFoundError):
        remove_item(
            data["db"],
            data["user"].id,
            999999,
        )


def test_remove_missing_product_from_cart_rejected(db):
    data = db

    with pytest.raises(CartItemNotFoundError):
        remove_product(
            data["db"],
            data["user"].id,
            data["milk"].id,
        )


def test_clear_cart_removes_all_items(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    add_item(
        data["db"], data["user"].id, data["bread"].id, 1
    )

    cleared = clear_cart(
        data["db"],
        data["user"].id,
    )

    assert cleared["items"] == []
    assert cleared["summary"]["item_count"] == 0
    assert cleared["summary"]["total_quantity"] == 0
    assert cleared["summary"]["total"] == 0.0


def test_clear_empty_cart_is_safe(db):
    data = db

    cleared = clear_cart(
        data["db"],
        data["user"].id,
    )

    assert cleared["items"] == []
    assert cleared["summary"]["total"] == 0.0


def test_calculate_cart_returns_authoritative_summary(db):
    data = db

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )
    add_item(
        data["db"], data["user"].id, data["bread"].id, 1
    )

    summary = calculate_cart(
        data["db"],
        data["user"].id,
    )

    assert summary["item_count"] == 2
    assert summary["total_quantity"] == 3
    assert summary["subtotal"] == 175.0
    assert summary["total"] == 175.0
    assert summary["currency"] == "INR"


def test_cart_is_user_scoped(db):
    data = db

    other_user = User(
        name="Other User",
        email="other-cart@buyqk.com",
        phone="7777777777",
        password_hash="test-password",
    )
    data["db"].add(other_user)
    data["db"].commit()

    add_item(
        data["db"], data["user"].id, data["milk"].id, 2
    )

    other_cart = get_cart(
        data["db"],
        other_user.id,
    )

    assert other_cart["items"] == []


def test_product_price_is_authoritative_not_supplied_by_ai(db):
    data = db

    cart = add_item(
        data["db"],
        data["user"].id,
        data["milk"].id,
        2,
    )

    # There is intentionally no price argument in add_item().
    # The returned amount must come from Product.price.
    assert cart["items"][0]["unit_price"] == 65.0
    assert cart["summary"]["subtotal"] == 130.0