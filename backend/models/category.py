"""
The Category model will:
Store product categories.
Give each category a unique ID.
Store a category name and description.
Allow multiple products to belong to one category.
Support category-based product searches later.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Category(Base):
    """
    Represents a product category in BuyQK.
    """

    __tablename__ = "categories"

    # Unique identifier for the category
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Category name
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    # Optional category description
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    # Category creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship with products
    products = relationship(
        "Product",
        back_populates="category"
    )