# =========================================================
# BuyQK AI - Graph State
# =========================================================
#
# Purpose:
# Central state shared by all nodes in the BuyQK LangGraph.
#
#   - Conversation state
#   - Checkout state
#   - Transaction state
#   - Product resolution
#   - Address/payment selection
#   - Tool execution
#   - Order state
#   - Authoritative billing
#   - Context Loader state
#   - AI understanding
#   - AI planning
#   - Policy validation
#   - Tool planning
#
# IMPORTANT ARCHITECTURAL RULE
#
# AI is responsible for:
#
#   - understanding language
#   - understanding user intent
#   - resolving conversational references
#   - understanding user goals
#   - identifying missing conversational information
#   - proposing the next conversational/action step
#   - selecting an appropriate capability/tool
#   - generating natural-language responses
#
# Backend/business logic is responsible for:
#
#   - product identity
#   - product price
#   - stock
#   - accepted quantity
#   - address ownership
#   - payment availability/validity
#   - authorization
#   - order creation
#   - order ID
#   - billing
#   - taxes
#   - discounts
#   - delivery charges
#   - final totals
#   - cancellation eligibility
#   - refund eligibility
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

    # =====================================================
    # USER INPUT
    # =====================================================

    # Current raw user message.
    message: str

    # Conversation/session identifier.
    session_id: str

    # Application-level authenticated user identifier.
    user_id: int

    # =====================================================
    # PHASE 2 - CONTEXT LOADER
    # =====================================================
    #
    # The Context Loader prepares the information required
    # by the AI without making the actual decision.
    #
    # Context may contain:
    #
    #   - current user message
    #   - relevant conversation history
    #   - current checkout state
    #   - previous backend result
    #   - current order state
    #   - relevant user context
    #   - relevant product/order references
    #
    # IMPORTANT:
    #
    # Context is informational.
    #
    # It does NOT replace authoritative backend state.
    #
    # =====================================================

    context: dict[str, Any]

    # =====================================================
    # CONVERSATION HISTORY
    # =====================================================
    #
    # Previous conversational turns.
    #
    # This is used by the AI to understand references such as:
    #
    #   "that one"
    #   "the other one"
    #   "make it five"
    #   "same address"
    #   "my previous order"
    #
    # It is NOT authoritative transaction storage.
    #
    # =====================================================

    conversation_history: list[dict[str, Any]]

    # =====================================================
    # PHASE 2 - AI UNDERSTANDING
    # =====================================================

    # Semantic intent understood from the conversation.
    #
    # This is an AI interpretation, not a backend transaction
    # state.
    #
    # Examples:
    #
    #   general
    #   product_search
    #   order_create
    #   order_tracking
    #   order_cancel
    #   customer_support
    #   order_modify
    #
    intent: str

    # User's underlying conversational goal as understood
    # by the AI.
    #
    # Example:
    #
    #   "purchase three packets of Maggi"
    #
    # This is semantic information and must not be treated as
    # an instruction to mutate the database.
    #
    user_goal: str | None

    # Language detected/understood from the current
    # conversation.
    #
    # Examples:
    #
    #   en
    #   hi
    #   hinglish
    #   etc.
    #
    # The value is determined by the AI/language layer.
    #
    detected_language: str | None

    # Conversational references resolved by the AI.
    #
    # Examples:
    #
    # {
    #     "that_product": ...,
    #     "that_order": ...,
    #     "other_address": ...,
    # }
    #
    # These are semantic references.
    #
    # They must be resolved against authoritative state before
    # any backend mutation.
    #
    references: dict[str, Any]

    # =====================================================
    # ACCUMULATED TRANSACTION ENTITIES
    # =====================================================
    #
    # Information accumulated across turns.
    #
    # This is useful for conversational understanding.
    #
    # Dedicated authoritative state fields below should be
    # preferred once backend resolution has occurred.
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
    # =====================================================

    entities: dict[str, Any]

    # Information currently missing from the conversation/
    # checkout.
    #
    # This may initially be inferred by AI.
    #
    # Before a transaction is executed, required fields must
    # also be validated against authoritative backend state.
    #
    missing_fields: list[str]

    # =====================================================
    # PHASE 2 - AI PLANNER
    # =====================================================
    #
    # The planner converts understanding + context + current
    # transaction state into a proposed next action.
    #
    # Example:
    #
    # {
    #     "action": "CREATE_ORDER",
    #     "tool": "create_order",
    #     "arguments": {...},
    #     "missing_information": [],
    #     "confidence": 0.96
    # }
    #
    # IMPORTANT:
    #
    # planner_decision is a PROPOSAL.
    #
    # It does not have authority to mutate the database.
    #
    # Policy validation and backend services remain authoritative.
    #
    # =====================================================

    planner_decision: dict[str, Any]

    # AI-proposed conversational/action capability.
    #
    # Examples:
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
    # These are capability labels, not database operations.
    #
    planned_action: str | None

    # Tool proposed by the AI planner.
    #
    # Example:
    #
    #   search_products
    #   create_order
    #   track_order
    #
    # The policy layer must validate this before execution.
    #
    planned_tool: str | None

    # Arguments proposed for the planned capability/tool.
    #
    # These arguments are NOT automatically trusted.
    #
    # The policy/backend layer must validate:
    #
    #   identity
    #   authorization
    #   product
    #   stock
    #   address
    #   payment
    #   transaction state
    #   idempotency
    #
    planned_arguments: dict[str, Any]

    # Optional confidence supplied by the AI planner.
    #
    # Confidence is informational.
    #
    # It must NOT override backend validation.
    #
    planner_confidence: float | None

    # =====================================================
    # PHASE 2 - POLICY / VALIDATION
    # =====================================================
    #
    # Result produced after validating the AI planner's
    # proposed action.
    #
    # Example:
    #
    # {
    #     "allowed": True,
    #     "action": "CREATE_ORDER",
    #     "tool": "create_order"
    # }
    #
    # or:
    #
    # {
    #     "allowed": False,
    #     "reason": "checkout_already_completed"
    # }
    #
    # The policy layer protects the backend from invalid
    # or unsafe AI proposals.
    #
    # =====================================================

    policy_result: dict[str, Any]

    # Structured policy/validation error.
    #
    # This should contain actual validation information rather
    # than an AI-generated guess.
    #
    policy_error: dict[str, Any] | None

    # =====================================================
    # CHECKOUT / TRANSACTION IDENTITY
    # =====================================================

    # Unique identifier for the current checkout transaction.
    #
    # checkout_id is NOT the order ID.
    #
    # It identifies one logical checkout attempt and is used
    # for durable idempotency.
    #
    checkout_id: str | None

    # =====================================================
    # CHECKOUT STATUS
    # =====================================================
    #
    # Current lifecycle state of the checkout.
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
    # Other possible states:
    #
    #   failed
    #   cancelled
    #
    # The exact transition is controlled by application/
    # backend logic.
    #
    # The AI must understand the state but must not fabricate
    # transaction transitions.
    #
    # =====================================================

    checkout_status: str | None

    # =====================================================
    # CHECKOUT SELECTION - FRONTEND INPUT
    # =====================================================

    # Address selected through the frontend.
    #
    # Backend must verify ownership/validity.
    #
    selected_address_id: int | None

    # Payment method selected through the frontend.
    #
    # This is the user's selection.
    #
    # Backend must verify that the method is currently valid
    # and available.
    #
    selected_payment_method: str | None

    # Backward-compatible alias.
    #
    # Existing nodes may still use payment_method.
    #
    payment_method: str | None

    # =====================================================
    # DATABASE
    # =====================================================

    # SQLAlchemy session used by the graph when required.
    #
    # The session itself is infrastructure state and should
    # never be exposed to the LLM.
    #
    db: Any

    # =====================================================
    # RESOLVED PRODUCT
    # =====================================================

    # Natural-language product reference understood by AI.
    #
    product_name: str | None

    # Authoritative database product ID.
    #
    # This must come from product resolution/backend data.
    #
    product_id: int | None

    # =====================================================
    # CHECKOUT QUANTITY
    # =====================================================

    # Quantity understood/requested for the checkout.
    #
    # Backend must validate final quantity against stock.
    #
    quantity: int | None

    # =====================================================
    # SELECTED ADDRESS
    # =====================================================

    # Authoritative address ID used by the current checkout.
    #
    address_id: int | None

    # =====================================================
    # SELECTED PAYMENT
    # =====================================================

    # Backend-normalized/accepted payment method.
    #
    # Example:
    #
    # User:
    #   "cash on delivery"
    #
    # Backend:
    #   "cod"
    #
    # This field should represent the accepted/normalized
    # transaction value.
    #
    selected_payment_method_normalized: str | None

    # =====================================================
    # TOOL EXECUTION
    # =====================================================

    # Tool selected after planner + policy validation.
    #
    # This is the actual tool that will be executed.
    #
    tool_name: str | None

    # Authoritative result returned by the backend/tool.
    #
    # May contain:
    #
    #   products
    #   order
    #   billing
    #   tracking
    #   support
    #   validation errors
    #
    tool_result: Any

    # =====================================================
    # ORDER STATE
    # =====================================================

    # Backend-created order ID.
    #
    # NEVER generated by AI.
    #
    order_id: int | None

    # Whether an order has successfully been created for
    # this checkout.
    #
    # This is an important duplicate-order safeguard.
    #
    order_created: bool

    # Whether an order-creation attempt has already been made
    # for this checkout.
    #
    order_creation_attempted: bool

    # Whether the current checkout reached a terminal state.
    #
    # Terminal state may be:
    #
    #   completed
    #   cancelled
    #   failed
    #
    checkout_completed: bool

    # Whether the AI is waiting for the user to decide whether
    # they want to track the created order.
    #
    awaiting_order_tracking_confirmation: bool

    # =====================================================
    # TRANSACTION ERROR
    # =====================================================

    # Structured backend transaction error.
    #
    # Example:
    #
    # {
    #     "code": "OUT_OF_STOCK",
    #     "message": "...",
    #     "retryable": True
    # }
    #
    # The AI may explain this result but must not invent it.
    #
    transaction_error: dict[str, Any] | None

    # =====================================================
    # BILLING
    # =====================================================
    #
    # Billing is completely backend-authoritative.
    #
    # AI can explain it but cannot calculate it independently.
    #
    # =====================================================

    # Primary authoritative billing object.
    #
    # Example:
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
    billing: dict[str, Any]

    # Backward-compatible alias for billing.
    #
    bill: dict[str, Any]

    # Backend-returned billing line items.
    #
    billing_items: list[dict[str, Any]]

    # =====================================================
    # BILLING AMOUNTS
    # =====================================================
    #
    # Convenience projections of authoritative billing.
    #
    # These MUST be copied from backend results.
    #
    subtotal: float | None

    delivery_charge: float | None

    discount: float | None

    tax: float | None

    total_amount: float | None

    # Currency returned by backend.
    #
    currency: str | None

    # Payment method actually associated with the order.
    #
    # This may be backend-normalized.
    #
    billing_payment_method: str | None

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    # Final natural-language response generated for the user.
    #
    # The response node may use:
    #
    #   planner_decision
    #   policy_result
    #   tool_result
    #   order_id
    #   billing
    #   transaction_error
    #
    # But it must never invent authoritative values.
    #
    response: str

    # =====================================================
    # FRONTEND / GRAPH METADATA
    # =====================================================
    #
    # Structured data consumed by the frontend.
    #
    # Examples:
    #
    # address_selection
    # payment_selection
    # product_search
    # order_success
    # tracking
    # error
    #
    # Metadata must be generated from actual graph/backend
    # state.
    #
    metadata: dict[str, Any]