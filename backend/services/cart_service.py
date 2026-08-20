"""
BuyQK Cart Service

Authoritative backend service for shopping-cart operations.

Responsibilities:
    - Get or create a user's active cart.
    - Add products to the cart.
    - Remove products from the cart.
    - Update item quantities.
    - Clear the cart.
    - Retrieve the cart.
    - Calculate the current cart summary.
    - Validate product availability and stock.

Architecture:

    AI / Planner
        ↓
    Tool Node
        ↓
    Cart Service
        ↓
    Database

IMPORTANT:
    The AI does NOT calculate prices, stock, subtotals, discounts,
    delivery charges, or totals.

CartItem stores only:
    - cart_id
    - product_id
    - quantity

Current product information comes from Product.

Historical purchase pricing belongs to OrderItem.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.cart import Cart
from backend.models.cart_item import CartItem
from backend.models.product import Product


# ============================================================
# Constants
# ============================================================

ACTIVE_CART_STATUS = "active"


# ============================================================
# Exceptions
# ============================================================


class CartServiceError(Exception):
    """Base exception for cart-service errors."""


class ProductNotFoundError(CartServiceError):
    """Raised when the requested product does not exist."""


class ProductUnavailableError(CartServiceError):
    """Raised when a product is not currently available."""


class InsufficientStockError(CartServiceError):
    """Raised when requested quantity exceeds available stock."""


class CartItemNotFoundError(CartServiceError):
    """Raised when a cart item does not exist."""


class InvalidQuantityError(CartServiceError):
    """Raised when a quantity is invalid."""


# ============================================================
# Internal Helpers
# ============================================================


def _validate_quantity(quantity: int) -> int:
    """
    Validate and normalize a cart quantity.

    Quantity must be a positive integer.
    """

    if isinstance(quantity, bool):
        raise InvalidQuantityError(
            "Quantity must be a positive integer."
        )

    try:
        normalized_quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise InvalidQuantityError(
            "Quantity must be a positive integer."
        ) from exc

    if normalized_quantity <= 0:
        raise InvalidQuantityError(
            "Quantity must be greater than zero."
        )

    return normalized_quantity


def _get_product(
    db: Session,
    product_id: int,
) -> Product:
    """
    Retrieve a product by ID.

    Product existence, availability, and stock are
    authoritative backend facts.
    """

    product = db.execute(
        select(Product).where(
            Product.id == product_id
        )
    ).scalar_one_or_none()

    if product is None:
        raise ProductNotFoundError(
            f"Product {product_id} was not found."
        )

    if not product.is_available:
        raise ProductUnavailableError(
            f"Product {product_id} is currently unavailable."
        )

    return product


def _get_active_cart(
    db: Session,
    user_id: int,
) -> Cart | None:
    """
    Return the user's current active cart, if one exists.

    IMPORTANT:
    The cart and its items are freshly loaded from the database.
    """

    return (
        db.execute(
            select(Cart)
            .options(
                joinedload(Cart.items)
                .joinedload(CartItem.product)
            )
            .where(
                Cart.user_id == user_id,
                Cart.status == ACTIVE_CART_STATUS,
            )
            .order_by(Cart.id.desc())
        )
        .unique()
        .scalars()
        .first()
    )


def _refresh_cart(
    db: Session,
    cart_id: int,
) -> Cart:
    """
    Reload a cart from the database.

    This is important after INSERT/UPDATE/DELETE operations because
    SQLAlchemy's in-memory relationship collection may otherwise
    still contain stale CartItem objects.

    The returned Cart has its items and products freshly loaded.
    """

    db.expire_all()

    cart = (
        db.execute(
            select(Cart)
            .options(
                joinedload(Cart.items)
                .joinedload(CartItem.product)
            )
            .where(
                Cart.id == cart_id
            )
        )
        .unique()
        .scalar_one_or_none()
    )

    if cart is None:
        raise CartServiceError(
            f"Cart {cart_id} was not found."
        )

    return cart


def _serialize_item(
    item: CartItem,
) -> dict[str, Any]:
    """
    Convert a CartItem into a frontend/API-safe dictionary.

    Current product information is read from Product.
    """

    product = item.product

    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": product.name,
        "brand": product.brand,
        "description": product.description,
        "image_url": product.image_url,
        "quantity": item.quantity,
        "unit_price": float(product.price),
        "line_total": float(
            product.price * item.quantity
        ),
        "stock": product.stock,
        "is_available": product.is_available,
    }


def _build_summary(
    items: list[CartItem],
) -> dict[str, Any]:
    """
    Calculate the current cart summary from authoritative
    Product prices.

    The AI never supplies monetary values.

    Delivery, discount, and tax remain None until their
    respective backend services are implemented.
    """

    serialized_items = [
        _serialize_item(item)
        for item in items
    ]

    subtotal = sum(
        item["line_total"]
        for item in serialized_items
    )

    total_quantity = sum(
        item["quantity"]
        for item in serialized_items
    )

    return {
        "item_count": len(serialized_items),
        "total_quantity": total_quantity,
        "subtotal": float(subtotal),
        "currency": "INR",
        "delivery_charge": None,
        "discount": None,
        "tax": None,
        "total": float(subtotal),
    }


def _serialize_cart(
    cart: Cart,
) -> dict[str, Any]:
    """
    Serialize a cart and its freshly loaded contents.
    """

    items = list(cart.items)

    return {
        "cart_id": cart.id,
        "user_id": cart.user_id,
        "status": cart.status,
        "items": [
            _serialize_item(item)
            for item in items
        ],
        "summary": _build_summary(items),
        "created_at": cart.created_at,
        "updated_at": cart.updated_at,
    }


# ============================================================
# Get / Create Cart
# ============================================================


def get_or_create_cart(
    db: Session,
    user_id: int,
) -> Cart:
    """
    Return the user's active cart.

    If no active cart exists, create one.

    The database is authoritative for cart ownership.
    """

    if user_id is None:
        raise ValueError(
            "user_id is required."
        )

    cart = _get_active_cart(
        db=db,
        user_id=user_id,
    )

    if cart is not None:
        return cart

    cart = Cart(
        user_id=user_id,
        status=ACTIVE_CART_STATUS,
    )

    db.add(cart)
    db.flush()

    # Return a fresh database-backed representation.
    return _refresh_cart(
        db=db,
        cart_id=cart.id,
    )


# ============================================================
# Get Cart
# ============================================================


def get_cart(
    db: Session,
    user_id: int,
) -> dict[str, Any]:
    """
    Retrieve the user's active cart.

    An empty cart is created when the user does not yet have
    an active cart.
    """

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    cart = _refresh_cart(
        db=db,
        cart_id=cart.id,
    )

    return _serialize_cart(cart)


# ============================================================
# Add Item
# ============================================================


def add_item(
    db: Session,
    user_id: int,
    product_id: int,
    quantity: int,
) -> dict[str, Any]:
    """
    Add a product to the user's cart.

    If the product already exists in the cart, its quantity is
    increased rather than creating a duplicate CartItem.

    Stock is checked against the resulting total quantity.
    """

    normalized_quantity = _validate_quantity(
        quantity
    )

    product = _get_product(
        db=db,
        product_id=product_id,
    )

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    existing_item = next(
        (
            item
            for item in cart.items
            if item.product_id == product.id
        ),
        None,
    )

    current_quantity = (
        existing_item.quantity
        if existing_item is not None
        else 0
    )

    requested_total = (
        current_quantity
        + normalized_quantity
    )

    if requested_total > product.stock:
        raise InsufficientStockError(
            f"Only {product.stock} unit(s) of "
            f"'{product.name}' are available."
        )

    if existing_item is not None:
        existing_item.quantity = requested_total

    else:
        existing_item = CartItem(
            cart=cart,
            product=product,
            quantity=normalized_quantity,
        )

        db.add(existing_item)

    db.flush()

    # IMPORTANT:
    # Reload after mutation so the response represents the
    # actual database state.
    cart = _refresh_cart(
        db=db,
        cart_id=cart.id,
    )

    return _serialize_cart(cart)


# ============================================================
# Update Quantity
# ============================================================


def update_quantity(
    db: Session,
    user_id: int,
    cart_item_id: int,
    quantity: int,
) -> dict[str, Any]:
    """
    Replace the quantity of an existing cart item.

    The resulting quantity must not exceed backend-reported
    product stock.
    """

    normalized_quantity = _validate_quantity(
        quantity
    )

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    item = next(
        (
            item
            for item in cart.items
            if item.id == cart_item_id
        ),
        None,
    )

    if item is None:
        raise CartItemNotFoundError(
            f"Cart item {cart_item_id} was not found."
        )

    product = _get_product(
        db=db,
        product_id=item.product_id,
    )

    if normalized_quantity > product.stock:
        raise InsufficientStockError(
            f"Only {product.stock} unit(s) of "
            f"'{product.name}' are available."
        )

    item.quantity = normalized_quantity

    db.flush()

    cart = _refresh_cart(
        db=db,
        cart_id=cart.id,
    )

    return _serialize_cart(cart)


# ============================================================
# Update Quantity By Product
# ============================================================


def update_item_quantity(
    db: Session,
    user_id: int,
    product_id: int,
    quantity: int,
) -> dict[str, Any]:
    """
    Update the quantity of a product already present in the cart.

    Useful for AI/tool operations where the AI identifies a
    product rather than a CartItem ID.
    """

    normalized_quantity = _validate_quantity(
        quantity
    )

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    item = next(
        (
            item
            for item in cart.items
            if item.product_id == product_id
        ),
        None,
    )

    if item is None:
        raise CartItemNotFoundError(
            f"Product {product_id} is not in the cart."
        )

    product = _get_product(
        db=db,
        product_id=product_id,
    )

    if normalized_quantity > product.stock:
        raise InsufficientStockError(
            f"Only {product.stock} unit(s) of "
            f"'{product.name}' are available."
        )

    item.quantity = normalized_quantity

    db.flush()

    cart = _refresh_cart(
        db=db,
        cart_id=cart.id,
    )

    return _serialize_cart(cart)


# ============================================================
# Remove Item
# ============================================================


def remove_item(
    db: Session,
    user_id: int,
    cart_item_id: int,
) -> dict[str, Any]:
    """
    Remove one CartItem from the user's active cart.

    The returned cart is reloaded after deletion so the deleted
    item cannot remain in the response because of a stale
    SQLAlchemy relationship collection.
    """

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    item = next(
        (
            item
            for item in cart.items
            if item.id == cart_item_id
        ),
        None,
    )

    if item is None:
        raise CartItemNotFoundError(
            f"Cart item {cart_item_id} was not found."
        )

    cart_id = cart.id

    db.delete(item)
    db.flush()

    # CRITICAL FIX:
    # Do not serialize the old cart.items collection.
    cart = _refresh_cart(
        db=db,
        cart_id=cart_id,
    )

    return _serialize_cart(cart)


# ============================================================
# Remove Item By Product
# ============================================================


def remove_product(
    db: Session,
    user_id: int,
    product_id: int,
) -> dict[str, Any]:
    """
    Remove a product from the user's active cart.

    Useful when the AI/tool layer identifies the product but
    does not have a CartItem ID.
    """

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    item = next(
        (
            item
            for item in cart.items
            if item.product_id == product_id
        ),
        None,
    )

    if item is None:
        raise CartItemNotFoundError(
            f"Product {product_id} is not in the cart."
        )

    cart_id = cart.id

    db.delete(item)
    db.flush()

    # CRITICAL FIX:
    # Reload the relationship from the database.
    cart = _refresh_cart(
        db=db,
        cart_id=cart_id,
    )

    return _serialize_cart(cart)


# ============================================================
# Clear Cart
# ============================================================


def clear_cart(
    db: Session,
    user_id: int,
) -> dict[str, Any]:
    """
    Remove all items from the user's active cart.

    The cart itself remains available for future use.
    """

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    cart_id = cart.id

    for item in list(cart.items):
        db.delete(item)

    db.flush()

    # CRITICAL FIX:
    # Reload after all DELETE operations.
    cart = _refresh_cart(
        db=db,
        cart_id=cart_id,
    )

    return _serialize_cart(cart)


# ============================================================
# Cart Summary
# ============================================================


def calculate_cart(
    db: Session,
    user_id: int,
) -> dict[str, Any]:
    """
    Return the backend-calculated cart summary.

    No AI-generated monetary values are accepted here.
    """

    cart = get_or_create_cart(
        db=db,
        user_id=user_id,
    )

    cart = _refresh_cart(
        db=db,
        cart_id=cart.id,
    )

    serialized = _serialize_cart(cart)

    return serialized["summary"]


# ============================================================
# Commit Helper
# ============================================================


def commit_cart(
    db: Session,
) -> None:
    """
    Commit a completed cart mutation.

    Transaction ownership remains with the caller/service
    boundary rather than being hidden inside every operation.
    """

    db.commit()