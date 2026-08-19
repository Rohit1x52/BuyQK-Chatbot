# ============================================================
# BuyQK - Cart API
# ============================================================
#
# Purpose:
#   Expose the backend cart service through FastAPI.
#
# Architecture:
#
#   Frontend / Client
#          ↓
#   Cart API
#          ↓
#   Cart Service
#          ↓
#   SQLAlchemy
#          ↓
#   Database
#
# IMPORTANT:
#
# The API layer does NOT:
#
#   - calculate prices
#   - calculate stock
#   - calculate totals
#   - resolve products by natural language
#   - interpret AI intent
#   - modify quantities using AI reasoning
#   - authorize checkout
#   - create orders
#
# The Cart Service remains authoritative for cart state,
# product availability, stock validation, quantities and
# monetary calculations.
#
# ============================================================

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from backend.database.dependencies import get_db

from backend.services.cart_service import (
    CartServiceError,
    CartItemNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
    ProductNotFoundError,
    ProductUnavailableError,
    add_item,
    clear_cart,
    commit_cart,
    get_cart,
    remove_item,
    remove_product,
    update_item_quantity,
    update_quantity,
)


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
)


# ============================================================
# Schemas
# ============================================================


class CartAddItemRequest(BaseModel):
    """
    Request to add a product to the user's active cart.
    """

    user_id: int = Field(
        ...,
        ge=1,
        description="User who owns the cart.",
    )

    product_id: int = Field(
        ...,
        ge=1,
        description="Authoritative product database ID.",
    )

    quantity: int = Field(
        ...,
        ge=1,
        description="Quantity to add.",
    )


class CartUpdateItemRequest(BaseModel):
    """
    Request to replace the quantity of an existing cart item.
    """

    user_id: int = Field(
        ...,
        ge=1,
        description="User who owns the cart.",
    )

    quantity: int = Field(
        ...,
        ge=1,
        description="New quantity for the cart item.",
    )


class CartUpdateProductRequest(BaseModel):
    """
    Request to replace the quantity of a product in the cart.

    This endpoint is useful when the client knows the product ID
    but does not need to expose the CartItem ID.
    """

    user_id: int = Field(
        ...,
        ge=1,
        description="User who owns the cart.",
    )

    quantity: int = Field(
        ...,
        ge=1,
        description="New quantity for the product.",
    )


class CartProductRequest(BaseModel):
    """
    Request used when removing a product by product ID.
    """

    user_id: int = Field(
        ...,
        ge=1,
        description="User who owns the cart.",
    )


# ============================================================
# Error Handling
# ============================================================


def _cart_error_response(
    exc: CartServiceError,
) -> HTTPException:
    """
    Convert authoritative cart-service exceptions into
    appropriate HTTP responses.

    The API does not replace the service error with invented
    business logic. It only maps the backend error to HTTP.
    """

    if isinstance(
        exc,
        (
            ProductNotFoundError,
            CartItemNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(
        exc,
        (
            InsufficientStockError,
            ProductUnavailableError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if isinstance(
        exc,
        InvalidQuantityError,
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _rollback_and_raise(
    db: Session,
    exc: Exception,
) -> None:
    """
    Roll back the current SQLAlchemy transaction and raise
    an appropriate API exception.
    """

    db.rollback()

    if isinstance(
        exc,
        CartServiceError,
    ):
        raise _cart_error_response(
            exc
        ) from exc

    if isinstance(
        exc,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to process the cart operation.",
    ) from exc


# ============================================================
# GET /cart
# ============================================================


@router.get(
    "",
    status_code=status.HTTP_200_OK,
)
def get_user_cart(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the user's active cart.

    The cart service creates an empty active cart when one does
    not already exist.
    """

    try:
        cart = get_cart(
            db=db,
            user_id=user_id,
        )

        # get_cart() may create the user's first cart.
        # Persist that authoritative state.
        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# POST /cart/items
# ============================================================


@router.post(
    "/items",
    status_code=status.HTTP_200_OK,
)
def add_cart_item(
    request: CartAddItemRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Add a product to the user's active cart.

    If the product already exists, the cart service increases
    the existing quantity instead of creating a duplicate item.
    """

    try:
        cart = add_item(
            db=db,
            user_id=request.user_id,
            product_id=request.product_id,
            quantity=request.quantity,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# PATCH /cart/items/{cart_item_id}
# ============================================================


@router.patch(
    "/items/{cart_item_id}",
    status_code=status.HTTP_200_OK,
)
def update_cart_item(
    request: CartUpdateItemRequest,
    cart_item_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Replace the quantity of an existing CartItem.
    """

    try:
        cart = update_quantity(
            db=db,
            user_id=request.user_id,
            cart_item_id=cart_item_id,
            quantity=request.quantity,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# PATCH /cart/products/{product_id}
# ============================================================


@router.patch(
    "/products/{product_id}",
    status_code=status.HTTP_200_OK,
)
def update_cart_product(
    request: CartUpdateProductRequest,
    product_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Replace the quantity of a product already present in the
    user's cart.

    This endpoint uses product_id rather than cart_item_id.
    """

    try:
        cart = update_item_quantity(
            db=db,
            user_id=request.user_id,
            product_id=product_id,
            quantity=request.quantity,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# DELETE /cart/items/{cart_item_id}
# ============================================================


@router.delete(
    "/items/{cart_item_id}",
    status_code=status.HTTP_200_OK,
)
def remove_cart_item(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    cart_item_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Remove one CartItem from the user's active cart.
    """

    try:
        cart = remove_item(
            db=db,
            user_id=user_id,
            cart_item_id=cart_item_id,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# DELETE /cart/products/{product_id}
# ============================================================


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_200_OK,
)
def remove_cart_product(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    product_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Remove a product from the user's active cart by product ID.
    """

    try:
        cart = remove_product(
            db=db,
            user_id=user_id,
            product_id=product_id,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )


# ============================================================
# DELETE /cart
# ============================================================


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
)
def clear_user_cart(
    user_id: int = Path(
        ...,
        ge=1,
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Remove all items from the user's active cart.

    The cart itself remains active and available for future use.
    """

    try:
        cart = clear_cart(
            db=db,
            user_id=user_id,
        )

        commit_cart(
            db=db,
        )

        return {
            "success": True,
            "cart": cart,
        }

    except (
        CartServiceError,
        ValueError,
    ) as exc:
        _rollback_and_raise(
            db,
            exc,
        )

    except Exception as exc:
        _rollback_and_raise(
            db,
            exc,
        )