"""
BuyQK Product Tools.

This module is the AI-facing adapter around the product service layer.

Architecture:

    ToolRegistry
          ↓
    Product Tools
          ↓
    Product Service
          ↓
      Database

Responsibilities:
    - Validate tool inputs.
    - Call the existing product service.
    - Convert ORM Product objects into serializable dictionaries.
    - Return standardized ToolResult objects.

This module must NOT:
    - Query the database directly.
    - Implement product business rules.
    - Invent product information.
    - Perform semantic product matching.
    - Generate customer-facing responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ai_engine.tools.results import (
    ToolErrorResult,
    ToolResult,
)
from backend.models.product import Product
from backend.services.product_service import (
    check_product_availability,
    get_product,
    search_products,
)


# =========================================================
# Canonical Tool Names
# =========================================================

SEARCH_PRODUCTS_TOOL = "search_products"
GET_PRODUCT_TOOL = "get_product"
CHECK_PRODUCT_AVAILABILITY_TOOL = (
    "check_product_availability"
)


# =========================================================
# Product Serialization
# =========================================================


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    """
    Convert a datetime into an ISO-8601 string.

    None remains None.
    """

    if value is None:
        return None

    return value.isoformat()


def _serialize_product(
    product: Product,
) -> dict[str, Any]:
    """
    Convert a SQLAlchemy Product object into plain
    serializable data.

    No business logic is performed here.
    """

    serialized = {
        "id": product.id,
        "merchant_id": product.merchant_id,
        "category_id": product.category_id,
        "name": product.name,
        "description": product.description,
        "brand": product.brand,
        "price": product.price,
        "stock": product.stock,
        "image_url": product.image_url,
        "is_available": product.is_available,
        "created_at": _serialize_datetime(
            product.created_at
        ),
        "updated_at": _serialize_datetime(
            product.updated_at
        ),
    }

    for field in (
        "model_number",
        "specifications",
        "prescription_required",
    ):
        if hasattr(product, field):
            serialized[field] = getattr(product, field)

    return serialized


# =========================================================
# Error Helpers
# =========================================================


def _validation_error(
    tool: str,
    message: str,
    *,
    field: str | None = None,
) -> ToolResult:
    """
    Create a standardized validation failure.
    """

    details = (
        {"field": field}
        if field is not None
        else None
    )

    return ToolResult.fail(
        tool=tool,
        error=ToolErrorResult(
            code="validation_error",
            message=message,
            details=details,
        ),
    )


def _backend_error(
    tool: str,
    message: str,
) -> ToolResult:
    """
    Create a standardized backend failure.

    Internal exception information is deliberately not
    exposed through the ToolResult.
    """

    return ToolResult.fail(
        tool=tool,
        error=ToolErrorResult(
            code="backend_error",
            message=message,
        ),
    )


def _not_found_error(
    tool: str,
    message: str,
    *,
    resource_id: int,
) -> ToolResult:
    """
    Create a standardized not-found failure.
    """

    return ToolResult.fail(
        tool=tool,
        error=ToolErrorResult(
            code="not_found",
            message=message,
            details={
                "product_id": resource_id,
            },
        ),
    )


# =========================================================
# Search Products
# =========================================================


def search_products_tool(
    db: Session,
    query: str,
    limit: int = 10,
    brand: str | None = None,
    category_id: int | None = None,
    merchant_id: int | None = None,
    model_number: str | None = None,
    prescription_required: bool | None = None,
) -> ToolResult:
    """
    Search available products.

    Backend search semantics are delegated entirely to
    product_service.search_products().

    Optional structured filters:

        brand
        category_id
        merchant_id
        model_number
        prescription_required
    """

    tool = SEARCH_PRODUCTS_TOOL

    # -----------------------------------------------------
    # Query validation
    # -----------------------------------------------------

    if not isinstance(query, str):
        return _validation_error(
            tool,
            "Product search query must be text.",
            field="query",
        )

    query = query.strip()

    if not query:
        return _validation_error(
            tool,
            "Product search query is required.",
            field="query",
        )

    # -----------------------------------------------------
    # Limit validation
    # -----------------------------------------------------

    if isinstance(limit, bool):
        return _validation_error(
            tool,
            "Product search limit must be a positive integer.",
            field="limit",
        )

    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return _validation_error(
                tool,
                "Product search limit must be a positive integer.",
                field="limit",
            )

    if limit <= 0:
        return _validation_error(
            tool,
            "Product search limit must be a positive integer.",
            field="limit",
        )

    # Keep tool requests bounded.
    limit = min(limit, 100)

    # -----------------------------------------------------
    # Optional filter validation
    # -----------------------------------------------------

    if brand is not None:
        if not isinstance(brand, str):
            return _validation_error(
                tool,
                "Product brand filter must be text.",
                field="brand",
            )

        brand = brand.strip() or None

    if category_id is not None:
        if isinstance(category_id, bool):
            return _validation_error(
                tool,
                "Category ID must be a positive integer.",
                field="category_id",
            )

        if not isinstance(category_id, int):
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                return _validation_error(
                    tool,
                    "Category ID must be a positive integer.",
                    field="category_id",
                )

        if category_id <= 0:
            return _validation_error(
                tool,
                "Category ID must be a positive integer.",
                field="category_id",
            )

    if merchant_id is not None:
        if isinstance(merchant_id, bool):
            return _validation_error(
                tool,
                "Merchant ID must be a positive integer.",
                field="merchant_id",
            )

        if not isinstance(merchant_id, int):
            try:
                merchant_id = int(merchant_id)
            except (TypeError, ValueError):
                return _validation_error(
                    tool,
                    "Merchant ID must be a positive integer.",
                    field="merchant_id",
                )

        if merchant_id <= 0:
            return _validation_error(
                tool,
                "Merchant ID must be a positive integer.",
                field="merchant_id",
            )

    if model_number is not None:
        if not isinstance(model_number, str):
            return _validation_error(
                tool,
                "Model number filter must be text.",
                field="model_number",
            )

        model_number = model_number.strip() or None

    if prescription_required is not None:
        if not isinstance(
            prescription_required,
            bool,
        ):
            return _validation_error(
                tool,
                "Prescription requirement filter must be boolean.",
                field="prescription_required",
            )

    # -----------------------------------------------------
    # Backend operation
    # -----------------------------------------------------

    try:
        search_arguments = {
            "db": db,
            "query": query,
            "limit": limit,
        }
        optional_filters = {
            "brand": brand,
            "category_id": category_id,
            "merchant_id": merchant_id,
            "model_number": model_number,
            "prescription_required": prescription_required,
        }
        search_arguments.update({
            key: value
            for key, value in optional_filters.items()
            if value is not None
        })
        products = search_products(**search_arguments)
    except Exception:
        return _backend_error(
            tool,
            "Unable to search products right now.",
        )

    # -----------------------------------------------------
    # Normalize backend objects
    # -----------------------------------------------------

    serialized_products = [
        _serialize_product(product)
        for product in products
    ]

    return ToolResult.ok(
        tool=tool,
        data={
            "products": serialized_products,
            "count": len(serialized_products),
            "query": query,
        },
    )


# =========================================================
# Get Product
# =========================================================


def get_product_tool(
    db: Session,
    product_id: int,
) -> ToolResult:
    """
    Retrieve one product by database ID.
    """

    tool = GET_PRODUCT_TOOL

    # -----------------------------------------------------
    # Product ID validation
    # -----------------------------------------------------

    if isinstance(product_id, bool):
        return _validation_error(
            tool,
            "Product ID must be a positive integer.",
            field="product_id",
        )

    if not isinstance(product_id, int):
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return _validation_error(
                tool,
                "Product ID must be a positive integer.",
                field="product_id",
            )

    if product_id <= 0:
        return _validation_error(
            tool,
            "Product ID must be a positive integer.",
            field="product_id",
        )

    # -----------------------------------------------------
    # Backend operation
    # -----------------------------------------------------

    try:
        product = get_product(
            db=db,
            product_id=product_id,
        )
    except Exception:
        return _backend_error(
            tool,
            "Unable to retrieve the product right now.",
        )

    # -----------------------------------------------------
    # Product not found
    # -----------------------------------------------------

    if product is None:
        return _not_found_error(
            tool,
            f"Product {product_id} does not exist.",
            resource_id=product_id,
        )

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    return ToolResult.ok(
        tool=tool,
        data={
            "product": _serialize_product(product),
        },
    )


# =========================================================
# Check Product Availability
# =========================================================


def check_product_availability_tool(
    db: Session,
    product_id: int,
    quantity: int = 1,
) -> ToolResult:
    """
    Check whether a product is available in the requested
    quantity.

    Availability and stock rules remain authoritative in
    product_service.check_product_availability().
    """

    tool = CHECK_PRODUCT_AVAILABILITY_TOOL

    # -----------------------------------------------------
    # Product ID validation
    # -----------------------------------------------------

    if isinstance(product_id, bool):
        return _validation_error(
            tool,
            "Product ID must be a positive integer.",
            field="product_id",
        )

    if not isinstance(product_id, int):
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return _validation_error(
                tool,
                "Product ID must be a positive integer.",
                field="product_id",
            )

    if product_id <= 0:
        return _validation_error(
            tool,
            "Product ID must be a positive integer.",
            field="product_id",
        )

    # -----------------------------------------------------
    # Quantity validation
    # -----------------------------------------------------

    if isinstance(quantity, bool):
        return _validation_error(
            tool,
            "Quantity must be a positive integer.",
            field="quantity",
        )

    if not isinstance(quantity, int):
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return _validation_error(
                tool,
                "Quantity must be a positive integer.",
                field="quantity",
            )

    if quantity <= 0:
        return _validation_error(
            tool,
            "Quantity must be a positive integer.",
            field="quantity",
        )

    # -----------------------------------------------------
    # Authoritative availability check
    # -----------------------------------------------------

    try:
        available = check_product_availability(
            db=db,
            product_id=product_id,
            quantity=quantity,
        )
    except Exception:
        return _backend_error(
            tool,
            "Unable to check product availability right now.",
        )

    # -----------------------------------------------------
    # Retrieve product information
    #
    # The availability service intentionally returns a bool.
    # We separately retrieve the authoritative product record
    # so the tool result can provide useful context.
    # -----------------------------------------------------

    try:
        product = get_product(
            db=db,
            product_id=product_id,
        )
    except Exception:
        return _backend_error(
            tool,
            "Unable to retrieve product information right now.",
        )

    if product is None:
        return _not_found_error(
            tool,
            f"Product {product_id} does not exist.",
            resource_id=product_id,
        )

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    return ToolResult.ok(
        tool=tool,
        data={
            "product": _serialize_product(product),
            "product_id": product_id,
            "quantity": quantity,
            "available": available,
        },
    )


# =========================================================
# Public API
# =========================================================


__all__ = [
    "SEARCH_PRODUCTS_TOOL",
    "GET_PRODUCT_TOOL",
    "CHECK_PRODUCT_AVAILABILITY_TOOL",
    "search_products_tool",
    "get_product_tool",
    "check_product_availability_tool",
]