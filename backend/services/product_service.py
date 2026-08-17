# Purpose:
# Contains business logic for BuyQK product operations.
#
# Responsibilities:
# - Search products
# - Retrieve a product by ID
# - Check product availability
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
) -> list[Product]:
    """
    Search for products using name, brand, or description.

    Args:
        db:
            Active SQLAlchemy database session.

        query:
            Product search text.

        limit:
            Maximum number of products to return.

    Returns:
        List of matching Product objects.
    """

    # Remove unnecessary whitespace.
    query = query.strip()

    # Don't perform an empty database search.
    if not query:
        return []

    # SQL LIKE pattern.
    search_pattern = f"%{query}%"

    products = (
        db.query(Product)
        .filter(
            Product.is_available.is_(True),
            or_(
                Product.name.ilike(search_pattern),
                Product.brand.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            ),
        )
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