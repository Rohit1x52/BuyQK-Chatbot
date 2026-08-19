# =========================================================
# BuyQK AI - Graph State
# =========================================================
#
# Purpose:
# Central state shared by all nodes in the BuyQK LangGraph.
#
# Architecture:
#
# User Message
#       ↓
# Context
#       ↓
# Entity Understanding
#       ↓
# Planner
#       ↓
# Policy
#       ↓
# Tool
#       ↓
# Backend Service
#       ↓
# Authoritative State
#       ↓
# Response
#
# The graph state contains conversational information and
# backend-authoritative snapshots.
#
# IMPORTANT:
#
# AI is responsible for:
#   - understanding language
#   - understanding intent
#   - resolving conversational references
#   - identifying user goals
#   - proposing actions
#   - selecting capabilities/tools
#   - generating responses
#
# Backend/business logic is responsible for:
#   - product identity
#   - product price
#   - stock
#   - quantity validation
#   - cart persistence
#   - cart calculations
#   - address validation
#   - payment validation
#   - authorization
#   - order creation
#   - order ID
#   - billing
#   - taxes
#   - discounts
#   - delivery charges
#   - final totals
#   - cancellation/refund eligibility
#   - transaction status
#   - idempotency
#
# The AI must NEVER invent authoritative transactional values.
#
# =========================================================


from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):

    # =========================================================
    # USER INPUT
    # =========================================================

    # Current raw user message.
    message: str

    # Conversation/session identifier.
    session_id: str

    # Authenticated application user ID.
    user_id: int

    # =========================================================
    # CONTEXT LOADER
    # =========================================================

    # Context assembled for the AI.
    #
    # This may contain:
    #   - current message
    #   - conversation history
    #   - checkout state
    #   - cart state
    #   - order state
    #   - product references
    #   - backend results
    #
    # Context is informational.
    # It does not replace backend authority.
    context: dict[str, Any]

    # =========================================================
    # CONVERSATION HISTORY
    # =========================================================

    conversation_history: list[dict[str, Any]]

    # =========================================================
    # AI UNDERSTANDING
    # =========================================================

    # Semantic intent understood from the conversation.
    #
    # Examples:
    #
    #   general
    #   product_search
    #   cart
    #   order_create
    #   order_tracking
    #   order_cancel
    #   customer_support
    #   order_modify
    #
    intent: str

    # User's underlying conversational goal.
    user_goal: str | None

    # Detected language.
    #
    # Examples:
    #   en
    #   hi
    #   hinglish
    detected_language: str | None

    # Conversational references resolved by AI.
    references: dict[str, Any]

    # =========================================================
    # ACCUMULATED ENTITIES
    # =========================================================

    # Semantic information accumulated across turns.
    #
    # Example:
    #
    # {
    #     "product_id": 9,
    #     "product_name": "Maggi",
    #     "quantity": 3,
    # }
    #
    # These values are not automatically authoritative.
    entities: dict[str, Any]

    # Information currently missing from the conversation
    # or current transaction.
    missing_fields: list[str]

    # =========================================================
    # AI PLANNER
    # =========================================================

    # Planner proposal.
    #
    # Example:
    #
    # {
    #     "action": "ADD_CART_ITEM",
    #     "tool": "add_cart_item",
    #     "arguments": {
    #         "product_id": 10,
    #         "quantity": 2
    #     },
    #     "confidence": 0.97
    # }
    #
    # This is only a proposal.
    planner_decision: dict[str, Any]

    # Proposed capability/action.
    #
    # Existing Phase 2 actions:
    #
    #   SEARCH_PRODUCT
    #   START_CHECKOUT
    #   CONTINUE_CHECKOUT
    #   SELECT_ADDRESS
    #   SELECT_PAYMENT
    #   CREATE_ORDER
    #   TRACK_ORDER
    #   CANCEL_ORDER
    #   MODIFY_ORDER
    #   SUPPORT
    #   ANSWER
    #   ASK_CLARIFICATION
    #   CONFIRM
    #   END_CONVERSATION
    #
    # Phase 3 cart actions:
    #
    #   ADD_CART_ITEM
    #   REMOVE_CART_ITEM
    #   UPDATE_CART_ITEM
    #   CLEAR_CART
    #   SHOW_CART
    #   CHECKOUT_CART
    #
    planned_action: str | None

    # Proposed tool.
    planned_tool: str | None

    # Arguments proposed by planner.
    planned_arguments: dict[str, Any]

    # Informational planner confidence.
    #
    # This must never override backend validation.
    planner_confidence: float | None

    # =========================================================
    # POLICY / VALIDATION
    # =========================================================

    # Result of policy validation.
    policy_result: dict[str, Any]

    # Structured policy error.
    policy_error: dict[str, Any] | None

    # =========================================================
    # CART STATE - PHASE 3
    # =========================================================
    #
    # The cart is now a first-class state in the conversation.
    #
    # IMPORTANT:
    #
    # These fields represent the latest backend-authoritative
    # cart snapshot.
    #
    # The graph MUST NOT directly mutate the database.
    #
    # Cart mutations happen through:
    #
    #     planner
    #        ↓
    #     policy
    #        ↓
    #     tool
    #        ↓
    #     cart_service
    #        ↓
    #     database
    #
    # The resulting backend state is then written back into
    # these GraphState fields.
    #
    # =========================================================

    # Persistent cart identifier.
    #
    # This is NOT an order ID.
    cart_id: int | None

    # Current cart lifecycle status.
    #
    # Typical values:
    #
    #   active
    #   empty
    #   checked_out
    #   abandoned
    #
    # Exact values are controlled by backend services.
    cart_status: str | None

    # Current backend-authoritative cart items.
    #
    # Example:
    #
    # [
    #     {
    #         "id": 1,
    #         "product_id": 10,
    #         "product_name": "Maggi",
    #         "quantity": 3,
    #         "unit_price": 15,
    #         "line_total": 45
    #     },
    #     {
    #         "id": 2,
    #         "product_id": 20,
    #         "product_name": "Biscuits",
    #         "quantity": 2,
    #         "unit_price": 20,
    #         "line_total": 40
    #     }
    # ]
    #
    # Values such as price and stock must come from backend
    # services, not from the LLM.
    cart_items: list[dict[str, Any]]

    # Backend-authoritative cart calculation.
    #
    # Example:
    #
    # {
    #     "subtotal": 85,
    #     "delivery_charge": 0,
    #     "discount": 0,
    #     "tax": 0,
    #     "total": 85,
    #     "currency": "INR"
    # }
    #
    # The AI may explain this data but must not calculate or
    # override it.
    cart_summary: dict[str, Any] | None

    # Requested cart operation.
    #
    # Examples:
    #
    #   add_item
    #   remove_item
    #   update_quantity
    #   clear_cart
    #   show_cart
    #   checkout
    #
    # This is a semantic/action classification.
    # It is not itself a database mutation.
    cart_action: str | None

    # Authoritative result returned by Cart Service.
    #
    # Example:
    #
    # {
    #     "success": True,
    #     "cart_id": 1,
    #     "items": [...],
    #     "summary": {...}
    # }
    #
    # Or:
    #
    # {
    #     "success": False,
    #     "error": {...}
    # }
    cart_result: dict[str, Any] | None

    # Whether the backend says the current cart is ready
    # for checkout.
    #
    # This must be determined by backend validation.
    cart_checkout_ready: bool

    # =========================================================
    # CHECKOUT / TRANSACTION IDENTITY
    # =========================================================

    # Unique checkout transaction identifier.
    #
    # checkout_id is NOT the cart ID.
    # checkout_id is NOT the order ID.
    checkout_id: str | None

    # =========================================================
    # CHECKOUT STATUS
    # =========================================================

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
    # Other possible states:
    #
    #   failed
    #   cancelled
    checkout_status: str | None

    # =========================================================
    # CHECKOUT SELECTION - FRONTEND INPUT
    # =========================================================

    # Address selected by frontend/user.
    #
    # Backend must verify ownership and validity.
    selected_address_id: int | None

    # Payment method selected by frontend/user.
    #
    # Backend must verify availability and validity.
    selected_payment_method: str | None

    # Backward-compatible alias.
    payment_method: str | None

    # =========================================================
    # DATABASE
    # =========================================================

    # SQLAlchemy session.
    #
    # Infrastructure state only.
    # Never expose this to the LLM.
    db: Any

    # =========================================================
    # PRODUCT RESOLUTION
    # =========================================================

    # Natural-language product reference.
    product_name: str | None

    # Authoritative product ID.
    product_id: int | None

    # =========================================================
    # QUANTITY
    # =========================================================

    # Quantity understood/requested for the current operation.
    #
    # Backend validates final quantity against stock.
    quantity: int | None

    # =========================================================
    # SELECTED ADDRESS
    # =========================================================

    # Authoritative address ID used by checkout.
    address_id: int | None

    # =========================================================
    # SELECTED PAYMENT
    # =========================================================

    # Backend-normalized payment method.
    selected_payment_method_normalized: str | None

    # =========================================================
    # TOOL EXECUTION
    # =========================================================

    # Actual tool selected after policy validation.
    tool_name: str | None

    # Authoritative result returned by backend/tool.
    #
    # May contain:
    #   - products
    #   - cart
    #   - order
    #   - billing
    #   - tracking
    #   - support
    #   - validation errors
    tool_result: Any

    # =========================================================
    # ORDER STATE
    # =========================================================

    # Backend-created order ID.
    #
    # NEVER generated by AI.
    order_id: int | None

    # Whether an order has successfully been created.
    order_created: bool

    # Whether order creation has already been attempted.
    order_creation_attempted: bool

    # Whether checkout reached a terminal state.
    checkout_completed: bool

    # Whether the AI is waiting for tracking confirmation.
    awaiting_order_tracking_confirmation: bool

    # =========================================================
    # TRANSACTION ERROR
    # =========================================================

    # Structured backend transaction error.
    transaction_error: dict[str, Any] | None

    # =========================================================
    # BILLING
    # =========================================================

    # Primary authoritative billing object.
    #
    # Example:
    #
    # {
    #     "items": [
    #         {
    #             "product_id": 9,
    #             "product_name": "Maggi",
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
    billing: dict[str, Any]

    # Backward-compatible billing alias.
    bill: dict[str, Any]

    # Backend-returned billing items.
    billing_items: list[dict[str, Any]]

    # =========================================================
    # BILLING AMOUNTS
    # =========================================================

    # Convenience projections of backend billing.
    subtotal: float | None
    delivery_charge: float | None
    discount: float | None
    tax: float | None
    total_amount: float | None

    # Backend-returned currency.
    currency: str | None

    # Backend-normalized payment method associated with order.
    billing_payment_method: str | None

    # =========================================================
    # FINAL RESPONSE
    # =========================================================

    # Final natural-language response.
    response: str

    # =========================================================
    # FRONTEND / GRAPH METADATA
    # =========================================================

    # Structured metadata consumed by frontend.
    #
    # Examples:
    #
    #   cart
    #   cart_updated
    #   cart_empty
    #   checkout
    #   address_selection
    #   payment_selection
    #   product_search
    #   order_success
    #   tracking
    #   error
    #
    # Metadata must come from actual graph/backend state.
    metadata: dict[str, Any]