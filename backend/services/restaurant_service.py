"""
Restaurant service for BuyQK food commerce.

This service provides database-backed restaurant discovery and lookup.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.models.merchant import Merchant
from backend.models.restaurant import Restaurant


def _restaurant_to_dict(
    restaurant: Restaurant,
) -> dict[str, Any]:
    """
    Convert a Restaurant ORM object into a serializable dictionary.
    """

    merchant = restaurant.merchant

    return {
        "id": restaurant.id,
        "merchant_id": restaurant.merchant_id,
        "name": merchant.business_name if merchant else None,
        "business_name": merchant.business_name if merchant else None,
        "category": merchant.category if merchant else None,
        "phone": merchant.phone if merchant else None,
        "email": merchant.email if merchant else None,
        "address": merchant.address if merchant else None,
        "verification_status": (
            merchant.verification_status
            if merchant
            else None
        ),
        "cuisine_type": restaurant.cuisine_type,
        "description": restaurant.description,
        "is_active": restaurant.is_active,
        "delivery_available": restaurant.delivery_available,
        "created_at": restaurant.created_at,
        "updated_at": restaurant.updated_at,
    }


def get_restaurant(
    db: Session,
    restaurant_id: int,
) -> dict[str, Any] | None:
    """
    Retrieve one restaurant by restaurant ID.
    """

    restaurant = (
        db.query(Restaurant)
        .options(joinedload(Restaurant.merchant))
        .filter(
            Restaurant.id == restaurant_id,
        )
        .first()
    )

    if restaurant is None:
        return None

    return _restaurant_to_dict(restaurant)


def get_restaurant_by_merchant(
    db: Session,
    merchant_id: int,
) -> dict[str, Any] | None:
    """
    Retrieve a restaurant using its existing merchant ID.
    """

    restaurant = (
        db.query(Restaurant)
        .options(joinedload(Restaurant.merchant))
        .filter(
            Restaurant.merchant_id == merchant_id,
        )
        .first()
    )

    if restaurant is None:
        return None

    return _restaurant_to_dict(restaurant)


def search_restaurants(
    db: Session,
    query: str | None = None,
    cuisine_type: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Search restaurants using authoritative database data.

    Search can match:
        - restaurant/merchant name
        - cuisine type
        - restaurant description
    """

    statement = (
        db.query(Restaurant)
        .join(Merchant)
        .options(joinedload(Restaurant.merchant))
    )

    if active_only:
        statement = statement.filter(
            Restaurant.is_active.is_(True),
        )

    if query:
        search_value = f"%{query.strip()}%"

        statement = statement.filter(
            or_(
                Merchant.business_name.ilike(search_value),
                Restaurant.cuisine_type.ilike(search_value),
                Restaurant.description.ilike(search_value),
            )
        )

    if cuisine_type:
        cuisine_value = f"%{cuisine_type.strip()}%"

        statement = statement.filter(
            Restaurant.cuisine_type.ilike(cuisine_value),
        )

    restaurants = (
        statement
        .order_by(Restaurant.id.asc())
        .all()
    )

    return [
        _restaurant_to_dict(restaurant)
        for restaurant in restaurants
    ]