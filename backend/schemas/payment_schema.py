"""
PaymentResponse will:
Return the payment ID.
Identify the associated order.
Return the transaction/reference ID when available.
Return the payment method.
Return the current payment status.
Return the payment amount.
Return timestamps.
Avoid exposing unnecessary internal payment-provider data.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentResponse(BaseModel):
    """
    Schema returned by the API when retrieving payment information.

    Used by:
    - Checkout/order APIs
    - Payment-status APIs
    - Customer-support flows
    - AI backend tools
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    # Payment database ID
    id: int

    # Order associated with the payment
    order_id: int

    # Transaction/reference ID
    # Can be None while payment is still pending.
    transaction_id: str | None

    # Payment method
    # Example: UPI, Card, NetBanking, Cash
    payment_method: str

    # Current payment status
    # Example: pending, success, failed, refunded
    payment_status: str

    # Payment amount
    amount: float

    # Payment timestamps
    created_at: datetime
    updated_at: datetime