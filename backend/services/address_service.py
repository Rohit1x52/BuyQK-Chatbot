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
    """Return all saved delivery addresses belonging to a user."""

    if user_id is None:
        raise ValueError("user_id is required.")

    return (
        db.query(Address)
        .filter(Address.user_id == user_id)
        .order_by(Address.id.asc())
        .all()
    )


# =========================================================
# Alias Used By AI Tool Layer
# =========================================================


def get_user_addresses(
    db: Session,
    user_id: int,
) -> list[Address]:
    """Compatibility wrapper used by the AI tool layer."""

    return get_saved_addresses(db=db, user_id=user_id)


# =========================================================
# Get Single Address
# =========================================================


def get_address(
    db: Session,
    address_id: int,
    user_id: int | None = None,
) -> Address | None:
    """Retrieve an address, optionally restricted to its owner."""

    if address_id is None:
        raise ValueError("address_id is required.")

    query = db.query(Address).filter(Address.id == address_id)

    if user_id is not None:
        query = query.filter(Address.user_id == user_id)

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
    address_line_2: str | None = None,
) -> Address:
    """Create and persist a complete delivery address."""

    if user_id is None:
        raise ValueError("user_id is required.")

    if not label or not label.strip():
        raise ValueError("Address label is required.")

    if not address or not address.strip():
        raise ValueError("Address is required.")

    # Address model columns are non-nullable, so service validation must
    # enforce the same contract before the database write.
    if not city or not city.strip():
        raise ValueError("City is required.")

    if not state or not state.strip():
        raise ValueError("State is required.")

    if not postal_code or not postal_code.strip():
        raise ValueError("Postal code is required.")

    new_address = Address(
        user_id=user_id,
        label=label.strip(),
        address=address.strip(),
        address_line_2=(
            address_line_2.strip()
            if address_line_2 and address_line_2.strip()
            else None
        ),
        city=city.strip(),
        state=state.strip(),
        postal_code=postal_code.strip(),
    )

    db.add(new_address)
    db.commit()
    db.refresh(new_address)

    return new_address


# =========================================================
# Delete Address
# =========================================================


def delete_address(
    db: Session,
    address_id: int,
    user_id: int,
) -> bool:
    """Delete a saved address belonging to the specified user."""

    address = get_address(
        db=db,
        address_id=address_id,
        user_id=user_id,
    )

    if address is None:
        return False

    db.delete(address)
    db.commit()

    return True
