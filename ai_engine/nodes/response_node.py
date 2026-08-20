# =========================================================
# BuyQK AI - Response Node
# =========================================================
#
# Phase 2
#
# =========================================================
#
# ARCHITECTURE
#
#     User Message
#          ↓
#     Context Node
#          ↓
#     Entity Node
#          ↓
#     Planner Node
#          ↓
#     Policy Node
#          ↓
#     Decision Node
#          ↓
#     Tool Node
#          ↓
#     Response Node
#
# =========================================================
#
# RESPONSIBILITY
#
# The Response Node is a PRESENTATION layer.
#
# It:
#
#   - interprets already-approved graph state
#   - presents backend/tool results
#   - generates natural language
#   - generates frontend metadata
#   - preserves authoritative transactional values
#   - renders checkout UI metadata
#
# It does NOT:
#
#   - decide intent
#   - select tools
#   - enforce policy
#   - choose checkout sequence
#   - calculate prices
#   - calculate taxes
#   - calculate discounts
#   - calculate delivery charges
#   - create orders
#   - modify backend state
#   - invent transactional facts
#
# =========================================================
#
# SOURCE OF TRUTH
#
# Planner:
#     decides WHAT should happen.
#
# Policy:
#     decides WHETHER it is allowed.
#
# Decision:
#     routes the approved action.
#
# Tool:
#     executes the capability.
#
# Backend:
#     owns transactional truth.
#
# Response:
#     explains what happened.
#
# =========================================================


from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# =========================================================
# LLM
# =========================================================

llm = get_llm()


# =========================================================
# Constants
# =========================================================

CHECKOUT_FIELDS = (
    "product_name",
    "quantity",
    "address_selection",
    "payment_method",
)


# =========================================================
# Utility
# =========================================================


def _has_value(
    value: Any,
) -> bool:
    """
    Return True when a value is actually present.

    None and empty strings are considered missing.

    Numeric zero is considered present here because this helper
    is only checking presence, not business validity.
    """

    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(
            value.strip()
        )

    return True


def _safe_int(
    value: Any,
) -> int | None:
    """
    Safely convert a value to integer.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _serialize_data(
    data: Any,
) -> str:
    """
    Safely serialize arbitrary graph state for the LLM.

    Graph state can contain ORM objects or other values that are
    not directly JSON serializable.
    """

    if data is None:
        return "{}"

    try:

        return json.dumps(
            data,
            default=str,
            ensure_ascii=False,
        )

    except Exception:

        return "{}"


def _extract_text_content(content: Any) -> str:
    """
    Convert common LangChain response-content shapes into plain text.

    Supports:
        - plain strings
        - objects with .content
        - list-based content blocks
        - dict content blocks
    """
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text

        content_value = content.get("content")
        if isinstance(content_value, str):
            return content_value

        if isinstance(content_value, list):
            return _extract_text_content(content_value)

        return ""

    if isinstance(content, list):
        parts: list[str] = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue

            if isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str):
                    parts.append(block_text)
                    continue

                block_content = block.get("content")
                if isinstance(block_content, str):
                    parts.append(block_content)
                    continue

            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                parts.append(block_text)

        return "\n".join(parts)

    nested = getattr(content, "content", None)
    if nested is not None and nested is not content:
        return _extract_text_content(nested)

    return ""


def _sanitize_user_response(
    response: Any,
) -> str:
    """
    Final safety boundary for all LLM-generated customer-facing text.

    Reasoning such as Qwen <think>...</think> must never reach the
    frontend. This function also removes common markdown/code wrappers
    that can accidentally expose an internal structured response.

    It does NOT alter normal user-facing content.
    """
    text = _extract_text_content(response).strip()

    if not text:
        return ""

    # Remove complete reasoning blocks.
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove an unmatched reasoning block.
    text = re.sub(
        r"<think>.*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove other common hidden-reasoning wrappers if a model emits them.
    text = re.sub(
        r"<analysis>.*?</analysis>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<analysis>.*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove a leading assistant/final label if emitted by a model.
    text = re.sub(
        r"^\s*(?:final\s+answer|assistant\s*:)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove surrounding markdown fences when the entire response is
    # accidentally wrapped as a code block.
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            lines = lines[1:-1]
            text = "\n".join(lines).strip()

    return text.strip()


def _get_entities(
    state: GraphState,
) -> dict[str, Any]:
    """
    Return entity state safely.
    """

    entities = state.get(
        "entities",
        {},
    )

    if not isinstance(
        entities,
        dict,
    ):
        return {}

    return dict(
        entities
    )


def _get_tool_result(
    state: GraphState,
) -> dict[str, Any] | None:
    """
    Return tool result when it is a dictionary.
    """

    result = state.get(
        "tool_result"
    )

    if not isinstance(
        result,
        dict,
    ):
        return None

    return result


# =========================================================
# Graph-Controlled Checkout State
# =========================================================
#
# IMPORTANT:
#
# Phase 1 allowed Response Node to calculate checkout state.
#
# Phase 2 does NOT.
#
# Planner / policy / decision / graph orchestration is responsible
# for determining workflow state.
#
# Response Node only consumes:
#
#     missing_fields
#     next_missing
#
# supplied by the graph.
#
# =========================================================


def _get_missing_fields(
    state: GraphState,
) -> list[str]:
    """
    Read graph-produced missing fields.

    The Response Node does not recompute checkout requirements.
    """

    raw = state.get(
        "missing_fields",
        [],
    )

    if not isinstance(
        raw,
        (list, tuple),
    ):
        return []

    result: list[str] = []

    for field in raw:

        if not isinstance(
            field,
            str,
        ):
            continue

        field = field.strip()

        if not field:
            continue

        if field not in result:
            result.append(
                field
            )

    return result


def _get_next_missing(
    state: GraphState,
    missing_fields: list[str],
) -> str | None:
    """
    Read graph-produced next_missing.

    For compatibility, if next_missing is absent, use the first
    graph-provided missing field.

    This is NOT a workflow calculation.
    It is only a compatibility fallback.
    """

    next_missing = state.get(
        "next_missing"
    )

    if isinstance(
        next_missing,
        str,
    ):

        next_missing = next_missing.strip()

        if next_missing:
            return next_missing

    if missing_fields:
        return missing_fields[0]

    return None


# =========================================================
# Planner / Policy / Decision Context
# =========================================================


def _get_planner_context(
    state: GraphState,
) -> dict[str, Any]:
    """
    Collect Phase-2 orchestration state.

    This information is supplied to the LLM as context only.

    The Response Node does not reinterpret or override it.
    """

    planner = state.get(
        "planner"
    )

    policy = state.get(
        "policy"
    )

    decision = state.get(
        "decision"
    )

    planner_args = state.get(
        "planner_args"
    )

    tool_args = state.get(
        "tool_args"
    )

    context: dict[str, Any] = {}

    if isinstance(
        planner,
        dict,
    ):
        context[
            "planner"
        ] = planner

    if isinstance(
        policy,
        dict,
    ):
        context[
            "policy"
        ] = policy

    if isinstance(
        decision,
        dict,
    ):
        context[
            "decision"
        ] = decision

    if isinstance(
        planner_args,
        dict,
    ):
        context[
            "planner_args"
        ] = planner_args

    if isinstance(
        tool_args,
        dict,
    ):
        context[
            "tool_args"
        ] = tool_args

    return context


# =========================================================
# Payment Methods
# =========================================================


def _get_payment_methods(
    tool_result: Any,
) -> list[dict[str, Any]]:
    """
    Read payment methods dynamically from the backend/tool result.

    Nothing is hardcoded here.
    """

    if not isinstance(
        tool_result,
        dict,
    ):
        return []

    methods = tool_result.get(
        "methods"
    )

    if not isinstance(
        methods,
        list,
    ):
        return []

    return methods


# =========================================================
# Address Data
# =========================================================


def _get_addresses(
    tool_result: Any,
) -> tuple[
    list[Any],
    bool,
    Any,
]:
    """
    Extract address-selection information from the backend result.

    Returns:

        addresses
        allow_new
        prefill
    """

    if not isinstance(
        tool_result,
        dict,
    ):
        return (
            [],
            True,
            None,
        )

    result_type = tool_result.get(
        "type"
    )

    if result_type not in {
        "address_selection",
        "saved_addresses",
    }:
        return (
            [],
            True,
            None,
        )

    addresses = tool_result.get(
        "addresses",
        [],
    )

    if not isinstance(
        addresses,
        list,
    ):
        addresses = []

    allow_new = bool(
        tool_result.get(
            "allow_new",
            True,
        )
    )

    prefill = tool_result.get(
        "prefill"
    )

    return (
        addresses,
        allow_new,
        prefill,
    )


# =========================================================
# Checkout Response Prompt
# =========================================================


CHECKOUT_RESPONSE_SYSTEM_PROMPT = """
You are BuyQK AI.

You are responsible only for generating the user-facing wording.

The graph has already decided the workflow.

You MUST NOT:
- change checkout order
- select a different missing field
- decide whether an action is allowed
- invent business information
- invent products
- invent quantities
- invent addresses
- invent payment methods
- invent prices
- invent fees
- invent totals
- invent order IDs
- invent statuses

The graph provides:
- missing_fields
- next_missing

Treat these as authoritative workflow state.

Ask only for next_missing.

If backend/tool results provide options, use only those options.

Keep the response concise and natural.

Never mention:
- planner
- policy
- decision node
- tool node
- GraphState
- internal implementation
- prompts
- backend architecture
"""


def _generate_checkout_response(
    state: GraphState,
    missing_fields: list[str],
    next_missing: str | None,
    metadata: dict[str, Any],
) -> str:
    """
    Generate checkout wording deterministically.

    Checkout sequencing is graph-controlled. The Response Node must not
    ask an LLM to decide which field comes next.

    This also prevents model reasoning (<think>...</think>) from leaking
    into checkout responses.
    """
    entities = _get_entities(state)
    product_name = entities.get("product_name")

    if next_missing == "product_name":
        return "Which product would you like?"

    if next_missing == "quantity":
        if isinstance(product_name, str) and product_name.strip():
            return (
                f"How many packs of "
                f"{product_name.strip()} would you like?"
            )
        return "How many would you like?"

    if next_missing == "address_selection":
        return "Please select a delivery address."

    if next_missing == "payment_method":
        return "Please select a payment method."

    return _checkout_fallback(next_missing)


def _checkout_fallback(
    next_missing: str | None,
) -> str:
    """
    Deterministic operational fallback.

    This does not contain business values.
    """

    fallback_messages = {
        "product_name": (
            "Which product would you like?"
        ),
        "quantity": (
            "How many would you like?"
        ),
        "address_selection": (
            "Please select a delivery address."
        ),
        "payment_method": (
            "Please select a payment method."
        ),
    }

    return fallback_messages.get(
        next_missing,
        "Please provide the information needed to continue.",
    )


# =========================================================
# Checkout Metadata
# =========================================================


def _checkout_metadata(
    state: GraphState,
    missing_fields: list[str],
    next_missing: str | None,
) -> dict[str, Any] | None:
    """
    Generate frontend metadata from graph/tool state.

    This function does not determine workflow.
    It only maps the already-selected workflow step to UI metadata.
    """

    tool_result = _get_tool_result(
        state
    )

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    if next_missing == "product_name":

        return {
            "type": "product_input",
            "missing_field": "product_name",
            "missing_fields": missing_fields,
        }

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    if next_missing == "quantity":

        return {
            "type": "quantity_input",
            "missing_field": "quantity",
            "missing_fields": missing_fields,
        }

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    if next_missing == "address_selection":

        addresses, allow_new, prefill = (
            _get_addresses(
                tool_result
            )
        )

        metadata = {
            "type": "address_selection",
            "missing_field": "address_selection",
            "missing_fields": missing_fields,
            "addresses": addresses,
            "allow_new": allow_new,
        }
        if state.get("checkout_id"):
            metadata["checkout_id"] = state.get("checkout_id")

        if prefill is not None:
            metadata[
                "prefill"
            ] = prefill

        return metadata

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    if next_missing == "payment_method":

        methods = _get_payment_methods(
            tool_result
        )

        result = {
            "type": "payment_selection",
            "missing_field": "payment_method",
            "missing_fields": missing_fields,
            "methods": methods,
        }
        if state.get("checkout_id"):
            result["checkout_id"] = state.get("checkout_id")
        return result

    return None


# =========================================================
# Metadata Cleanup
# =========================================================


def _clean_checkout_metadata(
    metadata: Any,
    next_missing: str | None,
) -> dict[str, Any]:
    """
    Remove stale checkout UI metadata.

    Only presentation state is cleaned here.

    This does NOT change graph workflow.
    """

    if not isinstance(
        metadata,
        dict,
    ):
        return {}

    cleaned = dict(
        metadata
    )

    # -----------------------------------------------------
    # Never preserve unrelated checkout UI after completion
    # -----------------------------------------------------

    if next_missing is None:

        cleaned.pop(
            "address_selection",
            None,
        )

        cleaned.pop(
            "payment_selection",
            None,
        )

        if cleaned.get(
            "type"
        ) in {
            "product_input",
            "quantity_input",
            "address_selection",
            "payment_selection",
        }:

            cleaned.pop(
                "type",
                None,
            )

        return cleaned

    # -----------------------------------------------------
    # Product / quantity
    # -----------------------------------------------------

    if next_missing in {
        "product_name",
        "quantity",
    }:

        cleaned.pop(
            "address_selection",
            None,
        )

        cleaned.pop(
            "payment_selection",
            None,
        )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    elif next_missing == "address_selection":

        cleaned.pop(
            "payment_selection",
            None,
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    elif next_missing == "payment_method":

        cleaned.pop(
            "address_selection",
            None,
        )

    return cleaned


# =========================================================
# Greeting
# =========================================================


def _is_greeting(
    message: str,
) -> bool:
    """
    Detect simple greetings without requiring an LLM call.
    """

    normalized = (
        str(
            message
            or ""
        )
        .strip()
        .lower()
        .replace(
            "!",
            "",
        )
        .replace(
            ".",
            "",
        )
        .replace(
            ",",
            "",
        )
    )

    greetings = {
        "hi",
        "hii",
        "hiii",
        "hello",
        "hey",
        "heyy",
        "good morning",
        "good afternoon",
        "good evening",
        "namaste",
    }

    return normalized in greetings


# =========================================================
# General Fallback
# =========================================================


def _general_fallback(
    message: str,
) -> str:
    """
    Deterministic fallback for general conversation.
    """

    if _is_greeting(
        message
    ):

        return (
            "Hello! I'm BuyQK AI. "
            "How can I help you today?"
        )

    return (
        "Sure, I'm here to help. "
        "What would you like to do?"
    )


# =========================================================
# General Response Prompt
# =========================================================


GENERAL_SYSTEM_PROMPT = """
You are BuyQK AI, an intelligent shopping assistant.

Generate the final user-facing response from the supplied graph state.

The graph has already handled:
- intent
- planning
- policy
- decision making
- tool selection
- workflow

The backend/tool result is authoritative for transactional facts.

You MUST:
- use supplied backend values
- preserve order IDs
- preserve product IDs
- preserve quantities
- preserve prices
- preserve totals
- preserve payment methods
- preserve statuses
- preserve ticket IDs
- preserve address information
- explain backend results naturally

You MUST NOT:
- invent facts
- modify prices
- modify quantities
- invent discounts
- invent fees
- invent taxes
- invent totals
- invent payment methods
- invent order IDs
- invent statuses
- invent products
- invent addresses
- claim a transaction succeeded when the tool says it failed

For billing:
- prefer the authoritative bill
- present itemized information when supplied
- do not recalculate or replace backend totals
- if billing information is incomplete, only state what is available

For product search:
- use only returned products

For tracking:
- use only returned order status

For cancellation:
- use only returned cancellation result

For support:
- use only returned ticket information

For errors:
- explain the actual error when safe to expose
- do not expose internal implementation details

Keep responses concise and natural.

Return ONLY the user-facing response.
Never output <think>, <analysis>, chain-of-thought, internal reasoning,
planning notes, JSON, markdown code fences, or implementation details.
"""


# =========================================================
# LLM General Response
# =========================================================


def _generate_llm_response(
    state: GraphState,
) -> str:
    """
    Generate the final general response.

    This function is presentation-only.
    """

    context = {
        "user_message": state.get(
            "message",
            "",
        ),
        "intent": state.get(
            "intent",
            "general",
        ),
        "entities": _get_entities(
            state
        ),
        "tool_name": state.get(
            "tool_name"
        ),
        "tool_result": _get_tool_result(
            state
        ),
        "order_id": state.get(
            "order_id"
        ),
        "missing_fields": _get_missing_fields(
            state
        ),
        "next_missing": _get_next_missing(
            state,
            _get_missing_fields(
                state
            ),
        ),
        "selected_address_id": state.get(
            "selected_address_id"
        ),
        "payment_method": state.get(
            "payment_method"
        ),
        "orchestration": _get_planner_context(
            state
        ),
        "conversation_history": (
            state.get(
                "conversation_history",
                [],
            )
            or []
        ),
    }

    prompt = f"""
Generate the final user-facing BuyQK response.

Current state:

{_serialize_data(context)}

Remember:
- backend/tool data is authoritative
- graph workflow is authoritative
- do not invent missing information
- do not change workflow
- do not expose internal architecture
- return only the user-facing response
- never expose <think>, <analysis>, chain-of-thought, or internal reasoning
"""

    try:

        result = llm.invoke(
            [
                SystemMessage(
                    content=GENERAL_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        content = _sanitize_user_response(result)

        if content:
            return content

    except Exception as exc:

        print(
            "[RESPONSE LLM ERROR]"
            f" {type(exc).__name__}: {exc}"
        )

    return _general_fallback(
        state.get(
            "message",
            "",
        )
    )


# =========================================================
# Tool Result Response
# =========================================================


def _generate_tool_response(
    state: GraphState,
) -> str | None:
    """
    Generate a natural-language explanation of a tool result.

    The tool result is authoritative.

    The LLM is only responsible for wording.
    """

    tool_result = _get_tool_result(
        state
    )

    if tool_result is None:
        return None

    if "success" not in tool_result:
        return None

    context = {
        "user_message": state.get(
            "message",
            "",
        ),
        "intent": state.get(
            "intent",
            "general",
        ),
        "entities": _get_entities(
            state
        ),
        "tool_name": state.get(
            "tool_name"
        ),
        "tool_result": tool_result,
        "order_id": state.get(
            "order_id"
        ),
        "orchestration": _get_planner_context(
            state
        ),
        "conversation_history": (
            state.get(
                "conversation_history",
                [],
            )
            or []
        ),
    }

    prompt = f"""
Generate the final user-facing response from this BuyQK tool result.

State:

{_serialize_data(context)}

Rules:

1. Treat tool_result as authoritative.
2. If success is false, explain the failure clearly.
3. If an order was created:
   - use the supplied order ID
   - use the supplied bill
   - use the supplied items
   - use the supplied quantities
   - use the supplied prices
   - use the supplied subtotal
   - use the supplied delivery charge
   - use the supplied discount
   - use the supplied tax
   - use the supplied total
   - use the supplied currency
   - use the supplied payment method
   - use the supplied status
4. Never invent missing values.
5. Do not recalculate or override authoritative backend totals.
6. For tracking, report the supplied status.
7. For cancellation, report only the supplied result.
8. For support, report only the supplied ticket information.
9. For product search, use only returned products.
10. Do not mention internal implementation.

Return ONLY the user-facing response.
Never output <think>, <analysis>, chain-of-thought, internal reasoning,
planning notes, JSON, markdown code fences, or implementation details.
"""

    try:

        result = llm.invoke(
            [
                SystemMessage(
                    content=GENERAL_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        content = _sanitize_user_response(result)

        if content:
            return content

    except Exception as exc:

        print(
            "[TOOL RESPONSE LLM ERROR]"
            f" {type(exc).__name__}: {exc}"
        )

    return _tool_fallback(
        tool_result
    )


# =========================================================
# Tool Fallback
# =========================================================


def _tool_fallback(
    tool_result: dict[str, Any],
) -> str:
    """
    Deterministic fallback for tool responses.

    Uses only supplied values.
    """

    success = tool_result.get(
        "success"
    )

    result_type = tool_result.get(
        "type"
    )

    # -----------------------------------------------------
    # Failure
    # -----------------------------------------------------

    if success is False:

        error = (
            tool_result.get(
                "error"
            )
            or tool_result.get(
                "message"
            )
        )

        if error:
            return str(
                error
            )

        return (
            "I couldn't complete that request."
        )

    # -----------------------------------------------------
    # Order
    # -----------------------------------------------------

    if result_type == "order_success":

        order_id = tool_result.get(
            "order_id"
        )

        status = tool_result.get(
            "status"
        )

        payment_method = tool_result.get(
            "payment_method"
        )

        parts = [
            "Your order has been placed."
        ]

        if order_id is not None:

            parts.append(
                f"Order ID: #{order_id}."
            )

        if status is not None:

            parts.append(
                f"Status: {status}."
            )

        if payment_method is not None:

            parts.append(
                f"Payment: {payment_method}."
            )

        return " ".join(
            parts
        )

    # -----------------------------------------------------
    # Tracking
    # -----------------------------------------------------

    if result_type == "tracking":

        order_id = tool_result.get(
            "order_id"
        )

        status = tool_result.get(
            "status"
        )

        if (
            order_id is not None
            and status is not None
        ):

            return (
                f"Your order #{order_id} "
                f"is currently {status}."
            )

        if status is not None:

            return (
                f"Your order is currently "
                f"{status}."
            )

        return (
            "I found the order information, "
            "but no current status was provided."
        )

    # -----------------------------------------------------
    # Cancellation
    # -----------------------------------------------------

    if result_type == "order_cancelled":

        order_id = tool_result.get(
            "order_id"
        )

        if order_id is not None:

            return (
                f"Order #{order_id} "
                "has been cancelled."
            )

        return (
            "The order has been cancelled."
        )

    # -----------------------------------------------------
    # Support
    # -----------------------------------------------------

    if result_type == "support_ticket":

        ticket_id = tool_result.get(
            "ticket_id"
        )

        if ticket_id is not None:

            return (
                "Your support request has been "
                f"created. Ticket ID: #{ticket_id}."
            )

        return (
            "Your support request has been created."
        )

    # -----------------------------------------------------
    # Product search
    # -----------------------------------------------------

    if result_type == "product_search":

        products = tool_result.get(
            "products",
            [],
        )

        if isinstance(
            products,
            list
        ) and products:

            return (
                "I found matching products for you."
            )

        return (
            "I couldn't find matching products."
        )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    if result_type == "address_selection":

        return (
            "Please select a delivery address."
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    if result_type == "payment_selection":

        return (
            "Please select a payment method."
        )

    return (
        "The request was completed."
    )


# =========================================================
# Product Metadata
# =========================================================


def _product_metadata(
    tool_result: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    """
    Convert backend product-search data into frontend metadata.

    No product selection or scoring happens here.
    """

    products = tool_result.get(
        "products",
        [],
    )

    if not isinstance(
        products,
        list,
    ):
        products = []

    normalized_products: list[
        dict[str, Any]
    ] = []

    for product in products:

        if isinstance(
            product,
            dict,
        ):

            normalized_products.append(
                dict(product)
            )

            continue

        normalized_products.append(
            {
                "id": getattr(
                    product,
                    "id",
                    None,
                ),
                "name": getattr(
                    product,
                    "name",
                    None,
                ),
                "description": getattr(
                    product,
                    "description",
                    None,
                ),
                "brand": getattr(
                    product,
                    "brand",
                    None,
                ),
                "price": getattr(
                    product,
                    "price",
                    None,
                ),
                "stock": getattr(
                    product,
                    "stock",
                    None,
                ),
                "merchant_id": getattr(
                    product,
                    "merchant_id",
                    None,
                ),
                "category_id": getattr(
                    product,
                    "category_id",
                    None,
                ),
                "image_url": getattr(
                    product,
                    "image_url",
                    None,
                ),
            }
        )

    return {
        "type": "product_results",
        "products": normalized_products,
        "missing_fields": missing_fields,
    }


# =========================================================
# Order Metadata
# =========================================================


def _order_success_metadata(
    state: GraphState,
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build frontend metadata for a successful order.

    Every transactional value comes directly from the backend/tool
    result.
    """

    order_id = tool_result.get(
        "order_id"
    )

    bill = tool_result.get(
        "bill"
    )

    purchase_summary = tool_result.get(
        "purchase_summary"
    )

    metadata = {
        "type": "order_success",
        "checkout_id": (
            tool_result.get("checkout_id")
            or state.get("checkout_id")
        ),
        "order_id": order_id,
        "status": tool_result.get(
            "status"
        ),
        "payment_status": tool_result.get(
            "payment_status"
        ),
        "payment_method": tool_result.get(
            "payment_method"
        ),
        "total_amount": tool_result.get(
            "total_amount"
        ),
        "currency": (
            bill.get(
                "currency"
            )
            if isinstance(
                bill,
                dict,
            )
            else None
        ),
        "bill": bill,
        "purchase_summary": purchase_summary,
        "can_track": (
            order_id is not None
        ),
    }

    return metadata


# =========================================================
# Generic Tool Metadata
# =========================================================


def _tool_metadata(
    state: GraphState,
    missing_fields: list[str],
) -> dict[str, Any]:
    """
    Preserve useful tool data for the frontend.

    This is presentation metadata only.
    """

    tool_result = _get_tool_result(
        state
    )

    if tool_result is None:
        return {}

    result_type = tool_result.get(
        "type"
    )

    if result_type == "order_success":

        return _order_success_metadata(
            state,
            tool_result,
        )

    if result_type == "tracking":

        return {
            "type": "tracking",
            "order_id": tool_result.get(
                "order_id"
            ),
            "status": tool_result.get(
                "status"
            ),
            "payment_status": tool_result.get(
                "payment_status"
            ),
            "bill": tool_result.get(
                "bill"
            ),
        }

    if result_type == "order_cancelled":

        return {
            "type": "order_cancelled",
            "order_id": tool_result.get(
                "order_id"
            ),
            "status": tool_result.get(
                "status"
            ),
        }

    if result_type == "support_ticket":

        return {
            "type": "support_ticket",
            "ticket_id": tool_result.get(
                "ticket_id"
            ),
            "status": tool_result.get(
                "status"
            ),
        }

    if result_type == "product_search":

        return _product_metadata(
            tool_result,
            missing_fields,
        )

    if result_type == "address_selection":

        addresses, allow_new, prefill = (
            _get_addresses(
                tool_result
            )
        )

        metadata = {
            "type": "address_selection",
            "addresses": addresses,
            "allow_new": allow_new,
            "missing_fields": missing_fields,
        }

        if prefill is not None:
            metadata[
                "prefill"
            ] = prefill

        return metadata

    if result_type == "payment_selection":

        return {
            "type": "payment_selection",
            "methods": _get_payment_methods(
                tool_result
            ),
            "missing_fields": missing_fields,
        }

    return {
        "tool_type": result_type,
        "missing_fields": missing_fields,
    }



# =========================================================
# Cart Presentation Helpers
# =========================================================

def _get_cart(tool_result: Any) -> dict[str, Any] | None:
    """Return the authoritative cart payload from a tool result."""
    if not isinstance(tool_result, dict):
        return None

    cart = tool_result.get("cart")
    if isinstance(cart, dict):
        return cart

    return None


def _cart_metadata(
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build frontend cart metadata exclusively from authoritative
    Tool Node / Cart Service output.

    This function never calculates totals, prices, or quantities.
    """
    cart = _get_cart(tool_result)

    metadata: dict[str, Any] = {
        "type": "cart",
        "action": tool_result.get("action"),
    }

    if cart is not None:
        metadata["cart"] = cart

    # Preserve checkout information when checkout_cart was used.
    if tool_result.get("type") == "cart_checkout_ready":
        metadata.update(
            {
                "type": "cart_checkout_ready",
                "checkout_id": tool_result.get("checkout_id"),
                "checkout_status": tool_result.get(
                    "checkout_status"
                ),
                "order_created": False,
            }
        )

    return metadata


def _cart_fallback(
    tool_result: dict[str, Any],
) -> str:
    """
    Deterministic fallback for cart operations.

    Every transactional/cart value comes from the Tool Node result.
    No totals or quantities are calculated here.
    """
    success = tool_result.get("success")
    result_type = tool_result.get("type")
    action = tool_result.get("action")
    cart = _get_cart(tool_result)

    if success is False:
        return str(
            tool_result.get("error")
            or tool_result.get("message")
            or "I couldn't complete that cart request."
        )

    if result_type == "cart_checkout_ready":
        return (
            "Your cart is ready for checkout. "
            "Let's continue with checkout."
        )

    if result_type == "cart_cleared":
        return "Your cart has been cleared."

    if result_type == "cart":
        if isinstance(cart, dict):
            items = cart.get("items")
            if isinstance(items, list) and not items:
                return "Your cart is empty."
        return "Here is your current cart."

    if result_type == "cart_updated":
        messages = {
            "add_item": "The item has been added to your cart.",
            "remove_item": "The item has been removed from your cart.",
            "update_quantity": "Your cart quantity has been updated.",
        }
        return messages.get(
            action,
            "Your cart has been updated.",
        )

    return "Your cart request was completed."


def _cart_tool_metadata(
    tool_result: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    """Return cart metadata while preserving graph checkout fields."""
    metadata = _cart_metadata(tool_result)
    metadata["missing_fields"] = missing_fields
    return metadata



# =========================================================
# Response Node
# =========================================================

def response_node(
    state: GraphState,
) -> GraphState:
    """
    Final presentation node.

    The Response Node:
        - consumes graph/tool state
        - presents authoritative backend results
        - generates user-facing wording
        - builds frontend metadata

    It does NOT:
        - select tools
        - enforce policy
        - calculate checkout state
        - calculate prices/taxes/fees/totals
        - resolve products
        - validate business facts
        - create orders
        - mutate backend state

    Phase 3 addition:
        Cart operations are presentation-only here. Cart truth comes
        exclusively from Tool Node / Cart Service output.
    """

    intent = state.get("intent", "general")
    tool_name = state.get("tool_name")
    message = str(state.get("message", "") or "")
    tool_result = _get_tool_result(state)

    missing_fields = _get_missing_fields(state)
    next_missing = _get_next_missing(
        state,
        missing_fields,
    )

    metadata = dict(
        state.get("metadata", {}) or {}
    )

    # ---------------------------------------------------------
    # Preserve graph-controlled checkout state.
    # ---------------------------------------------------------
    metadata["missing_fields"] = missing_fields

    if next_missing is not None:
        metadata["next_missing"] = next_missing
    else:
        metadata.pop("next_missing", None)

    # ---------------------------------------------------------
    # 1. Successful order
    #
    # Must be handled before any checkout UI so an already-created
    # order can never be presented as an unfinished checkout.
    # ---------------------------------------------------------
    if (
        isinstance(tool_result, dict)
        and tool_result.get("success") is True
        and tool_result.get("type") == "order_success"
    ):
        order_id = tool_result.get("order_id")

        order_metadata = _order_success_metadata(
            state,
            tool_result,
        )

        # Order success is transactional output. Do not spend another
        # LLM call just to paraphrase it; this also keeps checkout usable
        # when the LLM provider is rate-limited.
        response = _tool_fallback(tool_result)
        response = _sanitize_user_response(response)

        return {
            "response": response,
            "metadata": order_metadata,
            "missing_fields": [],
            "next_missing": None,
            "order_id": order_id,
            "checkout_status": "completed",
            "order_created": True,
            "awaiting_order_tracking_confirmation": (
                order_id is not None
            ),
        }

    # ---------------------------------------------------------
    # 2. Phase 3 cart results
    #
    # These MUST be handled before generic tool rendering so the
    # frontend receives the cart itself and checkout transition
    # metadata.
    # ---------------------------------------------------------
    cart_result_types = {
        "cart_updated",
        "cart_cleared",
        "cart",
        "cart_checkout_ready",
    }

    if (
        isinstance(tool_result, dict)
        and tool_result.get("type") in cart_result_types
    ):
        if tool_result.get("success") is False:
            response = _cart_fallback(tool_result)
            cart_metadata = _cart_tool_metadata(
                tool_result,
                missing_fields,
            )
        else:
            response = _generate_tool_response(state)

            if not response:
                response = _cart_fallback(tool_result)

            cart_metadata = _cart_tool_metadata(
                tool_result,
                missing_fields,
            )

        # A cart operation must not leave stale address/payment UI
        # from a previous checkout presentation.
        cart_metadata = _clean_checkout_metadata(
            cart_metadata,
            next_missing,
        )

        cart_metadata["missing_fields"] = missing_fields

        if next_missing is not None:
            cart_metadata["next_missing"] = next_missing
        else:
            cart_metadata.pop("next_missing", None)

        response = _sanitize_user_response(response)

        if not response:
            response = _cart_fallback(tool_result)

        result: dict[str, Any] = {
            "response": response,
            "metadata": cart_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

        # checkout_cart starts checkout but does not create an order.
        if tool_result.get("type") == "cart_checkout_ready":
            result.update(
                {
                    "checkout_id": tool_result.get(
                        "checkout_id"
                    ),
                    "checkout_status": tool_result.get(
                        "checkout_status",
                        "active",
                    ),
                    "order_created": False,
                }
            )

        return result

    # ---------------------------------------------------------
    # 3. Checkout UI
    #
    # The graph has already selected next_missing.
    # Response Node only renders it.
    # ---------------------------------------------------------
    checkout_metadata = _checkout_metadata(
        state,
        missing_fields,
        next_missing,
    )

    if checkout_metadata is not None:
        checkout_metadata = _clean_checkout_metadata(
            checkout_metadata,
            next_missing,
        )

        metadata.update(checkout_metadata)

        response = _sanitize_user_response(
            _generate_checkout_response(
                state,
                missing_fields,
                next_missing,
                metadata,
            )
        )

        return {
            "response": response,
            "metadata": metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
            "checkout_id": state.get("checkout_id"),
            "checkout_status": state.get("checkout_status"),
            "order_created": bool(state.get("order_created", False)),
        }

    # ---------------------------------------------------------
    # 4. Tracking
    # ---------------------------------------------------------
    if (
        isinstance(tool_result, dict)
        and tool_result.get("success") is True
        and tool_result.get("type") == "tracking"
    ):
        response = _generate_tool_response(state)

        if not response:
            response = _tool_fallback(tool_result)

        tracking_metadata = _tool_metadata(
            state,
            missing_fields,
        )

        response = _sanitize_user_response(response)

        if not response:
            response = _tool_fallback(tool_result)

        return {
            "response": response,
            "metadata": tracking_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
            "order_id": tool_result.get("order_id"),
            "awaiting_order_tracking_confirmation": False,
        }

    # ---------------------------------------------------------
    # 7. Product search
    #
    # Kept explicit because product results have dedicated UI
    # metadata.
    # ---------------------------------------------------------
    if tool_name == "search_products":
        products: list[Any] = []

        if isinstance(tool_result, dict):
            raw_products = tool_result.get(
                "products",
                [],
            )
            if isinstance(raw_products, list):
                products = raw_products

        if isinstance(tool_result, dict):
            product_metadata = _product_metadata(
                tool_result,
                missing_fields,
            )
        else:
            product_metadata = {
                "type": "product_results",
                "products": [],
                "missing_fields": missing_fields,
            }

        if products:
            response = _generate_tool_response(state)
            if not response:
                response = "I found these products for you."
        else:
            response = "I couldn't find matching products."

        response = _sanitize_user_response(response)

        if not response:
            response = (
                "I found these products for you."
                if products
                else "I couldn't find matching products."
            )

        return {
            "response": response,
            "metadata": product_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }


    # ---------------------------------------------------------
    # Policy failure
    #
    # NOTE (fix): policy_error is now written fresh on every turn by
    # decision_node (including an explicit None when there is no
    # rejection). Do not read any other key for this, and do not
    # remove decision_node's unconditional policy_error write —
    # doing so reintroduces stale rejections leaking into later,
    # unrelated turns (e.g. a plain "Hi" showing a checkout error
    # left over from an earlier failed transaction in the same
    # session).
    # ---------------------------------------------------------
    policy_error = state.get("policy_error")
    if isinstance(policy_error, dict) and policy_error.get("allowed") is False:
        reason = str(policy_error.get("reason") or "").strip().lower()
        policy_messages = {
            "missing_checkout_id": "The checkout session is missing. Please restart your checkout so I can place the order safely.",
            "checkout_already_completed": "This checkout has already been completed.",
            "checkout_incomplete": "The checkout is not complete yet. Please provide the remaining checkout details.",
        }
        response = policy_messages.get(
            reason,
            "I couldn't continue with that transaction. Please provide the required checkout information.",
        )
        return {
            "response": response,
            "metadata": _clean_checkout_metadata(metadata, next_missing),
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

    # ---------------------------------------------------------
    # 5. Tool failure
    #
    # Never ask the LLM to rewrite a transactional failure into
    # an apparent success.
    # ---------------------------------------------------------
    if (
        isinstance(tool_result, dict)
        and tool_result.get("success") is False
    ):
        if tool_result.get("type") in cart_result_types:
            response = _cart_fallback(tool_result)
        else:
            error = (
                tool_result.get("error")
                or tool_result.get("message")
            )
            response = (
                str(error)
                if error
                else "I couldn't complete that request."
            )

        failure_metadata = _clean_checkout_metadata(
            metadata,
            next_missing,
        )

        failure_metadata["missing_fields"] = missing_fields

        if next_missing is not None:
            failure_metadata["next_missing"] = next_missing
        else:
            failure_metadata.pop("next_missing", None)

        response = _sanitize_user_response(response)

        if not response:
            response = (
                str(
                    tool_result.get("error")
                    or tool_result.get("message")
                    or "I couldn't complete that request."
                )
            )

        return {
            "response": response,
            "metadata": failure_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

    # ---------------------------------------------------------
    # 6. Other successful tool results
    # ---------------------------------------------------------
    if (
        isinstance(tool_result, dict)
        and tool_result.get("success") is True
    ):
        response = _generate_tool_response(state)

        if not response:
            response = _tool_fallback(tool_result)

        tool_metadata = _tool_metadata(
            state,
            missing_fields,
        )

        tool_metadata = _clean_checkout_metadata(
            tool_metadata,
            next_missing,
        )

        tool_metadata["missing_fields"] = missing_fields

        if next_missing is not None:
            tool_metadata["next_missing"] = next_missing
        else:
            tool_metadata.pop("next_missing", None)

        response = _sanitize_user_response(response)

        if not response:
            response = _tool_fallback(tool_result)

        return {
            "response": response,
            "metadata": tool_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

    # ---------------------------------------------------------
    # 8. Greeting
    # ---------------------------------------------------------
    if (
        intent == "general"
        and _is_greeting(message)
    ):
        return {
            "response": (
                "Hello! I'm BuyQK AI. "
                "How can I help you today?"
            ),
            "metadata": {},
            "missing_fields": [],
            "next_missing": None,
        }

    # ---------------------------------------------------------
    # 9. General conversation
    # ---------------------------------------------------------
    response = _sanitize_user_response(
        _generate_llm_response(state)
    )

    if not response:
        response = _general_fallback(message)

    metadata = _clean_checkout_metadata(
        metadata,
        next_missing,
    )

    metadata["missing_fields"] = missing_fields

    if next_missing is not None:
        metadata["next_missing"] = next_missing
    else:
        metadata.pop("next_missing", None)

    return {
        "response": response,
        "metadata": metadata,
        "missing_fields": missing_fields,
        "next_missing": next_missing,
    }