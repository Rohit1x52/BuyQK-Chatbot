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
   User wants to find, search for, browse, compare, or know the
   availability/price of a product. Examples:
   - "Find milk products"
   - "Search for Amul"
   - "What milk is available?"
   - "Show me prices for milk"

2. order_create
   User wants to buy, order, or purchase a product. This includes
   statements like "I want X", "Give me X", "I need X" unless they
   are explicitly asking for information only. Examples:
   - "I want to buy milk"
   - "I want Amul milk" (implies wanting to purchase)
   - "Order me 2 packets of milk"
   - "Get me Amul"

3. order_tracking
   User wants to know the status, location, or progress
   of an existing order.

4. order_cancel
   User wants to cancel an existing order.

5. customer_support
   User has a complaint, issue, payment problem, delivery
   problem, refund issue, or wants customer assistance.

6. general
   Greetings, casual conversation, or messages that do not
   match the other supported intents.

Classification Rules:

- Select exactly one intent.
- Determine the user's primary goal.
- Do not invent information.
- If user says "I want X" or "I need X" or "Give me X", assume
  they want to ORDER/PURCHASE unless they ask for information
  (e.g., "I want to know about milk").
- If user asks to find/search/check/show/compare, it's product_search.
- "I want to buy milk" → order_create
- "I want Amul milk" → order_create
- "Find milk" → product_search
- "What milk do you have?" → product_search
- "Where is my order?" → order_tracking
- "Cancel my order" → order_cancel
- "My payment failed" → customer_support
- "Hello" → general
- If ambiguous, lean toward product_search for explicit search
  terms, or general for unclear messages.
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
        # We currently return general rather than
        # inventing an intent.
        # -------------------------------------------------

        print(
            f"[INTENT ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        # Deterministic fallback heuristics to handle API
        # outages or rate limits. These simple rules are
        # intentionally conservative and avoid inventing facts.
        text = message.lower()

        # Check order-related intents first (higher priority)
        if any(k in text for k in ["buy", "purchase", "i want", "i need", "give me", "order"]):
            # Distinguish tracking queries like "where is my order"
            if "where" in text or "status" in text or "track" in text:
                return "order_tracking"
            return "order_create"

        if any(k in text for k in ["find", "search", "available", "price", "how much", "do you have", "show me", "what"]):
            return "product_search"

        if "cancel" in text and "order" in text:
            return "order_cancel"

        if any(k in text for k in ["payment", "refund", "failed", "complaint"]):
            return "customer_support"

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