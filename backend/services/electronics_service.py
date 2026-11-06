"""Database-backed electronics search, comparison, and variant lookup."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.models.merchant import Merchant
from backend.models.category import Category
from backend.models.product import Product


ELECTRONICS_CATEGORY = "electronics"
ELECTRONICS_CATEGORIES = (
    "mobile",
    "laptop",
    "tv",
    "electronics accessories",
    "smartphones",
    "headphones",
    "tablets",
    "cameras",
)


def _electronics_scope():
    return or_(
        func.lower(Merchant.category) == ELECTRONICS_CATEGORY,
        func.lower(Category.name).in_(ELECTRONICS_CATEGORIES),
    )


def _product_data(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "model_number": product.model_number,
        "description": product.description,
        "specifications": product.specifications or {},
        "price": product.price,
        "stock": product.stock,
        "is_available": product.is_available,
        "image_url": product.image_url,
        "merchant_id": product.merchant_id,
        "category_id": product.category_id,
    }


def search_electronics(
    db: Session,
    query: str,
    limit: int = 20,
    brand: str | None = None,
) -> list[dict[str, Any]]:
    """Search available products sold by electronics merchants."""
    clean_query = query.strip() if isinstance(query, str) else ""
    if not clean_query:
        return []

    pattern = f"%{clean_query}%"
    statement = (
        db.query(Product)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .join(Category, Product.category_id == Category.id)
        .filter(
            _electronics_scope(),
            Product.is_available.is_(True),
            or_(
                Product.name.ilike(pattern),
                Product.brand.ilike(pattern),
                Product.description.ilike(pattern),
                Product.model_number.ilike(pattern),
            ),
        )
    )

    if brand and brand.strip():
        statement = statement.filter(Product.brand.ilike(f"%{brand.strip()}%"))

    return [
        _product_data(product)
        for product in statement.order_by(Product.id.asc()).limit(max(1, min(limit, 100))).all()
    ]


def compare_electronics(
    db: Session,
    product_ids: list[int],
) -> dict[str, Any]:
    """Compare two to four backend products using only stored specifications."""
    normalized_ids: list[int] = []
    for value in product_ids:
        if isinstance(value, bool):
            continue
        try:
            product_id = int(value)
        except (TypeError, ValueError):
            continue
        if product_id > 0 and product_id not in normalized_ids:
            normalized_ids.append(product_id)

    if len(normalized_ids) < 2 or len(normalized_ids) > 4:
        raise ValueError("Compare between two and four electronics products.")

    records = (
        db.query(Product)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .join(Category, Product.category_id == Category.id)
        .filter(
            Product.id.in_(normalized_ids),
            _electronics_scope(),
        )
        .all()
    )
    products_by_id = {product.id: product for product in records}
    if len(products_by_id) != len(normalized_ids):
        raise ValueError("One or more selected electronics products were not found.")

    products = [products_by_id[product_id] for product_id in normalized_ids]
    specification_keys: list[str] = [
        "brand",
        "model_number",
        "stock",
        "is_available",
    ]
    for product in products:
        specifications = product.specifications
        if isinstance(specifications, dict):
            for key in specifications:
                if key != "variant_group" and key not in specification_keys:
                    specification_keys.append(key)

    dimensions = [
        {
            "key": key,
            "values": [
                {
                    "product_id": product.id,
                    "value": (
                        getattr(product, key)
                        if key in {"brand", "model_number", "stock", "is_available"}
                        else product.specifications.get(key)
                        if isinstance(product.specifications, dict)
                        else None
                    ),
                }
                for product in products
            ],
        }
        for key in specification_keys
    ]

    return {
        "products": [_product_data(product) for product in products],
        "dimensions": dimensions,
    }


def get_electronic_variants(
    db: Session,
    product_id: int,
) -> list[dict[str, Any]]:
    """Return catalog items sharing the selected item's explicit variant group."""
    try:
        normalized_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("A valid electronics product ID is required.") from exc

    selected = (
        db.query(Product)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .join(Category, Product.category_id == Category.id)
        .filter(
            Product.id == normalized_id,
            _electronics_scope(),
        )
        .first()
    )
    if selected is None:
        return []

    specifications = selected.specifications
    variant_group = (
        specifications.get("variant_group")
        if isinstance(specifications, dict)
        else None
    )
    if not isinstance(variant_group, str) or not variant_group.strip():
        return [_product_data(selected)]

    candidates = (
        db.query(Product)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .join(Category, Product.category_id == Category.id)
        .filter(
            Product.merchant_id == selected.merchant_id,
            Product.category_id == selected.category_id,
            _electronics_scope(),
        )
        .order_by(Product.id.asc())
        .all()
    )
    variants = [
        product
        for product in candidates
        if isinstance(product.specifications, dict)
        and product.specifications.get("variant_group") == variant_group
    ]
    return [_product_data(product) for product in variants]
