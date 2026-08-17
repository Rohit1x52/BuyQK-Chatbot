"""
ProductResponse will:
Return product information from the backend.
Include the product's merchant and category IDs.
Provide price and stock information.
Tell the frontend whether the product is available.
Provide the product image URL.
Support product-search results used by the AI/tool layer.
Prevent database-specific fields from leaking into the API response.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    """
    Schema returned when a product is retrieved from BuyQK.

    Used by:
    - Product search APIs
    - AI/backend tools
    - Frontend product cards
    - Order/product selection flows
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Product database ID
    id: int

    # Merchant selling the product
    merchant_id: int

    # Product category
    category_id: int

    # Product information
    name: str
    description: str | None
    brand: str | None

    # Pricing and inventory
    price: float
    stock: int

    # Product image
    image_url: str | None

    # Availability
    is_available: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime