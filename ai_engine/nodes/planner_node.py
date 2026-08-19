# =========================================================
# BuyQK AI - Planner Node
# =========================================================
#
# Purpose:
# Convert AI understanding + conversation context +
# transaction state into a structured action proposal.
#
# Phase 2 architecture:
#
# User
#   ↓
# Context
#   ↓
# Understanding
#   ↓
# Planner
#   ↓
# Policy
#   ↓
# Tool
#
# IMPORTANT:
#
# The planner is an AI decision layer.
#
# It determines:
#
#   - user's current goal
#   - appropriate next action
#   - whether clarification is required
#   - appropriate capability/tool
#   - proposed tool arguments
#
# The planner DOES NOT:
#
#   - create database records
#   - calculate prices
#   - calculate bills
#   - validate stock
#   - authorize users
#   - validate payment
#   - generate order IDs
#   - bypass checkout state
#
# The planner produces a PROPOSAL.
#
# Policy validation + backend services remain authoritative.
#
# =========================================================

from __future__ import annotations

import json
from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Planner Capabilities
# =========================================================
#
# These are generic capabilities, not product-specific
# business rules.
#
# The AI chooses the appropriate capability based on
# conversation/context.
#
# =========================================================

PLANNER_ACTIONS = {
    "SEARCH_PRODUCT",
    "START_CHECKOUT",
    "CONTINUE_CHECKOUT",
    "SELECT_ADDRESS",
    "SELECT_PAYMENT",
    "CREATE_ORDER",
    "TRACK_ORDER",
    "CANCEL_ORDER",
    "MODIFY_ORDER",
    "SUPPORT",
    "ANSWER",
    "ASK_CLARIFICATION",
    "CONFIRM",
    "END_CONVERSATION",
}


# =========================================================
# Supported Backend Capabilities
# =========================================================

SUPPORTED_TOOLS = {
    "search_products",
    "create_order",
    "track_order",
    "cancel_order",
    "create_support_ticket",
    "list_saved_addresses",
}


# =========================================================
# Planner System Prompt
# =========================================================

PLANNER_SYSTEM_PROMPT = """
You are the BuyQK AI planning layer.

Your responsibility is to understand the user's current
goal and propose the most appropriate NEXT ACTION.

You receive:
- current user message
- conversation context
- previous AI understanding
- accumulated entities
- checkout state
- transaction state
- previous backend results
- billing information when available

You must reason about the conversation and choose an
appropriate action.

You may:
- identify the user's goal
- continue an existing workflow
- start a new workflow
- recognize a modification
- recognize tracking intent
- recognize cancellation intent
- recognize support intent
- ask for clarification
- decide that no backend tool is necessary
- select the appropriate capability/tool

You must NOT invent authoritative business information.

Never invent:
- product prices
- stock
- order IDs
- bills
- taxes
- delivery charges
- discounts
- payment availability
- order status
- cancellation eligibility
- refund eligibility

Backend results are authoritative.

If a transaction has already been successfully created,
do NOT propose creating another order merely because the
user sends a conversational message such as:
- thank you
- thanks
- okay
- great
- got it
- bye

If the current conversation is already a completed
transaction, understand subsequent conversational messages
in that context.

Use the conversation history to resolve references such as:
- "that one"
- "the other one"
- "make it five"
- "same address"
- "change that"
- "track it"

Do not guess when the reference is genuinely ambiguous.
Use ASK_CLARIFICATION.

Return ONLY valid JSON.

The JSON must contain:

{
  "action": "...",
  "intent": "...",
  "user_goal": "...",
  "missing_information": [],
  "tool": null,
  "tool_arguments": {},
  "confidence": 0.0
}

Rules:
- action must be one of the supported planner actions.
- tool must be null when no backend tool is required.
- tool must be one of the supported tools when a tool is required.
- missing_information must contain only information genuinely
  required for the proposed action.
- tool_arguments must contain only information already
  understood or available in context.
- confidence must be a number between 0 and 1.
"""


# =========================================================
# Generic JSON Extraction
# =========================================================

def _extract_json(
    content: Any,
) -> dict[str, Any]:
    """
    Convert an LLM response into a JSON dictionary.

    Handles:
    - plain JSON
    - markdown JSON fences
    """

    if isinstance(
        content,
        dict,
    ):
        return content

    if not isinstance(
        content,
        str,
    ):
        raise ValueError(
            "Planner returned an invalid response."
        )

    text = content.strip()

    if text.startswith(
        "```"
    ):
        lines = text.splitlines()

        if (
            lines
            and lines[0].startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    try:
        parsed = json.loads(
            text
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Planner returned invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "Planner response must be a JSON object."
        )

    return parsed


# =========================================================
# Normalize Planner Decision
# =========================================================

def _normalize_decision(
    decision: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize the planner output without changing its
    semantic decision.

    This function performs schema validation only.
    It does not make conversational decisions.
    """

    action = decision.get(
        "action"
    )

    if not isinstance(
        action,
        str,
    ):
        raise ValueError(
            "Planner did not provide an action."
        )

    action = action.strip().upper()

    if action not in PLANNER_ACTIONS:
        raise ValueError(
            f"Planner returned unsupported action: {action}"
        )

    intent = decision.get(
        "intent"
    )

    if intent is None:
        intent = ""

    if not isinstance(
        intent,
        str,
    ):
        intent = str(
            intent
        )

    user_goal = decision.get(
        "user_goal"
    )

    if user_goal is not None and not isinstance(
        user_goal,
        str,
    ):
        user_goal = str(
            user_goal
        )

    missing_information = decision.get(
        "missing_information",
        [],
    )

    if not isinstance(
        missing_information,
        list,
    ):
        missing_information = []

    missing_information = [
        str(item)
        for item in missing_information
        if item is not None
    ]

    tool = decision.get(
        "tool"
    )

    if tool is not None:
        if not isinstance(
            tool,
            str,
        ):
            raise ValueError(
                "Planner tool must be a string or null."
            )

        tool = tool.strip()

        if tool and tool not in SUPPORTED_TOOLS:
            raise ValueError(
                f"Planner returned unsupported tool: {tool}"
            )

    tool_arguments = decision.get(
        "tool_arguments",
        {},
    )

    if not isinstance(
        tool_arguments,
        dict,
    ):
        tool_arguments = {}

    confidence = decision.get(
        "confidence"
    )

    if confidence is not None:
        try:
            confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = None

    if confidence is not None:
        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    return {
        "action": action,
        "intent": intent,
        "user_goal": user_goal,
        "missing_information": missing_information,
        "tool": tool,
        "tool_arguments": tool_arguments,
        "confidence": confidence,
    }


# =========================================================
# LLM Provider
# =========================================================

def _get_planner_llm():
    """
    Create the LLM used by the planner.

    The planner intentionally uses the application's existing
    AI provider configuration rather than introducing a new
    provider or hardcoding credentials here.

    Supported project configurations are attempted in order.
    """

    # -----------------------------------------------------
    # Existing project LLM factory
    # -----------------------------------------------------

    try:
        from ai_engine.llm import get_llm

        return get_llm()

    except ImportError:
        pass

    # -----------------------------------------------------
    # Existing project model factory
    # -----------------------------------------------------

    try:
        from ai_engine.llm.factory import get_llm

        return get_llm()

    except ImportError:
        pass

    # -----------------------------------------------------
    # LangChain Groq fallback
    # -----------------------------------------------------

    try:
        from langchain_groq import ChatGroq

        import os

        api_key = os.getenv(
            "GROQ_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured."
            )

        model = os.getenv(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile",
        )

        return ChatGroq(
            model=model,
            temperature=0,
        )

    except ImportError as exc:
        raise RuntimeError(
            "No supported planner LLM provider is configured."
        ) from exc


# =========================================================
# Invoke Planner LLM
# =========================================================

def _invoke_planner_llm(
    context: dict[str, Any],
) -> dict[str, Any]:
    """
    Ask the LLM to produce a structured planning proposal.
    """

    llm = _get_planner_llm()

    prompt = (
        PLANNER_SYSTEM_PROMPT
        + "\n\n"
        + "CURRENT BUYQK CONTEXT:\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            default=str,
        )
        + "\n\n"
        + "Return ONLY the JSON planner decision."
    )

    # -----------------------------------------------------
    # LangChain-style LLM
    # -----------------------------------------------------

    if hasattr(
        llm,
        "invoke",
    ):
        result = llm.invoke(
            prompt
        )

        content = getattr(
            result,
            "content",
            result,
        )

        return _extract_json(
            content
        )

    # -----------------------------------------------------
    # Generic callable
    # -----------------------------------------------------

    if callable(llm):
        result = llm(
            prompt
        )

        content = getattr(
            result,
            "content",
            result,
        )

        return _extract_json(
            content
        )

    raise RuntimeError(
        "Configured planner LLM cannot be invoked."
    )


# =========================================================
# Planner Node
# =========================================================

def planner_node(
    state: GraphState,
) -> GraphState:
    """
    Phase 2 AI Planner.

    Input:
        GraphState containing context + AI understanding +
        transaction state.

    Output:
        GraphState containing planner_decision and its
        normalized projections.

    IMPORTANT:
    This node proposes an action.

    It does NOT execute tools.
    """

    context = state.get(
        "context",
        {},
    )

    if not context:
        raise ValueError(
            "Planner requires context from context_node."
        )

    decision = _invoke_planner_llm(
        context
    )

    normalized = _normalize_decision(
        decision
    )

    return {
        "planner_decision": normalized,

        "planned_action": normalized[
            "action"
        ],

        "planned_tool": normalized[
            "tool"
        ],

        "planned_arguments": normalized[
            "tool_arguments"
        ],

        "planner_confidence": normalized[
            "confidence"
        ],

        # The planner may refine semantic understanding.
        # These values are still AI interpretation, not
        # authoritative backend transaction values.
        "user_goal": normalized[
            "user_goal"
        ],
    }