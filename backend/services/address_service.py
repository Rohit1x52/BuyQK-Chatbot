# Purpose:
# Backend service for BuyQK delivery addresses.
#
# Responsibilities:
# - Retrieve saved addresses for a user
# - Create a new delivery address
# - Retrieve a single address
# - Validate address ownership
#
# This service contains database/business access logic.
# AI nodes should NOT query the Address model directly.


from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.address import Address


# =========================================================
# Get Saved Addresses
# =========================================================

def get_saved_addresses(
    db: Session,
    user_id: int,
) -> list[Address]:
    """
    Return all saved delivery addresses belonging to a user.
    """

    if user_id is None:
        raise ValueError(
            "user_id is required."
        )

    return (
        db.query(Address)
        .filter(
            Address.user_id == user_id
        )
        .order_by(
            Address.id.asc()
        )
        .all()
    )


# =========================================================
# Alias Used By AI Tool Layer
# =========================================================

def get_user_addresses(
    db: Session,
    user_id: int,
) -> list[Address]:
    """
    Compatibility wrapper used by the AI tool layer.

    The canonical implementation is get_saved_addresses().
    """

    return get_saved_addresses(
        db=db,
        user_id=user_id,
    )


# =========================================================
# Get Single Address
# =========================================================

def get_address(
    db: Session,
    address_id: int,
    user_id: int | None = None,
) -> Address | None:
    """
    Retrieve an address by ID.

    If user_id is supplied, the address must belong to that
    user. This prevents one user from using another user's
    saved address.
    """

    if address_id is None:
        raise ValueError(
            "address_id is required."
        )

    query = (
        db.query(Address)
        .filter(
            Address.id == address_id
        )
    )

    if user_id is not None:

        query = query.filter(
            Address.user_id == user_id
        )

    return query.first()


# =========================================================
# Create Address
# =========================================================

def create_address(
    db: Session,
    user_id: int,
    label: str,
    address: str,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
) -> Address:
    """
    Create and persist a new delivery address.
    """

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if user_id is None:

        raise ValueError(
            "user_id is required."
        )

    if not label or not label.strip():

        raise ValueError(
            "Address label is required."
        )

    if not address or not address.strip():

        raise ValueError(
            "Address is required."
        )

    # -----------------------------------------------------
    # Create Address
    # -----------------------------------------------------

    new_address = Address(
        user_id=user_id,
        label=label.strip(),
        address=address.strip(),
        city=(
            city.strip()
            if city
            else None
        ),
        state=(
            state.strip()
            if state
            else None
        ),
        postal_code=(
            postal_code.strip()
            if postal_code
            else None
        ),
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    db.add(
        new_address
    )

    db.commit()

    db.refresh(
        new_address
    )

    return new_address


# =========================================================
# Delete Address
# =========================================================

def delete_address(
    db: Session,
    address_id: int,
    user_id: int,
) -> bool:
    """
    Delete a saved address belonging to the specified user.

    Returns:
        True if deleted.
        False if the address does not exist or does not
        belong to the user.
    """

    address = get_address(
        db=db,
        address_id=address_id,
        user_id=user_id,
    )

    if address is None:

        return False

    db.delete(
        address
    )

    db.commit()

    return True