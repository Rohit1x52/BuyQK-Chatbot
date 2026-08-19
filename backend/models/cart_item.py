from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from backend.database.base import Base


class CartItem(Base):
    """
    Represents one product line inside a BuyQK shopping cart.

    Unlike OrderItem, CartItem does NOT store a historical price.

    The current product price, stock, availability, name, etc.
    remain authoritative in the Product model.

    Example:

        Cart
            ├── Maggi × 3
            ├── Biscuits × 2
            └── Milk × 1
    """

    __tablename__ = "cart_items"

    # =========================================================
    # Primary Key
    # =========================================================

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # =========================================================
    # Cart
    # =========================================================

    # Cart containing this item.
    cart_id: Mapped[int] = mapped_column(
        ForeignKey(
            "carts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Product
    # =========================================================

    # Product currently represented by this cart item.
    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Quantity
    # =========================================================

    # Current quantity requested by the customer.
    #
    # Stock availability must be validated by the backend
    # cart service before increasing or updating this value.
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # =========================================================
    # Timestamps
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # =========================================================
    # Relationships
    # =========================================================

    # Parent cart.
    cart = relationship(
        "Cart",
        back_populates="items",
    )

    # Current product information.
    product = relationship(
        "Product",
        back_populates="cart_items",
    )