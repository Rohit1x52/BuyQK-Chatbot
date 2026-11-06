# Purpose:
# Classifies the user's message using the BuyQK LLM.
#
# Flow:
#
# User Message
#      ↓
# System Prompt
#      ↓
# Groq / Llama
#      ↓
# Structured Intent
#      ↓
# Pydantic Validation
#      ↓
# GraphState
#
# Supported intents:
# - product_search
# - order_create
# - cart
# - order_tracking
# - order_cancel
# - customer_support
# - service_booking
# - general


from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# =========================================================
# Supported Intents
# =========================================================

IntentType = Literal[
    "product_search",
    "order_create",
    "cart",
    "order_tracking",
    "order_cancel",
    "customer_support",
    "service_booking",
    "general",
]


# =========================================================
# Structured LLM Output
# =========================================================

class IntentOutput(BaseModel):
    """
    Structured output expected from the LLM.
    """

    intent: IntentType = Field(
        description=(
            "The primary intent of the user's message."
        )
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence that the selected intent "
            "is correct, between 0 and 1."
        ),
    )


    intents: list[IntentType] = Field(
        default_factory=list,
        description=(
            "All distinct supported intents explicitly requested in the "
            "current message, ordered with the primary request first. "
            "Return one item for a single-intent message. Do not infer "
            "requests that the user did not make."
        ),
    )


# =========================================================
# System Prompt
# =========================================================

INTENT_SYSTEM_PROMPT = """
You are the intent-classification component of BuyQK AI.

Identify every distinct supported intent explicitly requested in the
user's current message. Return the primary intent in `intent` and all
distinct requested intents in `intents`, ordered with the primary request
first. For a single-intent message, return a one-item `intents` list.

Supported intents are:

1. product_search
   User wants to find, search, browse, compare, or know the
   availability/price of a product.

   Examples:
   - "Find milk products"
   - "Search for Amul"
   - "What milk is available?"
   - "Show me prices for milk"
   - "Compare Amul and Mother Dairy milk"

2. order_create
   User wants to start a new purchase/order for a product.

   This includes statements like:
   - "I want to buy milk"
   - "I want Amul milk"
   - "Order me 2 packets of milk"
   - "Get me Amul"

   IMPORTANT:
   If the user is clearly asking to purchase a product but is
   NOT modifying an existing cart, classify it as order_create.

3. cart
   User wants to view or modify their existing shopping cart.

   This includes:
   - adding an item to the cart
   - removing an item from the cart
   - changing an item's quantity
   - clearing the cart
   - viewing the cart
   - checking cart contents or cart total
   - starting checkout from the cart

   Examples:
   - "Add 2 Maggi"
   - "Add milk to my cart"
   - "Remove Maggi"
   - "Remove milk from my cart"
   - "Make Maggi 5"
   - "Change Maggi quantity to 5"
   - "Clear my cart"
   - "Empty my cart"
   - "Show my cart"
   - "What's in my cart?"
   - "How much is my cart?"
   - "Checkout my cart"

   IMPORTANT:
   The cart intent means the user's request is about the
   EXISTING CART or modifying cart state.

4. order_tracking
   User wants to know the status, location, or progress
   of an existing order.

   Examples:
   - "Where is my order?"
   - "Track my order"
   - "What's the status of my order?"

5. order_cancel
   User wants to cancel an existing order.

   Examples:
   - "Cancel my order"
   - "I want to cancel order 123"

6. customer_support
   User has a complaint, issue, payment problem, delivery
   problem, refund issue, or wants customer assistance.

   Examples:
   - "My payment failed"
   - "I didn't receive my order"
   - "I want a refund"
   - "I have a complaint"

7. service_booking
   User wants to book, schedule, arrange, or manage a bookable service.

   This single intent covers finding a service, checking availability,
   choosing a professional, creating a booking, viewing/cancelling a booking,
   and booking payment.

   Do not create separate intents for individual booking operations.

8. general
   Greetings, casual conversation, or messages that do not
   match the other supported intents.

   Examples:
   - "Hello"
   - "Hi"
   - "Thanks"

Classification Rules:

- Return all distinct intents explicitly requested in the current message.
- Put the primary request first; preserve the user's order for remaining
  requests when possible.
- Do not split one operation into multiple intents. Buying a product is one
  order_create intent, not both product_search and order_create unless the
  user separately asks to search/browse as another task.
- Do not duplicate an intent in the list.
- If only one intent is requested, return exactly one item in `intents`.
- Determine the user's PRIMARY goal.
- Do not invent information.
- Do not confuse a new purchase request with an existing
  cart modification.
- If the user says "I want X", "I need X", "Give me X",
  or "Get me X", assume they want to start a purchase/order
  unless they are clearly referring to an existing cart.
- If the user explicitly refers to "cart", "my cart",
  "shopping cart", or an existing cart item, use cart.
- Requests such as "add X", "remove X", "make X 5",
  "change X quantity", "clear cart", and "show cart"
  should use cart.
- "Add 2 Maggi" → cart
- "Add milk to my cart" → cart
- "Remove Maggi" → cart
- "Make Maggi 5" → cart
- "Clear my cart" → cart
- "Show my cart" → cart
- "Checkout my cart" → cart
- "I want to buy milk" → order_create
- "I want Amul milk" → order_create
- "Order me 2 packets of milk" → order_create
- "Find milk" → product_search
- "What milk do you have?" → product_search
- "Where is my order?" → order_tracking
- "Cancel my order" → order_cancel
- "My payment failed" → customer_support
- A request to book or schedule a service → service_booking
- "Hello" → general

IMPORTANT:
Do not classify a product purchase request as cart merely
because the user intends to purchase something.

Use cart only when the user is explicitly or contextually
working with an existing cart.

If ambiguous, choose the intent that best represents the
user's primary goal.

CONVERSATION CONTEXT:
- If the user is answering a question from an active order,
  classify the answer according to the active order context rather
  than treating the short answer as a new unrelated request.
- Short answers such as quantities, sizes, addresses, delivery
  details, or payment choices may be continuations of an active
  order. Use the supplied conversation context when available.
- Never invent a product, quantity, address, order, or cart state.
"""


# =========================================================
# LLM
# =========================================================

llm = get_llm()


# =========================================================
# Structured LLM
# =========================================================
#
# with_structured_output() forces the model response into
# the IntentOutput Pydantic schema.
# =========================================================

structured_llm = llm.with_structured_output(
    IntentOutput
)


# =========================================================
# Normalization / Context Helpers
# =========================================================

def _normalize_intent(value: object) -> str:
    """Return a valid BuyQK intent without allowing invalid LLM output."""
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {
            "product_search",
            "order_create",
            "cart",
            "order_tracking",
            "order_cancel",
            "customer_support",
            "service_booking",
            "general",
        }:
            return value
    return "general"


def _looks_like_order_continuation(state: GraphState) -> bool:
    """Detect an already-active order conversation from graph state."""
    if not isinstance(state, dict):
        return False

    intent = state.get("intent")
    order_action = state.get("order_action")
    missing_fields = state.get("missing_fields")
    checkout_id = state.get("checkout_id")
    booking_id = state.get("booking_id")
    service_id = state.get("service_id")

    if intent == "service_booking" or booking_id or service_id:
        return True

    if intent == "order_create" or order_action in {
        "start_new_order",
        "continue_order",
    }:
        return True

    if checkout_id:
        return True

    return isinstance(missing_fields, (list, tuple)) and bool(missing_fields)


def _has_explicit_new_intent(message: str) -> bool:
    """Deprecated language heuristic; intent classification belongs to AI."""
    return False


def _looks_like_cart_continuation(state: GraphState) -> bool:
    """Detect an active cart operation awaiting the missing product reference."""
    if not isinstance(state, dict):
        return False

    if state.get("intent") != "cart":
        return False

    entities = state.get("entities") or {}
    if not isinstance(entities, dict):
        return False

    cart_action = entities.get("cart_action")
    if cart_action in {"add_item", "remove_item", "update_quantity"}:
        return True

    missing_fields = state.get("missing_fields") or []
    if isinstance(missing_fields, (list, tuple)) and (
        "product_reference" in missing_fields or "cart_action" in missing_fields
    ):
        return True

    return False


def _classify_with_context(
    message: str,
    state: GraphState,
) -> str | None:
    """Return a context-derived continuation only when it is unambiguous."""
    text = message.strip()
    if not text or _has_explicit_new_intent(text):
        return None

    if _looks_like_cart_continuation(state):
        return "cart"

    if not _looks_like_order_continuation(state):
        return None

    # The active order context establishes the user's transaction goal.
    # Entity/Planner remain responsible for interpreting the actual value.
    return "order_create"


# =========================================================
# Classify Multiple Intents
# =========================================================

def classify_intents(
    message: str,
    state: GraphState | None = None,
) -> list[str]:
    """
    Return distinct supported intents in primary-first order.

    The legacy classify_intent() function remains available and still
    returns one primary intent for existing callers.
    """
    if not isinstance(message, str) or not message.strip():
        return ["general"]

    if (
        isinstance(state, dict)
        and str(state.get("commerce_vertical") or "").casefold() == "electronics"
        and isinstance(state.get("comparison_product_ids"), list)
        and len(state["comparison_product_ids"]) >= 2
    ):
        return ["product_search"]

    clean_message = message.strip()
    try:
        result: IntentOutput = structured_llm.invoke(
            [
                SystemMessage(content=INTENT_SYSTEM_PROMPT),
                HumanMessage(content=clean_message),
            ]
        )
        primary = _normalize_intent(getattr(result, "intent", None))
        raw_intents = getattr(result, "intents", None) or []
        intents: list[str] = []

        for raw in raw_intents:
            value = _normalize_intent(raw)
            if value not in intents:
                intents.append(value)

        if primary in intents:
            intents.remove(primary)
        intents.insert(0, primary)

        if primary in intents:
            intents.remove(primary)
        intents.insert(0, primary)
        return intents or [primary]

    except Exception as exc:
        print(f"[INTENT ERROR] {type(exc).__name__}: {exc}")
        contextual_intent = _classify_with_context(
            clean_message,
            state or {},
        )
        if contextual_intent is not None:
            return [contextual_intent]
        return ["general"]


# =========================================================
# Classify Intent
# =========================================================

def classify_intent(
    message: str,
    state: GraphState | None = None,
) -> str:
    """
    Classify a user message using the LLM.

    Args:
        message:
            User's natural-language message.

    Returns:
        One of the supported BuyQK intents.
    """

    if not message or not message.strip():
        return "general"

    if (
        isinstance(state, dict)
        and str(state.get("commerce_vertical") or "").casefold() == "electronics"
        and isinstance(state.get("comparison_product_ids"), list)
        and len(state["comparison_product_ids"]) >= 2
    ):
        return "product_search"

    messages = [
        SystemMessage(
            content=INTENT_SYSTEM_PROMPT
        ),
        HumanMessage(
            content=message.strip()
        ),
    ]

    try:
        result: IntentOutput = (
            structured_llm.invoke(
                messages
            )
        )

        normalized_intent = _normalize_intent(
            getattr(result, "intent", None)
        )
        return normalized_intent

    except Exception as exc:

        # -------------------------------------------------
        # Safe fallback
        # -------------------------------------------------
        #
        # If the LLM/API temporarily fails, the graph
        # should not completely crash.
        #
        # We use conservative deterministic rules only
        # as an availability fallback.
        # -------------------------------------------------

        print(
            f"[INTENT ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        if state is not None:
            contextual_intent = _classify_with_context(
                message,
                state,
            )
            if contextual_intent is not None:
                return contextual_intent

        return "general"


# =========================================================
# Intent Node
# =========================================================

def intent_node(
    state: GraphState,
) -> GraphState:
    """
    LangGraph node responsible for intent classification.

    Writes:
        intent: backward-compatible primary intent.
        detected_intents: ordered list of detected intent records.
    """
    message = state.get("message", "")
    intents = classify_intents(message, state)
    primary_intent = intents[0] if intents else "general"

    return {
        "intent": primary_intent,
        "detected_intents": [
            {"intent": item, "status": "pending", "position": index}
            for index, item in enumerate(intents)
        ],
    }
