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

    # Phase 3 cart capabilities.
    "add_to_cart",
    "remove_from_cart",
    "update_cart_item",
    "clear_cart",
    "show_cart",
    "checkout_cart",

    # Phase 7A address capability.
    "add_new_address",
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
# Phase 3: Cart Action → Planner Capability
# =========================================================


CART_ACTION_TO_CAPABILITY: dict[str, str] = {
    "add_item": "add_to_cart",
    "remove_item": "remove_from_cart",
    "update_quantity": "update_cart_item",
    "clear_cart": "clear_cart",
    "show_cart": "show_cart",
    "checkout": "checkout_cart",
}


def _cart_capability_from_state(
    state: dict[str, Any],
) -> str | None:
    """Map explicit entity understanding to a cart capability."""

    intent = str(
        state.get("intent") or ""
    ).strip().lower()

    if intent != "cart":
        return None

    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    cart_action = entities.get("cart_action")

    if not isinstance(cart_action, str):
        cart_action = state.get("cart_action")

    if not isinstance(cart_action, str):
        return None

    cart_action = (
        cart_action.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return CART_ACTION_TO_CAPABILITY.get(cart_action)


def _build_cart_arguments(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Build safe arguments from already-understood state.

    No database lookup, stock check, price calculation, or
    cart mutation occurs here.
    """

    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    arguments: dict[str, Any] = {}

    product_name = entities.get("product_name") or state.get("product_name")
    if product_name:
        arguments["product_name"] = product_name

    quantity = entities.get("quantity")
    if quantity is None:
        quantity = state.get("quantity")
    if quantity is not None:
        try:
            quantity = int(quantity)
            if quantity > 0:
                arguments["quantity"] = quantity
        except (TypeError, ValueError):
            pass

    # Preserve only already-resolved backend values.
    product_id = entities.get("product_id")
    if product_id is not None:
        try:
            product_id = int(product_id)
            if product_id > 0:
                arguments["product_id"] = product_id
        except (TypeError, ValueError):
            pass

    cart_id = state.get("cart_id")
    if cart_id is not None:
        arguments["cart_id"] = cart_id

    return arguments


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

    if action is not None:
        action_aliases = {
            "add_cart_item": "add_to_cart",
            "remove_cart_item": "remove_from_cart",
            "update_cart_item": "update_cart_item",
            "clear_cart": "clear_cart",
            "show_cart": "show_cart",
            "checkout_cart": "checkout_cart",
            "search_product": "search_products",
        }
        action = action_aliases.get(action, action)

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
                action = {
                    "add_cart_item": "add_to_cart",
                    "remove_cart_item": "remove_from_cart",
                    "update_cart_item": "update_cart_item",
                    "clear_cart": "clear_cart",
                    "show_cart": "show_cart",
                    "checkout_cart": "checkout_cart",
                    "search_product": "search_products",
                }.get(action, action)
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
    if isinstance(conversation_history, list):
        # The planner needs recent conversational context, not the entire
        # transcript. Keeping a bounded window prevents provider TPM
        # failures while retaining follow-up context.
        conversation_history = conversation_history[-6:]

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

    cart_state = {
        "cart_id": state.get("cart_id"),
        "cart_status": state.get("cart_status"),
        "cart_items": (
            state.get("cart_items", [])[-20:]
            if isinstance(state.get("cart_items", []), list)
            else []
        ),
        "cart_summary": state.get("cart_summary"),
        "cart_action": (
            entities.get("cart_action")
            if isinstance(entities, dict)
            else state.get("cart_action")
        ),
        "cart_checkout_ready": state.get(
            "cart_checkout_ready",
            False,
        ),
    }

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
        "address_id": state.get(
            "address_id"
        ) or state.get("selected_address_id"),
        "delivery_preference": state.get(
            "delivery_preference"
        ),
        "selected_payment_method": state.get(
            "selected_payment_method"
        ) or state.get("payment_method"),
        "order_created": state.get(
            "order_created"
        ),
        "order_id": state.get(
            "order_id"
        ),
        "bill": state.get(
            "bill"
        ),
        "cancellation_eligibility": state.get("cancellation_eligibility"),
        "cancellation_reason": state.get("cancellation_reason"),
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
        "cart": cart_state,
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

CHECKOUT CONTINUITY RULE:

When an active checkout is present, preserve these already-understood
checkout values in the execution plan when they are available:

- checkout_id
- address_id
- delivery_preference
- selected_payment_method

These values are state/context values, not values to calculate or invent.
Prefer backend-resolved/state values over anything newly invented by the
planner model. The planner must not calculate delivery charges, choose
delivery availability, or convert a delivery preference into a backend
delivery option.

For order creation, carry the available checkout values into arguments so
downstream Policy/Decision/Tool layers receive the complete order context.
If a value is absent, leave it absent; do not fabricate it.

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

CANCELLATION PLANNING RULE:

For order cancellation:
- specific order IDs/references come only from entity/state
- latest/previous order references must be passed through for backend resolution
- do not decide cancellation eligibility
- do not invent a cancellation reason
- if the user has supplied a cancellation_reason, preserve it exactly
- the Tool Node/backend owns eligibility and cancellation execution

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

- request_support

Phase 3 cart capabilities:

- add_to_cart
- remove_from_cart
- update_cart_item
- clear_cart
- show_cart
- checkout_cart

Phase 7A address capability:

- add_new_address

When the user explicitly asks to add a new delivery address, use
add_new_address only when address_action is "add". Pass only address
fields already present in the supplied state. Never invent address data.

CART PLANNING RULE:

When intent is "cart", map cart_action as follows:

add_item
→ add_to_cart

remove_item
→ remove_from_cart

update_quantity
→ update_cart_item

clear_cart
→ clear_cart

show_cart
→ show_cart

checkout
→ checkout_cart

For cart operations:
- pass product_name only when already understood.
- pass quantity only when already understood.
- pass product_id only when already backend-resolved.
- pass cart_id only when already present.
- never invent product_id or cart_id.
- never calculate prices, totals, stock, or discounts.
- never execute the cart operation.
- never claim that the cart was modified.

If intent is "cart" but cart_action is missing or ambiguous,
use ask_clarification.

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

def _deterministic_plan_fallback(state: dict[str, Any]) -> dict[str, Any]:
    """Safe planner fallback for LLM outages/rate limits.

    Entity/understanding state is already available; this function only
    maps that state to the canonical workflow capability.
    """
    intent = str(state.get("intent") or "general").strip().lower()
    entities = state.get("entities", {}) or {}
    missing = list(state.get("missing_fields", []) or [])

    # =====================================================
    # CART FALLBACK
    # =====================================================
    #
    # If the planner LLM is unavailable, an already-resolved
    # Cart intent/action must still map deterministically to
    # the canonical Cart capability.
    #
    # This function only creates a plan. It never calls a
    # CartService method and never mutates backend state.
    # =====================================================

    if intent == "cart":
        cart_capability = _cart_capability_from_state(state)

        if cart_capability is None:
            return {
                "action": "ask_clarification",
                "tool_name": "ask_clarification",
                "arguments": {},
                "missing_fields": ["cart_action"],
                "confidence": 0.0,
                "reason": (
                    "Cart intent was understood, but the Cart action "
                    "could not be resolved."
                ),
            }

        arguments = _build_cart_arguments(state)
        cart_missing_fields: list[str] = []

        if cart_capability in {
            "add_to_cart",
            "update_cart_item",
        }:
            if not (
                arguments.get("product_name")
                or arguments.get("product_id")
            ):
                cart_missing_fields.append("product_reference")

            if "quantity" not in arguments:
                cart_missing_fields.append("quantity")

        elif cart_capability == "remove_from_cart":
            if not (
                arguments.get("product_name")
                or arguments.get("product_id")
            ):
                cart_missing_fields.append("product_reference")

        if cart_missing_fields:
            return {
                "action": "ask_clarification",
                "tool_name": "ask_clarification",
                "arguments": arguments,
                "missing_fields": cart_missing_fields,
                "confidence": 0.0,
                "reason": (
                    "Deterministic Cart fallback requires "
                    "additional information."
                ),
            }

        return {
            "action": cart_capability,
            "tool_name": cart_capability,
            "arguments": arguments,
            "missing_fields": [],
            "confidence": 0.0,
            "reason": (
                "Deterministic Cart fallback used because "
                "the planner model was unavailable."
            ),
        }

    # =====================================================
    # ORDER CREATE FALLBACK
    # =====================================================

    if intent == "order_create":
        args = {}

        # Phase 7A: explicitly requested new-address flow.
        # This is conversational intent only; persistence happens in Tool.
        if str(entities.get("address_action") or "").strip().lower() == "add":
            for key in (
                "address_label",
                "address_text",
                "address_line_2",
                "address_city",
                "address_state",
                "address_postal_code",
            ):
                value = entities.get(key)
                if value is not None and str(value).strip():
                    args[key] = value

            required_address_fields = (
                "address_label",
                "address_text",
                "address_city",
                "address_state",
                "address_postal_code",
            )
            address_missing = [
                field
                for field in required_address_fields
                if not args.get(field)
            ]

            if address_missing:
                return {
                    "action": "ask_clarification",
                    "tool_name": "ask_clarification",
                    "arguments": args,
                    "missing_fields": address_missing,
                    "confidence": 0.0,
                    "reason": (
                        "A new delivery address was requested, but required "
                        "address information is missing."
                    ),
                }

            return {
                "action": "add_new_address",
                "tool_name": "add_new_address",
                "arguments": args,
                "missing_fields": [],
                "confidence": 0.0,
                "reason": "Deterministic new-address checkout flow.",
            }

        for key in (
            "product_name",
            "quantity",
            "address_id",
            "payment_method",
        ):
            value = entities.get(key)
            if value is not None:
                args[key] = value

        # Preserve already-resolved checkout context. These values are
        # carried forward only; the planner does not calculate or invent
        # transactional facts.
        checkout_values = {
            "checkout_id": state.get("checkout_id"),
            "address_id": (
                state.get("address_id")
                or state.get("selected_address_id")
            ),
            "delivery_preference": state.get(
                "delivery_preference"
            ),
            "selected_payment_method": (
                state.get("selected_payment_method")
                or state.get("payment_method")
            ),
        }

        for key, value in checkout_values.items():
            if value is not None and (
                not isinstance(value, str) or value.strip()
            ):
                args[key] = value

        if missing:
            return {
                "action": "start_checkout",
                "tool_name": None,
                "arguments": args,
                "missing_fields": missing,
                "confidence": 0.0,
                "reason": (
                    "Deterministic checkout fallback used because "
                    "the planner model was unavailable."
                ),
            }

        return {
            "action": "create_order",
            "tool_name": "create_order",
            "arguments": args,
            "missing_fields": [],
            "confidence": 0.0,
            "reason": (
                "Deterministic order-creation fallback used because "
                "the planner model was unavailable."
            ),
        }

    if intent == "order_cancel":
        arguments: dict[str, Any] = {}
        for key in (
            "order_id",
            "order_reference",
            "order_reference_type",
            "cancellation_reason",
        ):
            value = entities.get(key)
            if value is not None and (not isinstance(value, str) or value.strip()):
                arguments[key] = value

        if not (
            arguments.get("order_id")
            or arguments.get("order_reference")
            or arguments.get("order_reference_type") in {"latest", "previous"}
        ):
            return {
                "action": "ask_clarification",
                "tool_name": "ask_clarification",
                "arguments": {},
                "missing_fields": ["order_id"],
                "confidence": 0.0,
                "reason": "Cancellation requires an order reference.",
            }

        return {
            "action": "cancel_order",
            "tool_name": "cancel_order",
            "arguments": arguments,
            "missing_fields": [],
            "confidence": 0.0,
            "reason": "Deterministic cancellation plan used because the planner model was unavailable.",
        }

    if intent == "order_tracking":
        arguments: dict[str, Any] = {}
        for key in ("order_id", "order_reference", "order_reference_type"):
            value = entities.get(key)
            if value is not None and (not isinstance(value, str) or value.strip()):
                arguments[key] = value

        if not (
            arguments.get("order_id")
            or arguments.get("order_reference")
            or arguments.get("order_reference_type") in {"latest", "previous"}
        ):
            return {
                "action": "ask_clarification",
                "tool_name": "ask_clarification",
                "arguments": {},
                "missing_fields": ["order_id"],
                "confidence": 0.0,
                "reason": "Tracking requires an order reference.",
            }

        return {
            "action": "track_order",
            "tool_name": "track_order",
            "arguments": arguments,
            "missing_fields": [],
            "confidence": 0.0,
            "reason": "Deterministic tracking plan used because the planner model was unavailable.",
        }

    mapping = {
        "product_search": "search_products",
        "order_tracking": "track_order",
        "order_cancel": "cancel_order",
        "customer_support": "request_support",
    }
    action = mapping.get(intent, "answer")

    # Build arguments from already-understood entity state when the
    # planner LLM is unavailable. This prevents a provider failure from
    # dropping the current product and accidentally falling back to stale
    # or empty arguments. No product is invented here.
    arguments: dict[str, Any] = {}
    if intent == "product_search":
        product_name = entities.get("product_name")
        if isinstance(product_name, str) and product_name.strip():
            arguments["product_name"] = product_name.strip()

    if intent in {"order_tracking", "order_cancel"}:
        order_id = entities.get("order_id")
        if order_id is not None:
            try:
                normalized_order_id = int(order_id)
                if normalized_order_id > 0:
                    arguments["order_id"] = normalized_order_id
            except (TypeError, ValueError):
                pass

        if intent in {"order_tracking", "order_cancel"}:
            for key in ("order_reference", "order_reference_type"):
                value = entities.get(key)
                if value is not None and (not isinstance(value, str) or value.strip()):
                    arguments[key] = value

        if intent == "order_cancel":
            value = entities.get("cancellation_reason")
            if value is not None and (not isinstance(value, str) or value.strip()):
                arguments["cancellation_reason"] = value

    return {
        "action": action,
        "tool_name": action if action != "answer" else None,
        "arguments": arguments,
        "missing_fields": missing,
        "confidence": 0.0,
        "reason": "Deterministic planner fallback used because the planner model was unavailable.",
    }


def _preserve_checkout_arguments(
    state: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Preserve already-resolved checkout context in the planner arguments.

    The planner may carry authoritative state forward, but it must not
    calculate, invent, or mutate transactional values.
    """
    action = _normalize_action(plan.get("action"))
    if action not in {
        "start_checkout",
        "modify_checkout",
        "add_to_checkout",
        "create_order",
    }:
        return plan

    arguments = plan.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    merged_arguments = dict(arguments)

    authoritative_values = {
        "checkout_id": state.get("checkout_id"),
        "address_id": (
            state.get("address_id")
            or state.get("selected_address_id")
        ),
        "delivery_preference": state.get(
            "delivery_preference"
        ),
        "selected_payment_method": (
            state.get("selected_payment_method")
            or state.get("payment_method")
        ),
    }

    for key, value in authoritative_values.items():
        if value is not None and (
            not isinstance(value, str) or value.strip()
        ):
            merged_arguments[key] = value

    plan["arguments"] = merged_arguments
    return plan


def _preserve_tracking_arguments(
    state: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Carry already-understood tracking references into the tool plan."""
    action = _normalize_action(plan.get("action"))
    if action != "track_order":
        return plan

    arguments = plan.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    merged = dict(arguments)
    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    for key in ("order_id", "order_reference", "order_reference_type"):
        value = entities.get(key)
        if value is None:
            value = state.get(key)
        if value is not None and (not isinstance(value, str) or value.strip()):
            merged[key] = value

    plan["arguments"] = merged
    return plan



def _preserve_cancellation_arguments(
    state: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Carry order reference and user-provided reason into cancellation."""
    action = _normalize_action(plan.get("action"))
    if action != "cancel_order":
        return plan

    arguments = plan.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    merged = dict(arguments)

    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    for key in (
        "order_id",
        "order_reference",
        "order_reference_type",
        "cancellation_reason",
    ):
        value = entities.get(key)
        if value is None:
            value = state.get(key)
        if value is not None and (not isinstance(value, str) or value.strip()):
            merged[key] = value

    plan["arguments"] = merged
    return plan

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
    # Deterministic checkout orchestration
    # -----------------------------------------------------
    if str(state.get("intent") or "").strip().lower() == "order_create":
        plan = _deterministic_plan_fallback(state)
        result = {
            "planner": plan,
            "planner_args": dict(plan.get("arguments", {})),
            "missing_fields": list(plan.get("missing_fields", [])),
        }
        print("[AI PLANNER NODE] deterministic checkout plan")
        print(f"action          = {plan.get('action')!r}")
        print(f"arguments       = {plan.get('arguments')!r}")
        print(f"missing_fields  = {plan.get('missing_fields')!r}")
        print(f"checkout_id     = {state.get('checkout_id')!r}")
        return result

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

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        content = _get_content(response)
        raw_plan = _extract_json(content)
        plan = _normalize_plan(raw_plan)
    except Exception as exc:
        print(
            "[PLANNER LLM FALLBACK]"
            f" {type(exc).__name__}: {exc}"
        )
        plan = _deterministic_plan_fallback(state)

    # -----------------------------------------------------
    # Phase 3 cart capability enforcement
    # -----------------------------------------------------
    #
    # Explicit cart understanding from entity_node takes
    # precedence over a generic LLM planner action.
    # This prevents cart requests from becoming checkout/order
    # operations accidentally.
    #
    # No cart operation is executed here.
    # -----------------------------------------------------

    cart_capability = _cart_capability_from_state(
        state
    )

    if cart_capability is not None:

        llm_arguments = plan.get(
            "arguments",
            {},
        )

        if not isinstance(
            llm_arguments,
            dict,
        ):
            llm_arguments = {}

        cart_arguments = _build_cart_arguments(
            state
        )

        merged_arguments = dict(
            llm_arguments
        )

        for key, value in cart_arguments.items():
            merged_arguments[key] = value

        plan["action"] = cart_capability
        plan["tool_name"] = cart_capability
        plan["arguments"] = merged_arguments
        plan["reason"] = (
            "Mapped explicit cart understanding to the "
            "canonical cart capability."
        )

    elif (
        str(state.get("intent") or "").strip().lower()
        == "cart"
    ):
        plan["action"] = "ask_clarification"
        plan["tool_name"] = "ask_clarification"
        plan["arguments"] = {}
        plan["missing_fields"] = [
            "cart_action"
        ]
        plan["reason"] = (
            "Cart intent was understood, but the requested "
            "cart operation is ambiguous."
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
    # Preserve checkout context in the execution plan
    # -----------------------------------------------------
    #
    # These values are already understood/state-backed. Carry them
    # forward for checkout/order capabilities without calculating,
    # inventing, or mutating transactional facts.
    # -----------------------------------------------------

    plan = _preserve_checkout_arguments(
        state,
        plan,
    )

    plan = _preserve_tracking_arguments(
        state,
        plan,
    )
    plan = _preserve_cancellation_arguments(
        state,
        plan,
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
        f"address_id      = "
        f"{state.get('address_id') or state.get('selected_address_id')!r}"
    )

    print(
        f"delivery_pref   = "
        f"{state.get('delivery_preference')!r}"
    )

    print(
        f"payment_method  = "
        f"{state.get('selected_payment_method') or state.get('payment_method')!r}"
    )

    print(
        f"order_created   = "
        f"{state.get('order_created')!r}"
    )

    print(
        f"order_id        = "
        f"{state.get('order_id')!r}"
    )

    print(
        f"cart_action     = "
        f"{state.get('cart_action')!r}"
    )

    print(
        f"cart_capability = "
        f"{_cart_capability_from_state(state)!r}"
    )

    print("=" * 60)

    return result