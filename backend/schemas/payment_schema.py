"""
PaymentResponse will:

- Return the payment ID.
- Identify the associated order when applicable.
- Identify the associated booking when applicable.
- Return the transaction/reference ID when available.
- Return the payment method.
- Return the current payment status.
- Return the payment amount.
- Return timestamps.
- Avoid exposing unnecessary internal payment-provider data.

A payment belongs to exactly one of:

    order
    booking
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentResponse(BaseModel):
    """
    Schema returned by the API when retrieving payment information.

    Used by:

    - Checkout/order APIs
    - Booking/payment APIs
    - Payment-status APIs
    - Customer-support flows
    - AI backend tools
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # =========================================================
    # Payment
    # =========================================================

    # Payment database ID.
    id: int

    # =========================================================
    # Parent Transaction
    # =========================================================

    # Product-commerce transaction.
    #
    # None when this payment belongs to a Booking.

    order_id: int | None

    # Service-commerce transaction.
    #
    # None when this payment belongs to an Order.

    booking_id: int | None

    # =========================================================
    # Transaction Reference
    # =========================================================

    # Can be None while payment is still pending.

    transaction_id: str | None

    # =========================================================
    # Payment Information
    # =========================================================

    # Example:
    #
    #     UPI
    #     Card
    #     NetBanking
    #     Cash

    payment_method: str

    # Example:
    #
    #     pending
    #     success
    #     failed
    #     refunded

    payment_status: str

    # Payment amount.

    amount: float

    # =========================================================
    # Timestamps
    # =========================================================

    created_at: datetime
    updated_at: datetime