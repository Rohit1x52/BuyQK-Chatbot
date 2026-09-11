# Purpose:
# Contains business logic for BuyQK product operations.
#
# Responsibilities:
# - Search products
# - Retrieve a product by ID
# - Check product availability
# - Support optional commerce-specific product filters
#
# This service is used by:
# - FastAPI endpoints
# - LangGraph tools
#
# Database access is kept here instead of inside
# LangGraph nodes.


from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models.product import Product


# ---------------------------------------------------------
# Search Products
# ---------------------------------------------------------

def search_products(
    db: Session,
    query: str,
    limit: int = 10,
    brand: str | None = None,
    category_id: int | None = None,
    merchant_id: int | None = None,
    model_number: str | None = None,
    prescription_required: bool | None = None,
) -> list[Product]:
    """
    Search for products using the existing product search fields
    with optional structured filters.

    Existing behavior remains:

        name
        brand
        description

    Optional filters support:

        brand
        category_id
        merchant_id
        model_number
        prescription_required

    Args:
        db:
            Active SQLAlchemy database session.

        query:
            Product search text.

        limit:
            Maximum number of products to return.

        brand:
            Optional brand filter.

        category_id:
            Optional category ID filter.

        merchant_id:
            Optional merchant ID filter.

        model_number:
            Optional model number filter.

        prescription_required:
            Optional medicine prescription requirement filter.

    Returns:
        List of matching Product objects.
    """

    # ---------------------------------------------------------
    # Preserve existing query behavior.
    # ---------------------------------------------------------

    query = query.strip()

    # Don't perform an empty database search.
    if not query:
        return []

    # SQL LIKE pattern.
    search_pattern = f"%{query}%"

    # ---------------------------------------------------------
    # Existing search.
    #
    # DO NOT remove or change these fields.
    # ---------------------------------------------------------

    filters = [
        Product.is_available.is_(True),
        or_(
            Product.name.ilike(search_pattern),
            Product.brand.ilike(search_pattern),
            Product.description.ilike(search_pattern),
        ),
    ]

    # ---------------------------------------------------------
    # Optional structured filters.
    # ---------------------------------------------------------

    if brand is not None:
        brand = brand.strip()

        if brand:
            filters.append(
                Product.brand.ilike(
                    f"%{brand}%"
                )
            )

    if category_id is not None:
        filters.append(
            Product.category_id == category_id
        )

    if merchant_id is not None:
        filters.append(
            Product.merchant_id == merchant_id
        )

    if model_number is not None:
        model_number = model_number.strip()

        if model_number:
            filters.append(
                Product.model_number.ilike(
                    f"%{model_number}%"
                )
            )

    if prescription_required is not None:
        filters.append(
            Product.prescription_required.is_(
                prescription_required
            )
        )

    products = (
        db.query(Product)
        .filter(*filters)
        .limit(limit)
        .all()
    )

    return products


# ---------------------------------------------------------
# Get Product
# ---------------------------------------------------------

def get_product(
    db: Session,
    product_id: int,
) -> Product | None:
    """
    Retrieve a product by its database ID.

    Args:
        db:
            Active SQLAlchemy database session.

        product_id:
            Product database ID.

    Returns:
        Product object if found, otherwise None.
    """

    return (
        db.query(Product)
        .filter(
            Product.id == product_id
        )
        .first()
    )


# ---------------------------------------------------------
# Check Product Availability
# ---------------------------------------------------------

def check_product_availability(
    db: Session,
    product_id: int,
    quantity: int = 1,
) -> bool:
    """
    Check whether a product is available
    in the requested quantity.

    Args:
        db:
            Active SQLAlchemy database session.

        product_id:
            Product database ID.

        quantity:
            Number of units required.

    Returns:
        True if the product exists, is available,
        and has sufficient stock.
    """

    if quantity <= 0:
        return False

    product = get_product(
        db=db,
        product_id=product_id,
    )

    if product is None:
        return False

    if not product.is_available:
        return False

    if product.stock < quantity:
        return False

    return True