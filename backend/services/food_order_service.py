"""Transactional food ordering backed by restaurant menu records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.models.address import Address
from backend.models.food_order import FoodOrder, FoodOrderItem
from backend.models.merchant import Merchant
from backend.models.menu import Menu, MenuItem
from backend.models.restaurant import Restaurant
from backend.services.order_service import get_available_payment_methods


def _food_order_payload(order: FoodOrder) -> dict[str, Any]:
    lines = [
        {
            "menu_item_id": item.menu_item_id,
            "product_name": item.name_snapshot,
            "name": item.name_snapshot,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": item.line_total,
        }
        for item in order.items
    ]
    bill = {
        "order_id": order.id,
        "items": lines,
        "subtotal": order.subtotal,
        "currency": order.currency,
        "payment_method": order.payment_method,
    }
    return {
        "success": True,
        "type": "order_success",
        "order_type": "food",
        "order_id": order.id,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "subtotal": order.subtotal,
        "restaurant_id": order.restaurant_id,
        "purchase_summary": {
            "order_type": "food",
            "items": lines,
            "subtotal": order.subtotal,
            "currency": order.currency,
            "payment_method": order.payment_method,
        },
        "bill": bill,
    }


def _resolve_menu_item(
    db: Session,
    requested: dict[str, Any],
    restaurant_name: str | None,
) -> MenuItem:
    item_id = requested.get("menu_item_id")
    statement = (
        db.query(MenuItem)
        .join(Menu, MenuItem.menu_id == Menu.id)
        .join(Restaurant, Menu.restaurant_id == Restaurant.id)
        .join(Merchant, Merchant.id == Restaurant.merchant_id)
        .options(joinedload(MenuItem.menu).joinedload(Menu.restaurant))
        .filter(
            MenuItem.is_available.is_(True),
            Menu.is_active.is_(True),
            Restaurant.is_active.is_(True),
            Restaurant.delivery_available.is_(True),
        )
    )
    if item_id is not None:
        statement = statement.filter(MenuItem.id == int(item_id))
    else:
        name = str(requested.get("product_name") or requested.get("name") or "").strip()
        if not name:
            raise ValueError("A menu item name or ID is required.")
        statement = statement.filter(func.lower(MenuItem.name) == name.casefold())

    if restaurant_name and restaurant_name.strip():
        statement = statement.filter(
            func.lower(Merchant.business_name) == restaurant_name.strip().casefold()
        )

    matches = statement.all()
    if not matches:
        raise ValueError("The requested food item is not available from an active restaurant.")
    if len(matches) > 1:
        raise ValueError("More than one restaurant has this menu item; specify the restaurant.")
    return matches[0]


def create_food_order(
    *,
    db: Session,
    user_id: int,
    address_id: int,
    checkout_id: str,
    payment_method: str,
    items: list[dict[str, Any]],
    restaurant_name: str | None = None,
) -> dict[str, Any]:
    """Create an idempotent food order from available menu items."""
    if not checkout_id or not checkout_id.strip():
        raise ValueError("checkout_id is required.")

    existing = (
        db.query(FoodOrder)
        .options(joinedload(FoodOrder.items))
        .filter(
            FoodOrder.user_id == int(user_id),
            FoodOrder.checkout_id == checkout_id.strip(),
        )
        .first()
    )
    if existing is not None:
        return _food_order_payload(existing)

    address = (
        db.query(Address)
        .filter(
            Address.id == int(address_id),
            Address.user_id == int(user_id),
        )
        .first()
    )
    if address is None:
        raise ValueError("The selected delivery address is invalid.")

    normalized_payment = str(payment_method or "").strip().casefold()
    available_methods = {
        str(method.get("id", "")).casefold()
        for method in get_available_payment_methods()
        if isinstance(method, dict)
    }
    if normalized_payment not in available_methods:
        raise ValueError("The selected payment method is not available.")

    if not isinstance(items, list) or not items:
        raise ValueError("At least one food item is required.")

    resolved: list[tuple[MenuItem, int]] = []
    restaurant_ids: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Food order items must be structured records.")
        try:
            quantity = int(item.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Food item quantities must be positive integers.") from exc
        if quantity <= 0:
            raise ValueError("Food item quantities must be positive integers.")
        menu_item = _resolve_menu_item(db, item, restaurant_name)
        resolved.append((menu_item, quantity))
        restaurant_ids.add(menu_item.menu.restaurant_id)

    if len(restaurant_ids) != 1:
        raise ValueError("A food order can contain items from only one restaurant.")

    subtotal = sum(float(menu_item.price) * quantity for menu_item, quantity in resolved)
    order = FoodOrder(
        user_id=int(user_id),
        restaurant_id=restaurant_ids.pop(),
        address_id=int(address_id),
        checkout_id=checkout_id.strip(),
        payment_method=normalized_payment,
        subtotal=subtotal,
    )
    order.items = [
        FoodOrderItem(
            menu_item_id=menu_item.id,
            name_snapshot=menu_item.name,
            quantity=quantity,
            unit_price=float(menu_item.price),
            line_total=float(menu_item.price) * quantity,
        )
        for menu_item, quantity in resolved
    ]

    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        existing = (
            db.query(FoodOrder)
            .options(joinedload(FoodOrder.items))
            .filter(
                FoodOrder.user_id == int(user_id),
                FoodOrder.checkout_id == checkout_id.strip(),
            )
            .first()
        )
        if existing is not None:
            return _food_order_payload(existing)
        raise

    return _food_order_payload(order)