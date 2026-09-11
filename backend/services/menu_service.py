"""
Menu service for BuyQK food commerce.

This service provides database-backed menu and menu-item discovery.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from backend.models.menu import Menu, MenuItem
from backend.models.restaurant import Restaurant


def _menu_item_to_dict(
    item: MenuItem,
) -> dict[str, Any]:
    """
    Convert a MenuItem ORM object into a serializable dictionary.
    """

    return {
        "id": item.id,
        "menu_id": item.menu_id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price": item.price,
        "is_vegetarian": item.is_vegetarian,
        "is_available": item.is_available,
        "image_url": item.image_url,
        "preparation_time_minutes": item.preparation_time_minutes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _menu_to_dict(
    menu: Menu,
    include_items: bool = False,
) -> dict[str, Any]:
    """
    Convert a Menu ORM object into a serializable dictionary.
    """

    result: dict[str, Any] = {
        "id": menu.id,
        "restaurant_id": menu.restaurant_id,
        "name": menu.name,
        "description": menu.description,
        "is_active": menu.is_active,
        "created_at": menu.created_at,
        "updated_at": menu.updated_at,
    }

    if include_items:
        result["items"] = [
            _menu_item_to_dict(item)
            for item in menu.items
            if item.is_available
        ]

    return result


def get_menu(
    db: Session,
    menu_id: int,
    include_items: bool = True,
) -> dict[str, Any] | None:
    """
    Retrieve a menu by ID.
    """

    query = (
        db.query(Menu)
        .filter(
            Menu.id == menu_id,
        )
    )

    if include_items:
        query = query.options(
            joinedload(Menu.items),
        )

    menu = query.first()

    if menu is None:
        return None

    return _menu_to_dict(
        menu,
        include_items=include_items,
    )


def get_restaurant_menus(
    db: Session,
    restaurant_id: int,
    active_only: bool = True,
    include_items: bool = True,
) -> list[dict[str, Any]]:
    """
    Retrieve menus belonging to a restaurant.
    """

    query = (
        db.query(Menu)
        .filter(
            Menu.restaurant_id == restaurant_id,
        )
    )

    if active_only:
        query = query.filter(
            Menu.is_active.is_(True),
        )

    if include_items:
        query = query.options(
            joinedload(Menu.items),
        )

    menus = (
        query
        .order_by(Menu.id.asc())
        .all()
    )

    return [
        _menu_to_dict(
            menu,
            include_items=include_items,
        )
        for menu in menus
    ]


def get_menu_item(
    db: Session,
    menu_item_id: int,
) -> dict[str, Any] | None:
    """
    Retrieve one menu item by ID.
    """

    item = (
        db.query(MenuItem)
        .filter(
            MenuItem.id == menu_item_id,
        )
        .first()
    )

    if item is None:
        return None

    return _menu_item_to_dict(item)


def search_menu_items(
    db: Session,
    restaurant_id: int | None = None,
    menu_id: int | None = None,
    query: str | None = None,
    category: str | None = None,
    vegetarian_only: bool = False,
    available_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Search food items from the authoritative menu database.
    """

    statement = (
        db.query(MenuItem)
        .join(Menu)
        .join(Restaurant)
    )

    if restaurant_id is not None:
        statement = statement.filter(
            Menu.restaurant_id == restaurant_id,
        )

    if menu_id is not None:
        statement = statement.filter(
            MenuItem.menu_id == menu_id,
        )

    if available_only:
        statement = statement.filter(
            MenuItem.is_available.is_(True),
            Menu.is_active.is_(True),
            Restaurant.is_active.is_(True),
        )

    if query:
        search_value = f"%{query.strip()}%"

        statement = statement.filter(
            MenuItem.name.ilike(search_value)
            | MenuItem.description.ilike(search_value)
        )

    if category:
        category_value = f"%{category.strip()}%"

        statement = statement.filter(
            MenuItem.category.ilike(category_value),
        )

    if vegetarian_only:
        statement = statement.filter(
            MenuItem.is_vegetarian.is_(True),
        )

    items = (
        statement
        .order_by(MenuItem.id.asc())
        .all()
    )

    return [
        _menu_item_to_dict(item)
        for item in items
    ]