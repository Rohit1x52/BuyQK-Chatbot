"""
BuyQK AI Engine
Cart Tools

Thin AI-facing wrappers around the authoritative CartService.

Architecture:

    ToolRegistry
        ↓
    Cart Tool
        ↓
    CartService
        ↓
    Database

IMPORTANT:
- Cart business rules remain in backend/services/cart_service.py.
- These tools do not directly mutate SQLAlchemy models.
- Product identity and availability remain backend-authoritative.
- Tool failures are normalized into ToolResult.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ai_engine.tools.results import (
    ToolErrorResult,
    ToolResult,
)

from backend.services.cart_service import (
    CartItemNotFoundError,
    CartServiceError,
    InsufficientStockError,
    InvalidQuantityError,
    ProductNotFoundError,
    ProductUnavailableError,
    add_item,
    clear_cart,
    commit_cart,
    get_cart,
    remove_product,
    update_item_quantity,
)


# =========================================================
# Constants
# =========================================================

DEFAULT_CART_QUANTITY = 1


# =========================================================
# Generic Helpers
# =========================================================


def _normalize_positive_integer(
    value: Any,
) -> int | None:
    """
    Normalize a positive integer-like value.

    Accepted:
        1
        "1"
        " 1 "

    Rejected:
        True
        False
        0
        negative integers
        empty strings
        arbitrary strings
        None
        floats
        other objects

    Numeric strings are accepted because planner/entity state
    may have passed through serialization.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            return None

        try:
            parsed = int(normalized)
        except ValueError:
            return None

        return parsed if parsed > 0 else None

    return None


def _normalize_user_id(
    user_id: Any,
) -> int | None:
    """
    Normalize a user identifier.

    User identity must ultimately originate from the
    authenticated/runtime context.
    """

    return _normalize_positive_integer(user_id)


def _normalize_product_id(
    product_id: Any,
) -> int | None:
    """
    Normalize a product database identifier.
    """

    return _normalize_positive_integer(product_id)


def _tool_error(
    tool: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    """
    Create a normalized failed ToolResult.
    """

    return ToolResult.fail(
        tool=tool,
        error=ToolErrorResult(
            code=code,
            message=message,
            details=details,
        ),
    )


def _backend_error(
    tool: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    """
    Normalize an unexpected backend failure.

    Internal exception details are intentionally not exposed
    to the AI/user-facing layer.
    """

    return _tool_error(
        tool=tool,
        code="backend_error",
        message=message,
        details=details,
    )


def _serialize_cart(
    cart: Any,
) -> dict[str, Any]:
    """
    Normalize the CartService response into a dictionary.

    The current CartService returns dictionaries, but the
    boundary remains defensive in case the service changes.
    """

    if isinstance(cart, dict):
        return dict(cart)

    return {
        "cart": cart,
    }


def _cart_result(
    tool: str,
    cart: Any,
) -> ToolResult:
    """
    Build the canonical successful result shape shared by
    all cart mutation/retrieval tools.
    """

    serialized = _serialize_cart(cart)

    return ToolResult.ok(
        tool=tool,
        data={
            "action": tool,
            "cart": serialized,
            "cart_id": (
                serialized.get("cart_id")
                if isinstance(serialized, dict)
                else None
            ),
            "items": (
                serialized.get("items", [])
                if isinstance(serialized, dict)
                else []
            ),
            "summary": (
                serialized.get("summary")
                if isinstance(serialized, dict)
                else None
            ),
        },
    )


# =========================================================
# Add To Cart
# =========================================================


def add_to_cart_tool(
    db: Session,
    user_id: Any,
    product_id: Any,
    quantity: Any,
) -> ToolResult:
    """
    Add a product to the user's cart.

    CartService remains authoritative for:
    - product existence
    - availability
    - stock
    - cart lifecycle
    """

    tool = "add_to_cart"

    normalized_user_id = _normalize_user_id(user_id)

    if normalized_user_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="User ID must be a positive integer.",
            details={"field": "user_id"},
        )

    normalized_product_id = _normalize_product_id(product_id)

    if normalized_product_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="Product ID must be a positive integer.",
            details={"field": "product_id"},
        )

    normalized_quantity = _normalize_positive_integer(quantity)

    if normalized_quantity is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="Quantity must be a positive integer.",
            details={"field": "quantity"},
        )

    try:
        cart = add_item(
            db=db,
            user_id=normalized_user_id,
            product_id=normalized_product_id,
            quantity=normalized_quantity,
        )

        commit_cart(db)

        return _cart_result(
            tool=tool,
            cart=cart,
        )

    except (
        ProductNotFoundError,
        ProductUnavailableError,
        InsufficientStockError,
        InvalidQuantityError,
        CartServiceError,
        ValueError,
    ) as exc:
        return _tool_error(
            tool=tool,
            code="cart_operation_failed",
            message=str(exc),
        )

    except Exception:
        return _backend_error(
            tool=tool,
            message="Unable to add the product to the cart right now.",
        )


# =========================================================
# Remove From Cart
# =========================================================


def remove_from_cart_tool(
    db: Session,
    user_id: Any,
    product_id: Any,
) -> ToolResult:
    """
    Remove a product from the user's cart.

    Removal is performed by product identity rather than
    exposing CartItem database IDs to the AI layer.
    """

    tool = "remove_from_cart"

    normalized_user_id = _normalize_user_id(user_id)

    if normalized_user_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="User ID must be a positive integer.",
            details={"field": "user_id"},
        )

    normalized_product_id = _normalize_product_id(product_id)

    if normalized_product_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="Product ID must be a positive integer.",
            details={"field": "product_id"},
        )

    try:
        cart = remove_product(
            db=db,
            user_id=normalized_user_id,
            product_id=normalized_product_id,
        )

        commit_cart(db)

        return _cart_result(
            tool=tool,
            cart=cart,
        )

    except (
        CartItemNotFoundError,
        ProductNotFoundError,
        ProductUnavailableError,
        CartServiceError,
        ValueError,
    ) as exc:
        return _tool_error(
            tool=tool,
            code="cart_operation_failed",
            message=str(exc),
        )

    except Exception:
        return _backend_error(
            tool=tool,
            message=(
                "Unable to remove the product from the cart right now."
            ),
        )


# =========================================================
# Update Cart Item Quantity
# =========================================================


def update_cart_item_tool(
    db: Session,
    user_id: Any,
    product_id: Any,
    quantity: Any,
) -> ToolResult:
    """
    Update the quantity of an existing product in the cart.

    Canonical AI tool name:
        update_cart_item

    Backend operation:
        update_item_quantity
    """

    tool = "update_cart_item"

    normalized_user_id = _normalize_user_id(user_id)

    if normalized_user_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="User ID must be a positive integer.",
            details={"field": "user_id"},
        )

    normalized_product_id = _normalize_product_id(product_id)

    if normalized_product_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="Product ID must be a positive integer.",
            details={"field": "product_id"},
        )

    normalized_quantity = _normalize_positive_integer(quantity)

    if normalized_quantity is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="Quantity must be a positive integer.",
            details={"field": "quantity"},
        )

    try:
        cart = update_item_quantity(
            db=db,
            user_id=normalized_user_id,
            product_id=normalized_product_id,
            quantity=normalized_quantity,
        )

        commit_cart(db)

        return _cart_result(
            tool=tool,
            cart=cart,
        )

    except (
        CartItemNotFoundError,
        ProductNotFoundError,
        ProductUnavailableError,
        InsufficientStockError,
        InvalidQuantityError,
        CartServiceError,
        ValueError,
    ) as exc:
        return _tool_error(
            tool=tool,
            code="cart_operation_failed",
            message=str(exc),
        )

    except Exception:
        return _backend_error(
            tool=tool,
            message="Unable to update the cart quantity right now.",
        )


# =========================================================
# Clear Cart
# =========================================================


def clear_cart_tool(
    db: Session,
    user_id: Any,
) -> ToolResult:
    """
    Remove all items from the user's active cart.
    """

    tool = "clear_cart"

    normalized_user_id = _normalize_user_id(user_id)

    if normalized_user_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="User ID must be a positive integer.",
            details={"field": "user_id"},
        )

    try:
        cart = clear_cart(
            db=db,
            user_id=normalized_user_id,
        )

        commit_cart(db)

        return _cart_result(
            tool=tool,
            cart=cart,
        )

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        return _tool_error(
            tool=tool,
            code="cart_operation_failed",
            message=str(exc),
        )

    except Exception:
        return _backend_error(
            tool=tool,
            message="Unable to clear the cart right now.",
        )


# =========================================================
# Get Cart
# =========================================================


def get_cart_tool(
    db: Session,
    user_id: Any,
) -> ToolResult:
    """
    Retrieve the user's current cart.

    This operation is strictly read-only.

    It intentionally does NOT call commit_cart().
    """

    tool = "get_cart"

    normalized_user_id = _normalize_user_id(user_id)

    if normalized_user_id is None:
        return _tool_error(
            tool=tool,
            code="validation_error",
            message="User ID must be a positive integer.",
            details={"field": "user_id"},
        )

    try:
        cart = get_cart(
            db=db,
            user_id=normalized_user_id,
        )

        return _cart_result(
            tool=tool,
            cart=cart,
        )

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        return _tool_error(
            tool=tool,
            code="cart_operation_failed",
            message=str(exc),
        )

    except Exception:
        return _backend_error(
            tool=tool,
            message="Unable to retrieve your cart right now.",
        )


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "DEFAULT_CART_QUANTITY",
    "add_to_cart_tool",
    "remove_from_cart_tool",
    "update_cart_item_tool",
    "clear_cart_tool",
    "get_cart_tool",
]
