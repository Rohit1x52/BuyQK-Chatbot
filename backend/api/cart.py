# ============================================================
# BuyQK - Cart FastAPI API
# ============================================================
#
# Contract:
#   GET    /cart?user_id=1
#   POST   /cart/items
#   PATCH  /cart/items/{item_id}
#   DELETE /cart/items/{item_id}?user_id=1
#   DELETE /cart?user_id=1
#
# The CartService remains the only business-logic authority.
# This API layer only validates transport data and delegates.
# ============================================================

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.dependencies import get_db
from backend.services.cart_service import (
    add_item,
    clear_cart,
    get_cart,
    remove_item,
    update_quantity,
    ProductNotFoundError,
    ProductUnavailableError,
    InsufficientStockError,
    InvalidQuantityError,
    CartItemNotFoundError,
    CartServiceError,
)


router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
)


class AddCartItemRequest(BaseModel):
    user_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class UpdateCartItemRequest(BaseModel):
    user_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


def _cart_response(cart: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "cart": cart,
    }


@router.get("")
def get_cart_endpoint(
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    try:
        return _cart_response(
            get_cart(
                db=db,
                user_id=user_id,
            )
        )
    except (ValueError, CartServiceError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/items")
def add_cart_item_endpoint(
    request: AddCartItemRequest,
    db: Session = Depends(get_db),
):
    try:
        cart = add_item(
            db=db,
            user_id=request.user_id,
            product_id=request.product_id,
            quantity=request.quantity,
        )
        db.commit()
        return _cart_response(cart)
    except (
        ProductNotFoundError,
        ProductUnavailableError,
        InsufficientStockError,
        InvalidQuantityError,
        CartServiceError,
        ValueError,
    ) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.patch("/items/{item_id}")
def update_cart_item_endpoint(
    item_id: int,
    request: UpdateCartItemRequest,
    db: Session = Depends(get_db),
):
    if item_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="A valid cart item ID is required.",
        )

    try:
        cart = update_quantity(
            db=db,
            user_id=request.user_id,
            cart_item_id=item_id,
            quantity=request.quantity,
        )
        db.commit()
        return _cart_response(cart)
    except (
        CartItemNotFoundError,
        InvalidQuantityError,
        InsufficientStockError,
        CartServiceError,
        ValueError,
    ) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.delete("/items/{item_id}")
def remove_cart_item_endpoint(
    item_id: int,
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    if item_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="A valid cart item ID is required.",
        )

    try:
        cart = remove_item(
            db=db,
            user_id=user_id,
            cart_item_id=item_id,
        )
        db.commit()
        return _cart_response(cart)
    except (
        CartItemNotFoundError,
        CartServiceError,
        ValueError,
    ) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.delete("")
def clear_cart_endpoint(
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    try:
        cart = clear_cart(
            db=db,
            user_id=user_id,
        )
        db.commit()
        return _cart_response(cart)
    except (CartServiceError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
