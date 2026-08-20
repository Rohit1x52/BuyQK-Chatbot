"""
The Product model will:
Store product information.
Connect each product to a category.
Connect each product to a merchant.
Store price and stock.
Store brand information.
Store product description.
Store an image URL.
Track whether the product is currently available.
Allow the AI/tool layer to search products later.
Provide product information when creating order_items.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Product(Base):
    """
    Represents a product available on the BuyQK platform.
    """

    __tablename__ = "products"

    # Unique identifier for the product
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Merchant that sells this product
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Category to which this product belongs
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Product name
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )

    # Product description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Product brand
    brand: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    # Product price
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # Available stock
    stock: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # URL of product image
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    # Whether the product is currently available
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    # Product creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Product last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationship with Merchant
    merchant = relationship(
        "Merchant",
        back_populates="products"
    )

    # Relationship with Category
    category = relationship(
        "Category",
        back_populates="products"
    )

    # Relationship with OrderItem
    order_items = relationship(
        "OrderItem",
        back_populates="product"
    )

    ## relationship with cart items
    cart_items = relationship(
        "CartItem",
        back_populates="product",
    )