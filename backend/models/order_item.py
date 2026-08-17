"""
The OrderItem model will:
Connect an item to an Order.
Connect an item to a Product.
Store the quantity purchased.
Store the product's price at the time of purchase.
Store the total price for that line item.
Allow one order to contain multiple products.
Preserve the historical purchase price even if the product's current price changes later.
"""

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class OrderItem(Base):
    """
    Represents one product line inside a BuyQK order.

    Example:

        Order #101
            ├── Amul Milk × 2
            ├── Bread × 1
            └── Eggs × 12
    """

    __tablename__ = "order_items"

    # Unique identifier for the order item
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Order to which this item belongs
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Product purchased
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Number of units purchased
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Price of one unit at the time of purchase
    unit_price: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # Total price for this line item
    total_price: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # Relationship with Order
    order = relationship(
        "Order",
        back_populates="items"
    )

    # Relationship with Product
    product = relationship(
        "Product",
        back_populates="order_items"
    )