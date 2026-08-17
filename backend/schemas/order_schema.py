"""
order_schema.py will:
Validate order creation requests.
Associate an order with a delivery address.
Accept the products being ordered.
Validate quantities.
Return order status.
Return payment status.
Return total amount.
Return the order's items.
Support order tracking later.
Keep database models separate from API contracts.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    """
    Schema used when adding a product to a new order.
    """

    # Product being ordered
    product_id: int = Field(
        ...,
        gt=0
    )

    # Number of units requested
    quantity: int = Field(
        ...,
        gt=0
    )


class OrderCreate(BaseModel):
    """
    Schema used when creating a new customer order.
    """

    # Delivery address selected by the customer
    address_id: int = Field(
        ...,
        gt=0
    )

    # Products/items included in the order
    items: list[OrderItemCreate] = Field(
        ...,
        min_length=1
    )


class OrderItemResponse(BaseModel):
    """
    Schema returned for an individual order item.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Order item ID
    id: int

    # Product associated with this item
    product_id: int

    # Quantity purchased
    quantity: int

    # Product price at the time of purchase
    unit_price: float

    # Total price for this item
    total_price: float


class OrderResponse(BaseModel):
    """
    Schema returned when retrieving an order.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Order ID
    id: int

    # Customer who placed the order
    user_id: int

    # Delivery address
    address_id: int

    # Assigned delivery rider
    rider_id: int | None

    # Current order status
    status: str

    # Total order amount
    total_amount: float

    # Current payment status
    payment_status: str

    # Products contained in the order
    items: list[OrderItemResponse]

    # Timestamps
    created_at: datetime
    updated_at: datetime