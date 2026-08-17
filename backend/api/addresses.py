from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from backend.database.dependencies import get_db

from backend.services.address_service import (
    get_saved_addresses,
    create_address,
)


router = APIRouter(
    prefix="/addresses",
    tags=["addresses"],
)


# =========================================================
# Schemas
# =========================================================

class AddressCreateRequest(BaseModel):

    user_id: int

    label: str = Field(
        default="Home",
        min_length=1,
        max_length=50,
    )

    address: str = Field(
        min_length=1,
        max_length=500,
    )

    city: str | None = None

    state: str | None = None

    postal_code: str | None = None


# =========================================================
# GET /addresses
# =========================================================

@router.get("")
def list_addresses(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Return saved addresses for the current user.
    """

    return {
        "success": True,
        "addresses": get_saved_addresses(
            db=db,
            user_id=user_id,
        ),
    }


# =========================================================
# POST /addresses
# =========================================================

@router.post("")
def add_address(
    request: AddressCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new saved address.
    """

    address = create_address(
        db=db,
        user_id=request.user_id,
        label=request.label,
        address=request.address,
        city=request.city,
        state=request.state,
        postal_code=request.postal_code,
    )

    return {
        "success": True,
        "address": address,
    }