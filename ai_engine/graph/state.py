# =========================================================
# BuyQK AI - Graph State
# =========================================================
#
# Purpose:
# Central state shared by all nodes in the BuyQK LangGraph.
#
# The state contains:
#
#   - User input
#   - Conversation state
#   - AI understanding
#   - Checkout state
#   - Transaction state
#   - Resolved product
#   - Quantity
#   - Address/payment selection
#   - Tool execution
#   - Order state
#   - Authoritative billing state
#   - Final AI response
#   - Frontend metadata
#
# IMPORTANT:
#
# The AI may UNDERSTAND and EXPLAIN transaction information.
#
# The AI must NOT invent authoritative transactional values.
#
# Authoritative values such as:
#
#   - product_id
#   - product price
#   - stock
#   - quantity accepted by backend
#   - address ownership
#   - payment availability
#   - subtotal
#   - delivery charge
#   - tax
#   - discount
#   - final total
#   - order ID
#
# must come from backend/database/business logic.
#
# The graph state stores those values so that subsequent nodes
# can use the same authoritative information without repeatedly
# asking the LLM to reconstruct it.
#
# =========================================================


from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):

    # =====================================================
    # USER INPUT
    # =====================================================

    # Current user message.
    message: str

    # Conversation/session identifier.
    #
    # This identifies the conversation across HTTP requests.
    session_id: str

    # Authenticated/application-level user identifier.
    user_id: int

    # =====================================================
    # CHECKOUT / TRANSACTION IDENTITY
    # =====================================================
    #
    # checkout_id identifies ONE checkout transaction.
    #
    # IMPORTANT:
    #
    # checkout_id is NOT the order ID.
    #
    # checkout_id exists before an order is created.
    #
    # Example:
    #
    # checkout_id = "checkout-abc123"
    #
    # After successful order creation:
    #
    # checkout_id -> order_id
    #
    # This allows the system to distinguish:
    #
    #   "I am continuing the same checkout"
    #
    # from:
    #
    #   "I am starting a new order."
    #
    # This is important for idempotency and for preventing:
    #
    #   "Thank you"
    #
    # from creating another order.
    #
    # =====================================================

    checkout_id: str | None

    # =====================================================
    # CHECKOUT STATUS
    # =====================================================
    #
    # Represents the lifecycle of the current checkout.
    #
    # Typical lifecycle:
    #
    #   collecting
    #       ↓
    #   ready
    #       ↓
    #   creating
    #       ↓
    #   completed
    #
    # Possible terminal/error states may include:
    #
    #   failed
    #   cancelled
    #
    # The actual transition logic belongs to the decision/tool
    # layer, not to the LLM.
    #
    # =====================================================

    checkout_status: str | None

    # =====================================================
    # CHECKOUT SELECTION - FRONTEND AUTHORITATIVE
    # =====================================================

    # Selected saved address from the frontend.
    #
    # This should contain the database ID of the address.
    #
    # The backend must still verify that the address belongs
    # to the current user.
    selected_address_id: int | None

    # Selected payment method from the frontend.
    #
    # This is the user's selected value.
    #
    # It is NOT the authoritative source of which payment
    # methods are available.
    #
    # Available methods must come from backend/payment logic.
    selected_payment_method: str | None

    # Backward-compatible alias used by older nodes.
    #
    # Nodes should gradually migrate toward:
    #
    #     selected_payment_method
    #
    # but this field remains available so existing code does
    # not immediately break.
    payment_method: str | None

    # =====================================================
    # DATABASE
    # =====================================================

    # SQLAlchemy database session when required by the graph.
    db: Any

    # =====================================================
    # CONVERSATION
    # =====================================================

    # Previous conversation messages/context.
    #
    # This is conversational context, not authoritative
    # transaction data.
    conversation_history: list[dict[str, Any]]

    # =====================================================
    # AI UNDERSTANDING
    # =====================================================

    # Current semantic intent.
    #
    # Examples may include:
    #
    #   general
    #   product_search
    #   order_create
    #   order_tracking
    #   order_cancel
    #   customer_support
    #
    # The decision node must combine intent with transaction
    # state rather than blindly trusting the current LLM intent.
    intent: str

    # =====================================================
    # ACCUMULATED TRANSACTION ENTITIES
    # =====================================================
    #
    # This contains information accumulated from multiple
    # conversation turns.
    #
    # Example:
    #
    # {
    #     "product_id": 9,
    #     "product_name": "Maggi 2-Minute Noodles",
    #     "quantity": 3,
    #     "address_id": 1,
    #     "payment_method": "cod"
    # }
    #
    # IMPORTANT:
    #
    # This dictionary is NOT the only authoritative source.
    #
    # Once the backend resolves authoritative values, those
    # values should also be copied into their dedicated state
    # fields below.
    #
    # =====================================================

    entities: dict[str, Any]

    # Fields that are still required before checkout can
    # proceed.
    #
    # Examples:
    #
    #   ["quantity"]
    #   ["address_selection", "payment_method"]
    #
    missing_fields: list[str]

    # =====================================================
    # RESOLVED PRODUCT
    # =====================================================
    #
    # product_name:
    #     Natural-language/product reference understood from
    #     the conversation.
    #
    # product_id:
    #     Authoritative database product ID.
    #
    # Once product_id is resolved, order creation must use
    # product_id rather than repeatedly trusting product_name.
    #
    # =====================================================

    product_id: int | None

    product_name: str | None

    # =====================================================
    # CHECKOUT QUANTITY
    # =====================================================

    # Quantity requested/understood for the current checkout.
    #
    # The backend must validate the final quantity against
    # product availability/stock before creating the order.
    quantity: int | None

    # =====================================================
    # SELECTED ADDRESS
    # =====================================================

    # Authoritative database address ID selected for the
    # current checkout.
    address_id: int | None

    # =====================================================
    # SELECTED PAYMENT
    # =====================================================

    # Backend-normalized/accepted payment method.
    #
    # This can differ from the exact wording used by the user.
    #
    # Example:
    #
    # User:
    #     "cash on delivery"
    #
    # Backend-normalized value:
    #     "cod"
    #
    selected_payment_method: str | None

    # =====================================================
    # TOOL EXECUTION
    # =====================================================

    # Tool selected by the decision layer.
    tool_name: str | None

    # Raw authoritative result returned by the backend tool.
    #
    # This may contain:
    #
    #   - product information
    #   - search results
    #   - order information
    #   - billing information
    #   - tracking information
    #   - support information
    #   - validation errors
    #
    tool_result: Any

    # =====================================================
    # ORDER STATE
    # =====================================================

    # Backend-created order ID.
    #
    # This MUST come from the backend/database.
    #
    # The AI must never generate an order ID.
    order_id: int | None

    # Indicates that an order has successfully been created
    # for the current checkout.
    #
    # This is one of the safeguards against duplicate order
    # creation.
    #
    # Once True, create_order must not blindly create another
    # order for the same checkout_id.
    order_created: bool

    # True after an order has successfully been created and
    # the AI is waiting for the user to answer whether they
    # want to track the order.
    awaiting_order_tracking_confirmation: bool

    # =====================================================
    # BILLING
    # =====================================================
    #
    # Billing values are backend-authoritative.
    #
    # The AI can explain the bill but must never calculate
    # or invent these values independently.
    #
    # Example authoritative backend result:
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
    # No product, price, tax, discount, delivery fee or total
    # should be hardcoded in the AI layer.
    #
    # =====================================================

    # Primary authoritative billing object.
    #
    # This should be populated from the order service/tool.
    billing: dict[str, Any]

    # Backward-compatible alias.
    #
    # New code should prefer `billing`.
    #
    # If both exist, `billing` is considered the primary
    # authoritative object.
    bill: dict[str, Any]

    # Purchased line items returned by backend billing logic.
    billing_items: list[dict[str, Any]]

    # =====================================================
    # BILLING AMOUNTS
    # =====================================================
    #
    # These fields are convenience projections of the
    # authoritative billing object.
    #
    # They MUST be copied from backend results.
    #
    # The AI must never calculate these values.
    #
    # =====================================================

    subtotal: float | None

    delivery_charge: float | None

    discount: float | None

    tax: float | None

    total_amount: float | None

    # Currency returned by backend/business logic.
    currency: str | None

    # =====================================================
    # BILLING / PAYMENT SUMMARY
    # =====================================================

    # Payment method actually associated with the created
    # transaction/order.
    #
    # This may be backend-normalized.
    #
    # Example:
    #
    #     "cod"
    #
    billing_payment_method: str | None

    # =====================================================
    # TRANSACTION / IDEMPOTENCY INFORMATION
    # =====================================================
    #
    # These fields allow the graph/tool layer to distinguish
    # a new transaction from a repeated request.
    #
    # IMPORTANT:
    #
    # These fields do NOT replace database-level uniqueness or
    # transactional protection.
    #
    # The backend/order service remains responsible for the
    # final idempotency guarantee.
    #
    # =====================================================

    # Indicates whether an order creation attempt has already
    # been made for the current checkout.
    order_creation_attempted: bool

    # Indicates that the current checkout has reached a
    # terminal state and should not create another order.
    #
    # This is different from `order_created` because a checkout
    # may also become terminal due to cancellation/failure.
    checkout_completed: bool

    # Optional structured transaction error.
    #
    # Example:
    #
    # {
    #     "code": "OUT_OF_STOCK",
    #     "message": "...",
    #     "retryable": True
    # }
    #
    # The AI may explain this to the user, but should not
    # invent the error information.
    transaction_error: dict[str, Any] | None

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    # Final natural-language response generated for the user.
    #
    # The response node may use authoritative backend data
    # stored in:
    #
    #   billing
    #   order_id
    #   tool_result
    #
    # but must not invent transactional values.
    response: str

    # =====================================================
    # FRONTEND / GRAPH METADATA
    # =====================================================
    #
    # Metadata is used to communicate structured UI state.
    #
    # Examples:
    #
    # {
    #     "type": "address_selection",
    #     "addresses": [...]
    # }
    #
    # {
    #     "type": "payment_selection",
    #     "methods": [...]
    # }
    #
    # {
    #     "type": "order_success",
    #     "order_id": 1,
    #     "bill": {...},
    #     "can_track": True
    # }
    #
    # Metadata must be generated from actual graph/backend
    # state and should not contain fabricated transaction data.
    #
    # =====================================================

    metadata: dict[str, Any]