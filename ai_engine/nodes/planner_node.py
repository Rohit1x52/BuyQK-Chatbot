# =========================================================
# BuyQK - AI Planner Node
# =========================================================
#
# Purpose:
#
# Convert AI-understood conversation state into a structured
# execution plan.
#
# Architecture:
#
# User Message
#       ↓
# Context
#       ↓
# Entity / Understanding
#       ↓
# Planner
#       ↓
# Policy
#       ↓
# Decision
#       ↓
# Tool
#
# IMPORTANT:
#
# The planner is an AI reasoning layer.
#
# It may determine:
#
#   - user's goal
#   - conversational action
#   - required capability
#   - missing information
#   - checkout modification
#   - tracking request
#   - cancellation request
#   - support request
#
# It must NOT:
#
#   - calculate prices
#   - calculate bills
#   - invent stock
#   - invent order IDs
#   - invent payment results
#   - authorize transactions
#   - mutate the database
#
# Backend services remain authoritative for all
# transactional/business facts.
# =========================================================

from __future__ import annotations

import json
import re
from typing import Any

# IMPORTANT:
#
# Import get_llm directly into THIS module.
#
# Tests and other Phase-2 components intentionally patch:
#
#     planner_node.get_llm
#
# Therefore this symbol must exist at module level.
#
from ai_engine.llm.client import get_llm


# =========================================================
# Planner Actions
# =========================================================

PLANNER_ACTIONS: set[str] = {
    "answer",
    "end_conversation",
    "ask_clarification",
    "start_checkout",
    "modify_checkout",
    "search_products",
    "add_to_checkout",
    "create_order",
    "track_order",
    "cancel_order",
    "request_support",
}


# =========================================================
# Utility: Extract Response Content
# =========================================================

def _get_content(response: Any) -> Any:
    """
    Extract content from a LangChain response.

    Supports:
        - AIMessage-like objects
        - dictionaries
        - strings
        - structured content blocks
    """

    if isinstance(response, dict):
        return response

    content = getattr(response, "content", None)

    if content is not None:
        return content

    return response


# =========================================================
# Utility: Extract JSON
# =========================================================

def _extract_json(content: Any) -> dict[str, Any]:
    """
    Extract a JSON object from an LLM response.

    Handles:
        direct JSON
        markdown JSON fences
        Qwen <think>...</think> output
        explanatory text surrounding JSON
        structured LangChain content
    """

    # -----------------------------------------------------
    # Dictionary already returned
    # -----------------------------------------------------

    if isinstance(content, dict):
        return content

    # -----------------------------------------------------
    # LangChain message object
    # -----------------------------------------------------

    if not isinstance(content, str):

        message_content = getattr(
            content,
            "content",
            None,
        )

        if isinstance(message_content, str):

            content = message_content

        elif isinstance(message_content, list):

            text_parts: list[str] = []

            for block in message_content:

                if isinstance(block, str):
                    text_parts.append(block)

                elif isinstance(block, dict):

                    text = block.get("text")

                    if isinstance(text, str):
                        text_parts.append(text)

            content = "\n".join(text_parts)

        else:

            raise ValueError(
                "Planner returned an unsupported response type."
            )

    # -----------------------------------------------------
    # Validate text
    # -----------------------------------------------------

    text = content.strip()

    if not text:
        raise ValueError(
            "Planner returned an empty response."
        )

    # -----------------------------------------------------
    # Remove Qwen reasoning blocks
    # -----------------------------------------------------

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()

    # -----------------------------------------------------
    # Remove unmatched <think>
    # -----------------------------------------------------

    if "<think>" in text.lower():

        text = re.sub(
            r"<think>.*",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

    # -----------------------------------------------------
    # Remove markdown fences
    # -----------------------------------------------------

    if text.startswith("```"):

        lines = text.splitlines()

        if (
            lines
            and lines[0].strip().startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # -----------------------------------------------------
    # Direct JSON
    # -----------------------------------------------------

    try:

        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # -----------------------------------------------------
    # Embedded JSON
    # -----------------------------------------------------

    decoder = json.JSONDecoder()

    for index, character in enumerate(text):

        if character != "{":
            continue

        candidate = text[index:]

        try:

            parsed, _ = decoder.raw_decode(candidate)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            continue

    raise ValueError(
        "Planner returned invalid JSON."
    )


# =========================================================
# Utility: Normalize Action
# =========================================================

def _normalize_action(
    action: Any,
) -> str | None:
    """
    Normalize equivalent action field names.

    The AI may return:

        action
        capability
        tool
        tool_name
        intent

    No conversational decision is made here.
    """

    if not isinstance(action, str):
        return None

    normalized = (
        action
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return normalized or None


# =========================================================
# Utility: Normalize Planner Output
# =========================================================

def _normalize_plan(
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert raw LLM output into the canonical planner
    contract.
    """

    # -----------------------------------------------------
    # Action
    # -----------------------------------------------------

    action = _normalize_action(
        plan.get("action")
    )

    if action is None:

        for field in (
            "capability",
            "tool",
            "tool_name",
            "intent",
        ):

            action = _normalize_action(
                plan.get(field)
            )

            if action is not None:
                break

    # -----------------------------------------------------
    # Arguments
    # -----------------------------------------------------

    arguments = plan.get("arguments")

    if not isinstance(arguments, dict):

        arguments = plan.get(
            "tool_arguments"
        )

    if not isinstance(arguments, dict):
        arguments = {}

    # -----------------------------------------------------
    # Missing fields
    # -----------------------------------------------------

    missing_fields = plan.get(
        "missing_fields"
    )

    if not isinstance(
        missing_fields,
        list,
    ):
        missing_fields = []

    # Keep only strings.
    missing_fields = [
        str(value)
        for value in missing_fields
        if value is not None
    ]

    # -----------------------------------------------------
    # Confidence
    # -----------------------------------------------------

    confidence = plan.get(
        "confidence"
    )

    if isinstance(
        confidence,
        (int, float),
    ):

        confidence = max(
            0.0,
            min(
                1.0,
                float(confidence),
            ),
        )

    else:

        confidence = None

    # -----------------------------------------------------
    # Reason
    # -----------------------------------------------------

    reason = plan.get("reason")

    if not isinstance(reason, str):
        reason = None

    # -----------------------------------------------------
    # Canonical contract
    # -----------------------------------------------------

    return {
        "action": action,
        "tool_name": action,
        "arguments": arguments,
        "missing_fields": missing_fields,
        "confidence": confidence,
        "reason": reason,
    }


# =========================================================
# Planner Prompt
# =========================================================

def _build_planner_prompt(
    state: dict[str, Any],
) -> str:
    """
    Build the planner prompt from GraphState.

    Only conversational reasoning is delegated to the LLM.
    """

    message = state.get(
        "message",
        "",
    )

    conversation_history = state.get(
        "conversation_history",
        [],
    )

    entities = state.get(
        "entities",
        {},
    )

    intent = state.get(
        "intent"
    )

    missing_fields = state.get(
        "missing_fields",
        [],
    )

    # -----------------------------------------------------
    # Authoritative checkout state
    # -----------------------------------------------------

    checkout_state = {
        "checkout_id": state.get(
            "checkout_id"
        ),
        "checkout_status": state.get(
            "checkout_status"
        ),
        "order_created": state.get(
            "order_created"
        ),
        "order_id": state.get(
            "order_id"
        ),
        "bill": state.get(
            "bill"
        ),
    }

    # -----------------------------------------------------
    # Frontend selection
    # -----------------------------------------------------

    frontend_state = {
        "selected_address_id": state.get(
            "selected_address_id"
        ),
        "payment_method": state.get(
            "payment_method"
        ),
        "selected_payment_method": state.get(
            "selected_payment_method"
        ),
    }

    # -----------------------------------------------------
    # Safe context
    # -----------------------------------------------------

    context = {
        "current_message": message,
        "conversation_history": conversation_history,
        "intent": intent,
        "entities": entities,
        "missing_fields": missing_fields,
        "checkout": checkout_state,
        "frontend_selection": frontend_state,
    }

    return f"""
You are the BuyQK AI Planner.

Your job is to understand the user's CURRENT goal and
produce exactly ONE structured execution plan.

You are a conversational reasoning layer.

You may decide:

- what the user means
- the user's current goal
- whether the user wants to start a checkout
- whether the user wants to modify an existing checkout
- whether the user wants product search
- whether the user wants tracking
- whether the user wants cancellation
- whether the user wants support
- whether clarification is required
- whether the message is ordinary conversation
- which backend capability is appropriate

You must NOT:

- calculate prices
- calculate bills
- invent stock
- invent order IDs
- invent payment results
- invent transaction success
- decide backend authorization
- decide cancellation eligibility
- mutate the database
- claim an order was created without authoritative backend state

The backend is authoritative for transactional facts.

IMPORTANT CHECKOUT RULE:

The supplied checkout state is authoritative.

If:

checkout_status = "completed"
and
order_created = true

then a normal acknowledgement such as "Thank you",
"Thanks", "Okay", "Alright", or "Got it" must NOT
be interpreted as another purchase.

If the user explicitly expresses a NEW shopping goal,
that is a new conversational goal.

If the user wants to change an active checkout,
use modify_checkout.

If the user's reference cannot be resolved from the
available context, use ask_clarification.

Available capabilities:

answer
end_conversation
ask_clarification
start_checkout
modify_checkout
search_products
add_to_checkout
create_order
track_order
cancel_order
request_support

Return ONLY JSON.

Required structure:

{{
  "action": "<one action>",
  "arguments": {{}},
  "missing_fields": [],
  "confidence": 0.0,
  "reason": "<short explanation>"
}}

The arguments object may contain only information
supported by the supplied context.

Do not invent transactional values.

CURRENT GRAPH STATE:

{json.dumps(
    context,
    ensure_ascii=False,
    default=str,
    indent=2,
)}
""".strip()


# =========================================================
# Planner Node
# =========================================================

def planner_node(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the AI planner.

    Input:
        GraphState

    Output:
        planner
        planner_args
        missing_fields

    This node does NOT execute backend operations.
    """

    # -----------------------------------------------------
    # Build prompt
    # -----------------------------------------------------

    prompt = _build_planner_prompt(
        state
    )

    # -----------------------------------------------------
    # IMPORTANT
    #
    # get_llm is deliberately resolved through the module
    # namespace.
    #
    # This allows:
    #
    # monkeypatch.setattr(
    #     planner_module,
    #     "get_llm",
    #     ...
    # )
    #
    # and keeps production configuration centralized.
    # -----------------------------------------------------

    llm = get_llm()

    # -----------------------------------------------------
    # Invoke model
    # -----------------------------------------------------

    response = llm.invoke(
        prompt
    )

    # -----------------------------------------------------
    # Extract response
    # -----------------------------------------------------

    content = _get_content(
        response
    )

    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    raw_plan = _extract_json(
        content
    )

    # -----------------------------------------------------
    # Normalize
    # -----------------------------------------------------

    plan = _normalize_plan(
        raw_plan
    )

    # -----------------------------------------------------
    # Validate capability
    # -----------------------------------------------------

    action = plan.get(
        "action"
    )

    if (
        action is not None
        and action not in PLANNER_ACTIONS
    ):

        plan["action"] = None
        plan["tool_name"] = None

        plan["reason"] = (
            "Planner returned an unsupported capability."
        )

    # -----------------------------------------------------
    # Preserve backend transaction state
    # -----------------------------------------------------
    #
    # IMPORTANT:
    #
    # Do NOT return replacements for:
    #
    # checkout_id
    # checkout_status
    # order_created
    # order_id
    # bill
    #
    # The planner cannot mutate authoritative transaction
    # state.
    # -----------------------------------------------------

    result: dict[str, Any] = {
        "planner": plan,

        "planner_args": dict(
            plan.get(
                "arguments",
                {},
            )
        ),

        "missing_fields": list(
            plan.get(
                "missing_fields",
                state.get(
                    "missing_fields",
                    [],
                ),
            )
        ),
    }

    # -----------------------------------------------------
    # Debug logging
    # -----------------------------------------------------

    print(
        "\n"
        + "=" * 60
        + "\n"
        + "[AI PLANNER NODE]"
        + "\n"
        + "=" * 60
    )

    print(
        f"message         = "
        f"{state.get('message')!r}"
    )

    print(
        f"action          = "
        f"{plan.get('action')!r}"
    )

    print(
        f"arguments       = "
        f"{plan.get('arguments')!r}"
    )

    print(
        f"missing_fields  = "
        f"{plan.get('missing_fields')!r}"
    )

    print(
        f"confidence      = "
        f"{plan.get('confidence')!r}"
    )

    print(
        f"checkout_id     = "
        f"{state.get('checkout_id')!r}"
    )

    print(
        f"checkout_status = "
        f"{state.get('checkout_status')!r}"
    )

    print(
        f"order_created   = "
        f"{state.get('order_created')!r}"
    )

    print(
        f"order_id        = "
        f"{state.get('order_id')!r}"
    )

    print("=" * 60)

    return result