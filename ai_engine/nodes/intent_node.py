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


# =========================================================
# System Prompt
# =========================================================

INTENT_SYSTEM_PROMPT = """
You are the intent-classification component of BuyQK AI.

Classify the user's message into exactly one of the
following intents:

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

7. general
   Greetings, casual conversation, or messages that do not
   match the other supported intents.

   Examples:
   - "Hello"
   - "Hi"
   - "Thanks"

Classification Rules:

- Select exactly one intent.
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
- "Hello" → general

IMPORTANT:
Do not classify a product purchase request as cart merely
because the user intends to purchase something.

Use cart only when the user is explicitly or contextually
working with an existing cart.

If ambiguous, choose the intent that best represents the
user's primary goal.
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
# Classify Intent
# =========================================================

def classify_intent(
    message: str,
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

        return result.intent

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

        text = message.lower().strip()

        # -------------------------------------------------
        # Cart intent
        # -------------------------------------------------
        #
        # Check explicit cart operations first so that
        # phrases such as "add to my cart" do not get
        # incorrectly classified as order_create.
        # -------------------------------------------------

        cart_phrases = [
            "my cart",
            "the cart",
            "shopping cart",
            "to cart",
            "in cart",
            "into cart",
            "from cart",
            "cart",
        ]

        cart_actions = [
            "add",
            "remove",
            "delete",
            "clear",
            "empty",
            "show",
            "view",
            "checkout",
            "update",
            "change",
            "make",
        ]

        if (
            any(phrase in text for phrase in cart_phrases)
            and any(action in text for action in cart_actions)
        ):
            return "cart"

        # Explicit cart commands without the word "cart".
        #
        # Examples:
        # "Remove Maggi"
        # "Make Maggi 5"
        #
        # These are conservative patterns and are only
        # used when the LLM itself is unavailable.

        if text.startswith(
            (
                "remove ",
                "delete ",
                "clear ",
                "empty ",
            )
        ):
            return "cart"

        if (
            text.startswith("make ")
            or text.startswith("change ")
            or text.startswith("update ")
        ):
            return "cart"

        # -------------------------------------------------
        # Order-related intents
        # -------------------------------------------------

        if any(
            keyword in text
            for keyword in [
                "buy",
                "purchase",
                "i want",
                "i need",
                "give me",
                "order",
            ]
        ):

            # Distinguish tracking queries such as:
            # "Where is my order?"
            # "What is my order status?"
            # "Track my order"

            if any(
                keyword in text
                for keyword in [
                    "where",
                    "status",
                    "track",
                    "tracking",
                ]
            ):
                return "order_tracking"

            return "order_create"

        # -------------------------------------------------
        # Product search
        # -------------------------------------------------

        if any(
            keyword in text
            for keyword in [
                "find",
                "search",
                "available",
                "price",
                "how much",
                "do you have",
                "show me",
                "what",
                "compare",
            ]
        ):
            return "product_search"

        # -------------------------------------------------
        # Order cancellation
        # -------------------------------------------------

        if (
            "cancel" in text
            and "order" in text
        ):
            return "order_cancel"

        # -------------------------------------------------
        # Customer support
        # -------------------------------------------------

        if any(
            keyword in text
            for keyword in [
                "payment",
                "refund",
                "failed",
                "complaint",
            ]
        ):
            return "customer_support"

        # -------------------------------------------------
        # Default
        # -------------------------------------------------

        return "general"


# =========================================================
# Intent Node
# =========================================================

def intent_node(
    state: GraphState,
) -> GraphState:
    """
    LangGraph node responsible for intent classification.

    Reads:
        state["message"]

    Writes:
        state["intent"]
    """

    message = state.get(
        "message",
        "",
    )

    intent = classify_intent(
        message
    )

    return {
        "intent": intent,
    }