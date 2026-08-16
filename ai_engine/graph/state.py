# =========================================================
# BuyQK AI - Graph State
# =========================================================
#
# Purpose:
# Central state shared by all nodes in the BuyQK LangGraph.
#
# The state contains:
#
#   User input
#   Conversation state
#   AI understanding
#   Checkout state
#   Resolved product
#   Address/payment selection
#   Tool execution
#   Order state
#   Billing state
#   Final AI response
#   Frontend metadata
#
# IMPORTANT:
#
# AI may UNDERSTAND and EXPLAIN billing information.
#
# Transactional billing values must come from the backend/order
# service/database. The AI must never invent:
#
#   - product price
#   - quantity
#   - subtotal
#   - delivery charge
#   - tax
#   - discount
#   - final total
#   - order ID
#
# The backend calculates authoritative values.
# The AI interprets/presents those values.
#
# =========================================================


from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):

    # =====================================================
    # User Input
    # =====================================================

    message: str

    session_id: str

    user_id: int

    # =====================================================
    # Checkout Selection - Frontend Authoritative
    # =====================================================

    # Selected saved address from frontend.
    #
    # This should contain the database ID of the address.
    selected_address_id: int | None

    # Selected payment method from frontend.
    #
    # IMPORTANT:
    # Do not use this field as the source of truth for the
    # available payment methods.
    #
    # The actual available methods should come from the
    # backend/payment system.
    selected_payment_method: str | None

    # Backward-compatible alias used by older nodes.
    payment_method: str | None

    # =====================================================
    # Database
    # =====================================================

    db: Any

    # =====================================================
    # Conversation
    # =====================================================

    conversation_history: list[dict[str, Any]]

    # =====================================================
    # AI Understanding
    # =====================================================

    intent: str

    # =====================================================
    # Accumulated Transaction Entities
    # =====================================================
    #
    # This dictionary contains the accumulated information
    # understood from the conversation.
    #
    # Example:
    #
    # {
    #     "product_id": 1,
    #     "product_name": "Amul Milk",
    #     "quantity": 3,
    #     "address_id": 5,
    #     "payment_method": "cod"
    # }
    #
    # Additional AI/backend information may be stored here
    # without requiring the graph state schema to change.
    #
    # =====================================================

    entities: dict[str, Any]

    missing_fields: list[str]

    # =====================================================
    # RESOLVED PRODUCT
    # =====================================================
    #
    # product_name:
    #     Natural-language/product value understood by AI.
    #
    # product_id:
    #     Authoritative database product ID.
    #
    # Once product_id has been resolved, the order workflow
    # should use product_id rather than repeatedly searching
    # by product_name.
    #
    # =====================================================

    product_id: int | None

    product_name: str | None

    # =====================================================
    # Checkout Quantity
    # =====================================================

    quantity: int | None

    # =====================================================
    # Selected Address
    # =====================================================

    address_id: int | None

    # =====================================================
    # Selected Payment
    # =====================================================

    # Explicitly selected payment method.
    selected_payment_method: str | None

    # =====================================================
    # Tool Execution
    # =====================================================

    tool_name: str | None

    # Raw authoritative result returned by the backend tool.
    #
    # This may contain:
    #
    #   product information
    #   order information
    #   billing information
    #   tracking information
    #   support information
    #   errors
    #
    tool_result: Any

    # =====================================================
    # ORDER STATE
    # =====================================================

    # Created order ID.
    order_id: int | None

    # True after an order has successfully been created and
    # the AI is waiting for the user to answer whether they
    # want to track the order.
    awaiting_order_tracking_confirmation: bool

    # =====================================================
    # BILLING
    # =====================================================
    #
    # Billing is deliberately represented as dynamic data.
    #
    # Do NOT hardcode:
    #
    #   product names
    #   unit prices
    #   delivery fees
    #   taxes
    #   discounts
    #   payment methods
    #   totals
    #
    # The order service/tool should populate these values from
    # the authoritative database/business logic.
    #
    # Example backend result:
    #
    # {
    #     "items": [
    #         {
    #             "product_id": 9,
    #             "product_name": "Maggi 2-Minute Noodles",
    #             "quantity": 3,
    #             "unit_price": 15,
    #             "line_total": 45
    #         }
    #     ],
    #     "subtotal": 45,
    #     "delivery_charge": 0,
    #     "discount": 0,
    #     "tax": 0,
    #     "total": 45,
    #     "currency": "INR"
    # }
    #
    # The schema intentionally uses Any/dynamic structures so
    # the AI can understand different billing structures
    # without hardcoding individual products or charges.
    #
    # =====================================================

    # Complete authoritative bill returned by the backend.
    #
    # This is the primary billing object consumed by the
    # response node / AI.
    billing: dict[str, Any]

    # Backward/alternate naming for systems that refer to the
    # bill rather than billing.
    bill: dict[str, Any]

    # Individual purchased items.
    #
    # Each item can dynamically contain:
    #
    #   product_id
    #   product_name
    #   quantity
    #   unit_price
    #   line_total
    #
    # and any future pricing information.
    billing_items: list[dict[str, Any]]

    # =====================================================
    # Billing Amounts
    # =====================================================
    #
    # These are optional because not every tool result needs
    # to contain every monetary component.
    #
    # They must be populated from backend/business logic.
    # They must NOT be guessed by the AI.
    #
    # =====================================================

    subtotal: float | None

    delivery_charge: float | None

    discount: float | None

    tax: float | None

    total_amount: float | None

    # Currency returned by the backend.
    #
    # No currency should be assumed by the AI when this field
    # is available.
    currency: str | None

    # =====================================================
    # Payment/Billing Summary
    # =====================================================

    # Payment method actually associated with the order.
    #
    # This may be different from the user's initial selection
    # if the backend normalizes the value.
    billing_payment_method: str | None

    # =====================================================
    # Final Response
    # =====================================================

    response: str

    # =====================================================
    # Metadata
    # =====================================================
    #
    # Used by the frontend and other graph layers.
    #
    # Examples:
    #
    #   {
    #       "type": "order_success",
    #       "order_id": 1,
    #       "bill": {...},
    #       "can_track": True
    #   }
    #
    # =====================================================

    metadata: dict[str, Any]