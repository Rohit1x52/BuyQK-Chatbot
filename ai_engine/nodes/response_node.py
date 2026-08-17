# =========================================================
# BuyQK AI - Response Node
# =========================================================
#
# Purpose:
# Generate the final user-facing BuyQK response.
#
# Responsibilities:
# - Enforce sequential checkout
# - Generate natural language for general conversation
# - Keep backend/tool results authoritative
# - Generate frontend metadata
# - Prevent stale address/payment UI
#
# Checkout:
#
# Product
#    ↓
# Quantity
#    ↓
# Address
#    ↓
# Payment
#    ↓
# Create Order
#    ↓
# Order ID
#    ↓
# Track confirmation
#
# IMPORTANT:
#
# The response node controls PRESENTATION.
# The graph controls WORKFLOW.
# The backend controls TRANSACTIONAL TRUTH.
#
# Checkout questions are deterministic.
# The LLM is NOT allowed to decide checkout sequencing.
# =========================================================


from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# =========================================================
# LLM
# =========================================================

llm = get_llm()


# =========================================================
# Constants
# =========================================================

# These are workflow field keys, not business values.
# Product names, prices, payment methods, statuses, fees,
# addresses, and billing values are always supplied dynamically
# by the graph/backend/AI context.
CHECKOUT_FIELDS = (
    "product_name",
    "quantity",
    "address_selection",
    "payment_method",
)


# =========================================================
# Utility
# =========================================================


def _has_value(value: Any) -> bool:
    """
    Return True when a value is actually present.

    None and empty strings are missing.
    Numeric zero is considered a real value.
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _safe_int(value: Any) -> int | None:
    """
    Safely convert a value to an integer.
    """

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_data(
    data: Optional[dict[str, Any]],
) -> str:
    """
    Safely serialize graph state for the LLM.
    """

    if not data:
        return "{}"

    try:
        return json.dumps(
            data,
            default=str,
            ensure_ascii=False,
        )
    except Exception:
        return "{}"


# =========================================================
# Address Resolution
# =========================================================


def _get_selected_address_id(
    state: GraphState,
    entities: dict[str, Any],
) -> int | None:
    """
    Resolve the currently selected delivery address.

    Priority:

        1. Explicit frontend selected_address_id
        2. entities.address_id
    """

    selected_address_id = _safe_int(
        state.get("selected_address_id")
    )

    if selected_address_id is not None:
        return selected_address_id

    entity_address_id = _safe_int(
        entities.get("address_id")
    )

    if entity_address_id is not None:
        return entity_address_id

    return None


# =========================================================
# Checkout State
# =========================================================


def _calculate_checkout_missing_fields(
    state: GraphState,
) -> list[str]:
    """
    Calculate the real checkout state.

    NEVER trust stale state["missing_fields"] for order_create.

    Required order:

        product
        quantity
        address
        payment
    """

    entities = (
        state.get("entities", {})
        or {}
    )

    missing: list[str] = []

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    product_name = entities.get(
        "product_name"
    )

    if not _has_value(product_name):
        missing.append("product_name")

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    quantity = entities.get(
        "quantity"
    )

    if not _has_value(quantity):
        missing.append("quantity")

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------
    #
    # IMPORTANT:
    #
    # address_text alone does NOT satisfy checkout.
    #
    # The user must either:
    #
    # - select a saved address
    # - create a new saved address
    #
    # -----------------------------------------------------

    selected_address_id = (
        _get_selected_address_id(
            state,
            entities,
        )
    )

    if selected_address_id is None:
        missing.append(
            "address_selection"
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    payment_method = entities.get(
        "payment_method"
    )

    if not _has_value(payment_method):
        missing.append(
            "payment_method"
        )

    return missing


def _get_next_missing_field(
    missing_fields: list[str],
) -> str | None:
    """
    Return exactly ONE checkout field.

    Priority is always:

        product
        quantity
        address
        payment
    """

    for field in CHECKOUT_FIELDS:

        if field in missing_fields:
            return field

    return None


def _get_checkout_state(
    state: GraphState,
) -> tuple[list[str], str | None]:
    """
    Calculate current checkout state.

    For order_create:
        derive from entities + selected address.

    For other intents:
        preserve graph-provided missing_fields.
    """

    intent = state.get(
        "intent",
        "general",
    )

    if intent != "order_create":

        missing_fields = list(
            state.get(
                "missing_fields",
                [],
            )
            or []
        )

        return (
            missing_fields,
            _get_next_missing_field(
                missing_fields
            ),
        )

    missing_fields = (
        _calculate_checkout_missing_fields(
            state
        )
    )

    return (
        missing_fields,
        _get_next_missing_field(
            missing_fields
        ),
    )


# =========================================================
# Payment Methods
# =========================================================


def _get_payment_methods(
    tool_result: Any,
) -> list[dict[str, Any]]:
    """
    Read payment methods dynamically from the backend/tool
    result.

    Nothing is hardcoded here. If the backend has not supplied
    payment methods, return an empty list and let the AI explain
    what information is currently available.
    """

    if not isinstance(
        tool_result,
        dict,
    ):
        return []

    methods = tool_result.get(
        "methods"
    )

    if isinstance(
        methods,
        list,
    ):
        return methods

    return []


# =========================================================
# AI Checkout Response
# =========================================================


CHECKOUT_RESPONSE_SYSTEM_PROMPT = """
You are BuyQK AI.

Your job is to understand the user's current checkout state and
produce the single most useful next question.

The graph decides which checkout field is missing. You must NOT
change the workflow or invent missing business information.

Use only the supplied state.

Rules:
- Understand natural language and previous conversation.
- Never invent product names, quantities, prices, addresses,
  payment methods, fees, order IDs, or statuses.
- Ask for exactly the field identified as next_missing.
- Use the user's language naturally.
- If a backend result contains options, refer to those options
  without inventing additional ones.
- Keep the question concise.
- Do not mention internal implementation details.
"""


def _generate_ai_checkout_response(
    state: GraphState,
    missing_fields: list[str],
    next_missing: str | None,
    metadata: dict[str, Any],
) -> str:
    """
    Let the AI understand the current checkout state and phrase
    the next question.

    The workflow remains graph-controlled; the AI controls the
    natural-language understanding and response.
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
        "entities": (
            state.get(
                "entities",
                {},
            )
            or {}
        ),
        "tool_result": state.get(
            "tool_result"
        ),
        "missing_fields": missing_fields,
        "next_missing": next_missing,
        "frontend_metadata": metadata,
        "conversation_history": (
            state.get(
                "conversation_history",
                [],
            )
            or []
        ),
    }

    prompt = f"""
Understand the current BuyQK checkout state below and return
ONLY the user-facing question.

Current state:

{_serialize_data(context)}

The graph has already selected next_missing.
Do not ask for any other checkout field.
"""

    try:

        result = llm.invoke(
            [
                SystemMessage(
                    content=CHECKOUT_RESPONSE_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        content = getattr(
            result,
            "content",
            "",
        )

        if isinstance(
            content,
            str,
        ):

            content = content.strip()

            if content:
                return content

    except Exception as exc:

        print(
            "[CHECKOUT RESPONSE LLM ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    # This is intentionally only an operational failure message.
    # No product, payment, address, price, or other business value
    # is hardcoded.
    return "Please provide the information needed to continue."


def _checkout_response(
    state: GraphState,
    missing_fields: list[str],
    next_missing: str | None,
) -> dict[str, Any] | None:
    """
    Build frontend metadata dynamically and let the AI generate
    the user-facing checkout question.

    The graph still controls sequencing.
    The AI controls language and interpretation.
    """

    entities = (
        state.get(
            "entities",
            {},
        )
        or {}
    )

    tool_result = state.get(
        "tool_result"
    )

    # ---------------------------------------------------------
    # Product
    # ---------------------------------------------------------

    if next_missing == "product_name":

        metadata = {
            "type": "product_input",
            "missing_field": "product_name",
            "missing_fields": missing_fields,
        }

        return {
            "response": _generate_ai_checkout_response(
                state,
                missing_fields,
                next_missing,
                metadata,
            ),
            "metadata": metadata,
        }

    # ---------------------------------------------------------
    # Quantity
    # ---------------------------------------------------------

    if next_missing == "quantity":

        metadata = {
            "type": "quantity_input",
            "missing_field": "quantity",
            "missing_fields": missing_fields,
        }

        return {
            "response": _generate_ai_checkout_response(
                state,
                missing_fields,
                next_missing,
                metadata,
            ),
            "metadata": metadata,
        }

    # ---------------------------------------------------------
    # Address
    # ---------------------------------------------------------

    if next_missing == "address_selection":

        addresses: list[Any] = []
        allow_new = True
        prefill = None

        if isinstance(
            tool_result,
            dict,
        ):

            if (
                tool_result.get("type")
                == "address_selection"
            ):

                backend_addresses = (
                    tool_result.get(
                        "addresses",
                        [],
                    )
                )

                if isinstance(
                    backend_addresses,
                    list,
                ):
                    addresses = backend_addresses

                allow_new = bool(
                    tool_result.get(
                        "allow_new",
                        True,
                    )
                )

                prefill = tool_result.get(
                    "prefill"
                )

            elif (
                tool_result.get("type")
                == "saved_addresses"
            ):

                backend_addresses = (
                    tool_result.get(
                        "addresses",
                        [],
                    )
                )

                if isinstance(
                    backend_addresses,
                    list,
                ):
                    addresses = backend_addresses

        metadata = {
            "type": "address_selection",
            "missing_field": "address_selection",
            "missing_fields": missing_fields,
            "addresses": addresses,
            "allow_new": allow_new,
        }

        if prefill:
            metadata["prefill"] = prefill

        return {
            "response": _generate_ai_checkout_response(
                state,
                missing_fields,
                next_missing,
                metadata,
            ),
            "metadata": metadata,
        }

    # ---------------------------------------------------------
    # Payment
    # ---------------------------------------------------------

    if next_missing == "payment_method":

        methods = _get_payment_methods(
            tool_result
        )

        metadata = {
            "type": "payment_selection",
            "missing_field": "payment_method",
            "missing_fields": missing_fields,
            "methods": methods,
        }

        return {
            "response": _generate_ai_checkout_response(
                state,
                missing_fields,
                next_missing,
                metadata,
            ),
            "metadata": metadata,
        }

    return None


# =========================================================
# General Conversation
# =========================================================


def _is_greeting(
    message: str,
) -> bool:
    """
    Detect simple greetings without involving the LLM.

    This is important because a failed LLM call should never
    turn "Hi" into:

        "I'm sorry, I couldn't process that request..."
    """

    normalized = (
        message.strip()
        .lower()
        .replace("!", "")
        .replace(".", "")
        .replace(",", "")
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


def _general_fallback(
    message: str,
) -> str:
    """
    Deterministic fallback for normal conversation.
    """

    if _is_greeting(message):

        return (
            "Hello! I'm BuyQK AI. "
            "How can I help you today?"
        )

    return (
        "Sure, I'm here to help. "
        "What would you like to do?"
    )


# =========================================================
# AI Response
# =========================================================


GENERAL_SYSTEM_PROMPT = """
You are BuyQK AI, the intelligent shopping assistant.

Understand the user's intent, entities, conversation history and
backend results, then generate the final user-facing response.

The backend/tool result is authoritative for transactional facts.

Billing rules:
- When an order result contains a bill, understand every item,
  quantity, unit price, line total, subtotal, delivery charge,
  total, payment method and order ID.
- You may perform the arithmetic needed to explain the bill from
  the supplied quantities and prices.
- Prefer the authoritative bill values supplied by the backend
  when they are present.
- Never invent or change a price, quantity, fee, discount, total,
  order ID, payment method, status, address, product or ticket ID.
- If billing information is incomplete, say only what the supplied
  information supports.
- Never assume a fixed delivery charge or a fixed currency.
- Never hardcode product names or payment options.
- Never mention internal implementation details.

For an order-success result, give a clear itemized bill when bill
data exists, followed by the order ID/status/payment information
that is actually available and a natural next-step question.

For tracking, cancellation, support, product search and general
conversation, use the supplied tool result and conversation
context.

Keep the response concise and natural.
"""


def _generate_llm_response(
    state: GraphState,
) -> str:
    """
    Generate the final response using the AI.

    The complete graph/tool state is supplied so the AI can
    understand the request rather than relying on hardcoded
    product/payment/billing assumptions.
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
        "entities": (
            state.get(
                "entities",
                {},
            )
            or {}
        ),
        "tool_name": state.get(
            "tool_name"
        ),
        "tool_result": state.get(
            "tool_result"
        ),
        "order_id": state.get(
            "order_id"
        ),
        "selected_address_id": state.get(
            "selected_address_id"
        ),
        "payment_method": state.get(
            "payment_method"
        ),
        "missing_fields": state.get(
            "missing_fields",
            [],
        )
        or [],
        "conversation_history": (
            state.get(
                "conversation_history",
                [],
            )
            or []
        ),
    }

    prompt = f"""
Generate the final BuyQK response from the complete state below.

Current state:

{_serialize_data(context)}

Important:
- Understand the state dynamically.
- Use backend/tool data as transactional truth.
- If an order bill exists, explain the billing clearly and
  calculate/verify the arithmetic from the supplied item data
  before presenting it.
- Do not add facts that are absent from the state.
- Do not mention internal systems.
- Return only the user-facing response.
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

        content = getattr(
            result,
            "content",
            "",
        )

        if isinstance(
            content,
            str,
        ):

            content = content.strip()

            if content:
                return content

    except Exception as exc:

        print(
            "[RESPONSE LLM ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    return _general_fallback(
        state.get(
            "message",
            "",
        )
    )


# =========================================================
# AI Tool / Transaction Response
# =========================================================


def _generate_ai_tool_response(
    state: GraphState,
) -> str | None:
    """
    Let the AI interpret successful/failed tool results.

    This includes billing. No product, price, payment method,
    delivery fee, order ID, status, ticket ID or other business
    value is hardcoded here.
    """

    tool_result = state.get(
        "tool_result"
    )

    if not isinstance(
        tool_result,
        dict,
    ):
        return None

    if (
        "success" not in tool_result
    ):
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
        "entities": (
            state.get(
                "entities",
                {},
            )
            or {}
        ),
        "tool_name": state.get(
            "tool_name"
        ),
        "tool_result": tool_result,
        "conversation_history": (
            state.get(
                "conversation_history",
                [],
            )
            or []
        ),
    }

    prompt = f"""
Interpret the following BuyQK tool result and generate the final
user-facing response.

State:

{_serialize_data(context)}

For successful order creation:
1. Understand every order item.
2. For each item, use quantity and unit price to understand the
   line amount.
3. Understand subtotal, delivery charge and final total.
4. If the authoritative bill is present, use those values as
   transactional truth.
5. Present an itemized bill when enough data exists.
6. Include only the payment method, order ID and status that are
   actually supplied.
7. Do not invent discounts, taxes, delivery charges or payment
   options.
8. Ask whether the user wants to track the order only when the
   order result supports tracking.

For every other tool result, explain what actually happened using
only the supplied data.

Return ONLY the final user-facing response.
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

        content = getattr(
            result,
            "content",
            "",
        )

        if isinstance(
            content,
            str,
        ):

            content = content.strip()

            if content:
                return content

    except Exception as exc:

        print(
            "[TOOL RESULT RESPONSE LLM ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

    return None


# =========================================================
# Metadata Cleanup
# =========================================================


def _clean_checkout_metadata(
    metadata: dict[str, Any],
    next_missing: str | None,
) -> dict[str, Any]:
    """
    Remove stale checkout UI.

    Only ONE checkout UI can exist at a time.
    """

    cleaned = dict(
        metadata
    )

    # -----------------------------------------------------
    # Product / Quantity
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

        if cleaned.get("type") in {
            "address_selection",
            "payment_selection",
        }:

            cleaned.pop(
                "type",
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

        if cleaned.get("type") == (
            "payment_selection"
        ):

            cleaned.pop(
                "type",
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

        if cleaned.get("type") == (
            "address_selection"
        ):

            cleaned.pop(
                "type",
                None,
            )

    # -----------------------------------------------------
    # No checkout step
    # -----------------------------------------------------

    else:

        cleaned.pop(
            "address_selection",
            None,
        )

        cleaned.pop(
            "payment_selection",
            None,
        )

    return cleaned


# =========================================================
# Response Node
# =========================================================


def response_node(
    state: GraphState,
) -> GraphState:
    """
    Final LangGraph response node.

    Processing order:

        1. Determine checkout state
        2. Handle successful order
        3. Handle tracking/tool results
        4. Enforce sequential checkout
        5. Handle non-checkout tools
        6. Handle general conversation

    IMPORTANT:

    Never allow the LLM to determine checkout sequencing.
    """

    intent = state.get(
        "intent",
        "general",
    )

    tool_name = state.get(
        "tool_name"
    )

    tool_result = state.get(
        "tool_result"
    )

    message = state.get(
        "message",
        "",
    )

    # =====================================================
    # Existing metadata
    # =====================================================

    metadata = dict(
        state.get(
            "metadata",
            {},
        )
        or {}
    )

    # =====================================================
    # Calculate checkout state
    # =====================================================

    missing_fields, next_missing = (
        _get_checkout_state(
            state
        )
    )

    # =====================================================
    # 1. ORDER SUCCESS
    # =====================================================
    #
    # Billing is supplied by the tool/backend and understood and
    # presented by the AI. No product, price, fee or payment value
    # is calculated or hardcoded in this response node.
    # =====================================================

    if (
        isinstance(
            tool_result,
            dict,
        )
        and tool_result.get(
            "success"
        ) is True
        and tool_result.get(
            "type"
        ) == "order_success"
    ):

        order_id = tool_result.get(
            "order_id"
        )

        bill = tool_result.get(
            "bill"
        )

        purchase_summary = tool_result.get(
            "purchase_summary"
        )

        total_amount = tool_result.get(
            "total_amount"
        )

        status = tool_result.get(
            "status"
        )

        payment_method = tool_result.get(
            "payment_method"
        )

        # -----------------------------------------------------
        # AI generates the complete billing response.
        # -----------------------------------------------------

        response = _generate_ai_tool_response(
            state
        )

        if not response:
            response = _generate_llm_response(
                state
            )

        # -----------------------------------------------------
        # Dynamic frontend metadata.
        #
        # The bill is copied from the authoritative tool result;
        # this node does not invent or recompute business values.
        # -----------------------------------------------------

        metadata = {
            "type": "order_success",
            "order_id": order_id,
            "status": status,
            "payment_method": payment_method,
            "total_amount": total_amount,
            "bill": bill,
            "purchase_summary": purchase_summary,
            "can_track": (
                order_id is not None
            ),
        }

        return {
            "response": response,
            "metadata": metadata,
            "order_id": order_id,
            "awaiting_order_tracking_confirmation": (
                order_id is not None
            ),
            "missing_fields": [],
        }

    # =====================================================
    # 2. TRACKING RESULT
    # =====================================================

    if (
        isinstance(
            tool_result,
            dict,
        )
        and tool_result.get(
            "success"
        ) is True
        and tool_result.get(
            "type"
        ) == "tracking"
    ):

        tracking_order_id = (
            tool_result.get(
                "order_id"
            )
        )

        tracking_status = (
            tool_result.get(
                "status"
            )
        )

        if tracking_order_id is not None:

            response = (
                f"Your order #{tracking_order_id} "
                f"is currently {tracking_status}."
            )

        else:

            response = (
                f"Your order is currently "
                f"{tracking_status}."
            )

        metadata = {
            "type": "tracking",
            "order_id": tracking_order_id,
            "status": tracking_status,
        }

        return {
            "response": response,
            "metadata": metadata,
            "awaiting_order_tracking_confirmation": False,
            "missing_fields": [],
        }

    # =====================================================
    # 3. STRICT ORDER CHECKOUT
    # =====================================================

    if intent == "order_create":

        # -------------------------------------------------
        # Product / Quantity
        # -------------------------------------------------

        if next_missing in {
            "product_name",
            "quantity",
        }:

            checkout = _checkout_response(
                state,
                missing_fields,
                next_missing,
            )

            if checkout:

                checkout_metadata = (
                    checkout.get(
                        "metadata",
                        {},
                    )
                )

                checkout_metadata = (
                    _clean_checkout_metadata(
                        checkout_metadata,
                        next_missing,
                    )
                )

                return {
                    "response": checkout[
                        "response"
                    ],
                    "metadata": checkout_metadata,
                    "missing_fields": missing_fields,
                }

        # -------------------------------------------------
        # Address
        # -------------------------------------------------

        if next_missing == (
            "address_selection"
        ):

            checkout = _checkout_response(
                state,
                missing_fields,
                next_missing,
            )

            if checkout:

                checkout_metadata = (
                    checkout.get(
                        "metadata",
                        {},
                    )
                )

                checkout_metadata = (
                    _clean_checkout_metadata(
                        checkout_metadata,
                        next_missing,
                    )
                )

                return {
                    "response": checkout[
                        "response"
                    ],
                    "metadata": checkout_metadata,
                    "missing_fields": missing_fields,
                }

        # -------------------------------------------------
        # Payment
        # -------------------------------------------------

        if next_missing == (
            "payment_method"
        ):

            checkout = _checkout_response(
                state,
                missing_fields,
                next_missing,
            )

            if checkout:

                checkout_metadata = (
                    checkout.get(
                        "metadata",
                        {},
                    )
                )

                checkout_metadata = (
                    _clean_checkout_metadata(
                        checkout_metadata,
                        next_missing,
                    )
                )

                return {
                    "response": checkout[
                        "response"
                    ],
                    "metadata": checkout_metadata,
                    "missing_fields": missing_fields,
                }

    # =====================================================
    # 4. Tool Result
    # =====================================================

    ai_tool_response = _generate_ai_tool_response(
        state
    )

    if ai_tool_response:

        # Do not expose stale checkout UI.
        metadata = _clean_checkout_metadata(
            metadata,
            next_missing,
        )

        metadata["missing_fields"] = (
            missing_fields
        )

        # Preserve dynamic bill/tool data for the frontend.
        if isinstance(
            tool_result,
            dict,
        ):

            if "bill" in tool_result:
                metadata["bill"] = tool_result.get(
                    "bill"
                )

            if "purchase_summary" in tool_result:
                metadata["purchase_summary"] = (
                    tool_result.get(
                        "purchase_summary"
                    )
                )

        return {
            "response": ai_tool_response,
            "metadata": metadata,
            "missing_fields": missing_fields,
        }

    # =====================================================
    # 5. Product Search
    # =====================================================

    if (
        tool_name == "search_products"
        and isinstance(
            tool_result,
            dict,
        )
        and tool_result.get(
            "success"
        ) is True
    ):

        products = tool_result.get(
            "products",
            [],
        )

        product_list: list[dict[str, Any]] = []

        if isinstance(
            products,
            list,
        ):

            for product in products:

                # -----------------------------------------
                # Dictionary
                # -----------------------------------------

                if isinstance(
                    product,
                    dict,
                ):

                    product_list.append(
                        product
                    )

                    continue

                # -----------------------------------------
                # ORM object
                # -----------------------------------------

                product_list.append(
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
                    }
                )

        if product_list:

            metadata = {
                "type": "product_results",
                "products": product_list,
                "missing_fields": missing_fields,
            }

            return {
                "response": (
                    "I found these products "
                    "for you."
                ),
                "metadata": metadata,
                "missing_fields": missing_fields,
            }

        return {
            "response": (
                "I couldn't find matching products."
            ),
            "metadata": {
                "type": "product_results",
                "products": [],
                "missing_fields": missing_fields,
            },
            "missing_fields": missing_fields,
        }

    # =====================================================
    # 6. Tool Failure
    # =====================================================

    if (
        isinstance(
            tool_result,
            dict,
        )
        and tool_result.get(
            "success"
        ) is False
    ):

        error = (
            tool_result.get("error")
            or tool_result.get("message")
        )

        if error:

            return {
                "response": str(error),
                "metadata": metadata,
                "missing_fields": missing_fields,
            }

        return {
            "response": (
                "I couldn't complete that request."
            ),
            "metadata": metadata,
            "missing_fields": missing_fields,
        }

    # =====================================================
    # 7. General Conversation
    # =====================================================
    #
    # IMPORTANT:
    #
    # "Hi" should NEVER depend on the LLM being available.
    # =====================================================

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
        }

    # =====================================================
    # 8. General LLM Response
    # =====================================================

    response = _generate_llm_response(
        state
    )

    metadata = _clean_checkout_metadata(
        metadata,
        next_missing,
    )

    metadata["missing_fields"] = (
        missing_fields
    )

    # =====================================================
    # 9. Return
    # =====================================================

    return {
        "response": response,
        "metadata": metadata,
        "missing_fields": missing_fields,
    }