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
Store an optional model number for products such as electronics.
Store flexible product specifications.
Store whether a product requires a prescription.
Allow the AI/tool layer to search products later.
Provide product information when creating order_items.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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

    The Product model is intentionally generic so that the same
    product infrastructure can support multiple commerce verticals
    such as grocery, pharmacy, electronics, and future categories.
    """

    __tablename__ = "products"

    # =========================================================
    # Primary Key
    # =========================================================

    # Unique identifier for the product
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # =========================================================
    # Merchant
    # =========================================================

    # Merchant that sells this product
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # =========================================================
    # Category
    # =========================================================

    # Category to which this product belongs
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # =========================================================
    # Basic Product Information
    # =========================================================

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

    # =========================================================
    # Electronics / Product Identification
    # =========================================================

    # Optional model number.
    #
    # Useful for electronics and other products where a
    # manufacturer model number is an important identifier.
    model_number: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True
    )

    # Flexible product-specific specifications.
    #
    # Examples:
    #
    # Electronics:
    # {
    #     "ram": "8GB",
    #     "storage": "256GB",
    #     "display": "6.5 inch"
    # }
    #
    # Other product categories can use their own specification
    # keys without requiring a new database column for each one.
    specifications: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # =========================================================
    # Medicine / Pharmacy
    # =========================================================

    # Indicates whether the product requires a prescription.
    #
    # This is catalog metadata about the product.
    # Actual prescription verification/status belongs to the
    # transaction/user workflow and should not be stored here.
    prescription_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    # =========================================================
    # Pricing and Inventory
    # =========================================================

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

    # =========================================================
    # Media
    # =========================================================

    # URL of product image
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    # =========================================================
    # Availability
    # =========================================================

    # Whether the product is currently available
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    # =========================================================
    # Timestamps
    # =========================================================

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

    # =========================================================
    # Relationships
    # =========================================================

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

    # Relationship with CartItem
    cart_items = relationship(
        "CartItem",
        back_populates="product",
    )