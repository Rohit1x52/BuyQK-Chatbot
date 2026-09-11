"""
Purpose:
Contains business logic for BuyQK medicine and pharmacy operations.

Responsibilities:
- Search medicines
- Retrieve a medicine by ID
- Search pharmacy merchants
- Check whether a medicine requires a prescription

Medicine is represented using the existing Product model.

Pharmacy is represented using the existing Merchant model
with category="pharmacy".

Prescription requirement is stored as Product metadata.

Actual prescription verification is a separate transaction/workflow
concern and is intentionally not implemented here.
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.models.merchant import Merchant
from backend.models.product import Product


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

PHARMACY_CATEGORY = "pharmacy"


# ---------------------------------------------------------
# Search Medicines
# ---------------------------------------------------------

def search_medicines(
    db: Session,
    query: str,
    limit: int = 10,
    prescription_required: bool | None = None,
) -> list[Product]:
    """
    Search products sold by pharmacy merchants.

    Existing Product fields are used for the search:

        name
        brand
        description
        model_number

    Optional structured filtering:

        prescription_required

    Args:
        db:
            Active SQLAlchemy database session.

        query:
            Medicine search text.

        limit:
            Maximum number of medicines to return.

        prescription_required:
            Optional prescription requirement filter.

    Returns:
        List of matching pharmacy Product objects.
    """

    query = query.strip()

    if not query:
        return []

    search_pattern = f"%{query}%"

    filters = [
        Product.is_available.is_(True),
        func.lower(Merchant.category) == PHARMACY_CATEGORY,
        or_(
            Product.name.ilike(search_pattern),
            Product.brand.ilike(search_pattern),
            Product.description.ilike(search_pattern),
            Product.model_number.ilike(search_pattern),
        ),
    ]

    if prescription_required is not None:
        filters.append(
            Product.prescription_required.is_(
                prescription_required
            )
        )

    medicines = (
        db.query(Product)
        .join(
            Merchant,
            Product.merchant_id == Merchant.id,
        )
        .filter(*filters)
        .limit(limit)
        .all()
    )

    return medicines


# ---------------------------------------------------------
# Get Medicine
# ---------------------------------------------------------

def get_medicine(
    db: Session,
    product_id: int,
) -> Product | None:
    """
    Retrieve a product only if it belongs to a pharmacy.

    Args:
        db:
            Active SQLAlchemy database session.

        product_id:
            Product database ID.

    Returns:
        Pharmacy Product object if found, otherwise None.
    """

    return (
        db.query(Product)
        .join(
            Merchant,
            Product.merchant_id == Merchant.id,
        )
        .filter(
            Product.id == product_id,
            func.lower(Merchant.category)
            == PHARMACY_CATEGORY,
        )
        .first()
    )


# ---------------------------------------------------------
# Search Pharmacies
# ---------------------------------------------------------

def search_pharmacies(
    db: Session,
    query: str | None = None,
    limit: int = 10,
) -> list[Merchant]:
    """
    Search pharmacy merchants.

    Args:
        db:
            Active SQLAlchemy database session.

        query:
            Optional pharmacy/business-name search.

        limit:
            Maximum number of pharmacies to return.

    Returns:
        List of matching pharmacy Merchant objects.
    """

    filters = [
        func.lower(Merchant.category)
        == PHARMACY_CATEGORY
    ]

    if query is not None:
        query = query.strip()

        if query:
            search_pattern = f"%{query}%"

            filters.append(
                Merchant.business_name.ilike(
                    search_pattern
                )
            )

    pharmacies = (
        db.query(Merchant)
        .filter(*filters)
        .limit(limit)
        .all()
    )

    return pharmacies


# ---------------------------------------------------------
# Prescription Requirement
# ---------------------------------------------------------

def check_prescription_requirement(
    db: Session,
    product_id: int,
) -> bool | None:
    """
    Determine whether a pharmacy product requires
    a prescription.

    Args:
        db:
            Active SQLAlchemy database session.

        product_id:
            Product database ID.

    Returns:
        True:
            Prescription is required.

        False:
            Prescription is not required.

        None:
            Product does not exist or is not a pharmacy product.
    """

    medicine = get_medicine(
        db=db,
        product_id=product_id,
    )

    if medicine is None:
        return None

    return bool(
        medicine.prescription_required
    )