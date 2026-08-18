# =========================================================
# BuyQK AI - Entity Node
# =========================================================
#
# Purpose:
# Context-aware entity extraction and transaction-state
# preservation for BuyQK AI.
#
# Responsibilities:
#
#   User message
#        ↓
#   AI intent understanding
#        ↓
#   AI entity extraction
#        ↓
#   Merge with existing transaction state
#        ↓
#   Frontend authoritative selections
#        ↓
#   Missing-field detection
#        ↓
#   GraphState update
#
# IMPORTANT:
#
# This node DOES NOT:
#
#   - create orders
#   - calculate prices
#   - calculate bills
#   - calculate taxes
#   - calculate delivery charges
#   - invent product IDs
#   - invent order IDs
#   - determine stock
#
# Those responsibilities belong to backend services/tools.
#
# The AI understands the user's language and intent.
# Backend/database values remain authoritative.
#
# =========================================================


from __future__ import annotations

import re
import uuid
from typing import Any, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# =========================================================
# Structured Entity Output
# =========================================================


class LLMEntityOutput(BaseModel):
    """
    Fields that the LLM is allowed to understand from the
    user's current message.

    product_id is intentionally excluded because it is a
    database identifier and must never be hallucinated.
    """

    product_name: Optional[str] = Field(
        default=None,
        description=(
            "Product the user is referring to. "
            "Understand the user's language semantically."
        ),
    )

    quantity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Explicit quantity requested by the user.",
    )

    order_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Order ID explicitly mentioned by the user.",
    )

    address_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Saved address ID explicitly selected by the user.",
    )

    address_text: Optional[str] = Field(
        default=None,
        description="Natural-language delivery address.",
    )

    payment_method: Optional[str] = Field(
        default=None,
        description=(
            "Payment method understood from the user's message. "
            "Return the normalized backend-supported value when known."
        ),
    )


# =========================================================
# Current-Turn Intent
# =========================================================


class IntentDecision(BaseModel):
    """
    Determines what the user means NOW.

    Previous state is context only.
    It must not force a transaction on the current message.
    """

    intent: Literal[
        "product_search",
        "order_create",
        "order_tracking",
        "order_cancel",
        "customer_support",
        "general",
    ]

    order_action: Literal[
        "start_new_order",
        "continue_order",
        "none",
    ]

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )


# =========================================================
# LLM
# =========================================================


llm = get_llm()

structured_entity_llm = llm.with_structured_output(
    LLMEntityOutput
)

structured_intent_llm = llm.with_structured_output(
    IntentDecision
)


# =========================================================
# AI Entity Prompt
# =========================================================


ENTITY_SYSTEM_PROMPT = """
You are BuyQK's transaction understanding AI.

Your job is to understand the user's CURRENT message in the
context of the existing checkout.

Return only the structured information you can confidently
understand.

SUPPORTED CONCEPTS:

- product_name
- quantity
- order_id
- address_id
- address_text
- payment_method

IMPORTANT:

product_id is NOT an extraction field.

Never invent a product_id.

Never calculate price.

Never calculate subtotal.

Never calculate total.

Never calculate tax.

Never calculate delivery charge.

Never invent an order ID.

Never invent stock.

Those values belong to the backend/database.

------------------------------------------------------------
CONTEXT UNDERSTANDING
------------------------------------------------------------

The user may communicate in:

- English
- Hindi
- Hinglish
- other natural languages
- short replies
- conversational phrases
- references such as "that one", "same product", "use this",
  "haan", "theek hai", etc.

Understand meaning rather than relying on exact English
keywords.

Examples:

"I want Maggi"
→ product_name = Maggi

"Mujhe 3 packet chahiye"
→ quantity = 3

"Teen"
→ quantity = 3 when the checkout context asks for quantity

"COD kar do"
→ payment_method = cod when that is the backend-supported
payment method

"UPI se pay karunga"
→ payment_method = upi

"address 2 use karo"
→ address_id = 2

"deliver it to Gola Road"
→ address_text = Gola Road

------------------------------------------------------------
ACCUMULATION
------------------------------------------------------------

The graph already contains previously established values.

Do not erase an existing value merely because it is absent
from the current message.

Example:

Previous:
product = Maggi
quantity = 3

Current:
"use the selected address"

Do NOT return an empty product or quantity.

The transaction state is accumulated across turns.

------------------------------------------------------------
PRODUCT CHANGE
------------------------------------------------------------

If the user explicitly changes the product:

Previous:
product = Maggi

Current:
"Actually I want Amul Milk"

Return:
product_name = Amul Milk

The application layer will invalidate the old product_id
because it belongs to the previous product.

------------------------------------------------------------
COMPLETED ORDERS
------------------------------------------------------------

A completed order does not automatically make the next
message an order.

Examples:

"Thank you"
→ no transactional entities

"Okay"
→ no transactional entities

"Yes"
→ do not assume an order

"I want to buy another Maggi"
→ product_name = Maggi

------------------------------------------------------------
IMPORTANT
------------------------------------------------------------

Extract meaning from the CURRENT message.

Use previous conversation only to understand references
and short follow-up answers.

Do not invent missing values.
"""


# =========================================================
# AI Intent Prompt
# =========================================================


INTENT_SYSTEM_PROMPT = """
You are BuyQK's current-turn intent understanding AI.

Determine what the USER wants NOW.

Do not classify the entire conversation.

Available intents:

product_search
order_create
order_tracking
order_cancel
customer_support
general

Order actions:

start_new_order
continue_order
none

------------------------------------------------------------
ORDER CREATION
------------------------------------------------------------

Use order_create when:

1. The user explicitly wants to purchase something.

OR

2. The user is clearly answering a required question for
   an active checkout.

Examples:

"I want Maggi"
→ order_create / start_new_order

"I want to buy milk"
→ order_create / start_new_order

"3"
when assistant asked quantity
→ order_create / continue_order

"Use address 2"
when assistant asked address
→ order_create / continue_order

"COD"
when assistant asked payment
→ order_create / continue_order

------------------------------------------------------------
COMPLETED ORDER SAFETY
------------------------------------------------------------

A completed order MUST NOT cause the next conversational
message to become another order.

Examples:

Previous:
"Your order #123 was placed."

Current:
"Thank you"
→ general / none

Current:
"Okay"
→ general / none

Current:
"Yes, track it"
→ order_tracking / none

Current:
"I want to buy another one"
→ order_create / start_new_order

------------------------------------------------------------
LANGUAGE
------------------------------------------------------------

Understand the meaning semantically.

Do not rely on fixed English keywords.

The user may use:

English
Hindi
Hinglish
or another language.

------------------------------------------------------------
SAFETY
------------------------------------------------------------

If the message is ambiguous, choose the safer
non-transactional interpretation.

Never create an order merely because old transaction
entities exist.
"""


# =========================================================
# Generic Helpers
# =========================================================


def _safe_role(item: dict[str, Any]) -> str:
    return str(item.get("role", "")).strip().lower()


def _safe_content(item: dict[str, Any]) -> str:
    return str(item.get("content", "")).strip()


def _has_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    return text if text else None


# =========================================================
# Conversation Formatting
# =========================================================


def format_conversation_history(
    conversation_history: list[dict[str, Any]] | None,
) -> str:

    if not conversation_history:
        return "No previous conversation."

    lines: list[str] = []

    for item in conversation_history:

        role = _safe_role(item)
        content = _safe_content(item)

        if not content:
            continue

        lines.append(
            f"{role.upper()}: {content}"
        )

    if not lines:
        return "No previous conversation."

    return "\n".join(lines)


# =========================================================
# User Message History
# =========================================================


def get_user_history(
    conversation_history: list[dict[str, Any]] | None,
) -> list[tuple[int, str]]:

    result: list[tuple[int, str]] = []

    if not conversation_history:
        return result

    for index, item in enumerate(conversation_history):

        role = _safe_role(item)
        content = _safe_content(item)

        if role in {"user", "human"} and content:
            result.append(
                (index, content)
            )

    return result


# =========================================================
# Previous Assistant Message
# =========================================================


def get_previous_assistant_message(
    conversation_history: list[dict[str, Any]] | None,
    user_index: int,
) -> str:

    if not conversation_history:
        return ""

    for index in range(
        user_index - 1,
        -1,
        -1,
    ):

        item = conversation_history[index]

        role = _safe_role(item)

        if role in {"assistant", "ai"}:
            return _safe_content(item)

    return ""


# =========================================================
# Deterministic Quantity Extraction
# =========================================================
#
# This is not intent detection.
#
# It only provides a safety fallback for numeric quantities.
# Semantic intent remains AI-controlled.
# =========================================================


def detect_quantity(
    message: str,
    allow_plain_number: bool = True,
) -> Optional[int]:

    if not message:
        return None

    patterns = [
        r"\b(\d+)\s*(?:packets?|packs?|pieces?|pcs?|items?|units?)\b",
        r"\b(\d+)\s*(?:kg|kgs|kilograms?)\b",
        r"\b(\d+)\s*(?:g|grams?)\b",
        r"\b(?:quantity|qty)\s*(?:is|=|:)?\s*(\d+)\b",
        r"\bmake\s+it\s+(\d+)\b",
        r"\bchange\s+(?:it\s+)?to\s+(\d+)\b",
    ]

    if allow_plain_number:
        patterns.append(
            r"^\s*(\d+)\s*$"
        )

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        try:

            value = int(
                match.group(1)
            )

            if value > 0:
                return value

        except (
            TypeError,
            ValueError,
        ):
            pass

    return None


# =========================================================
# Address ID Safety Extraction
# =========================================================
#
# This is only used when the user explicitly provides an
# address identifier.
#
# Frontend selected_address_id remains authoritative.
# =========================================================


def detect_address_id(
    message: str,
) -> Optional[int]:

    if not message:
        return None

    match = re.search(
        r"\baddress\s*(?:id)?\s*[:#]?\s*(\d+)\b",
        message,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:

        value = int(
            match.group(1)
        )

        return value if value > 0 else None

    except (
        TypeError,
        ValueError,
    ):
        return None


# =========================================================
# Order ID Safety Extraction
# =========================================================


def detect_order_id(
    message: str,
) -> Optional[int]:

    if not message:
        return None

    match = re.search(
        r"\border\s*(?:id|number|no\.?)?\s*[:#]?\s*(\d+)\b",
        message,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:

        value = int(
            match.group(1)
        )

        return value if value > 0 else None

    except (
        TypeError,
        ValueError,
    ):
        return None


# =========================================================
# AI Entity Extraction
# =========================================================


def extract_entities(
    state: GraphState,
    message: str,
) -> LLMEntityOutput:

    if not message.strip():
        return LLMEntityOutput()

    history = state.get(
        "conversation_history",
        [],
    ) or []

    existing_entities = (
        state.get(
            "entities",
            {},
        )
        or {}
    )

    context = f"""
CURRENT USER MESSAGE
====================
{message}

RECENT CONVERSATION
===================
{format_conversation_history(history)}

CURRENT TRANSACTION STATE
=========================
{existing_entities}

CHECKOUT STATUS
===============
{state.get("checkout_status")}

ORDER CREATED
=============
{state.get("order_created")}

IMPORTANT:

Understand the current message in context.

Do not invent fields.

Do not calculate anything.

Do not create identifiers.

Do not return product_id.
"""

    try:

        result = structured_entity_llm.invoke(
            [
                SystemMessage(
                    content=ENTITY_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=context
                ),
            ]
        )

        if isinstance(
            result,
            LLMEntityOutput,
        ):
            return result

    except Exception as exc:

        print(
            "[ENTITY LLM ERROR]"
            f" {type(exc).__name__}: {exc}"
        )

    return LLMEntityOutput()


# =========================================================
# AI Current-Turn Intent
# =========================================================


def resolve_current_turn_intent(
    state: GraphState,
    message: str,
) -> IntentDecision:

    history = state.get(
        "conversation_history",
        [],
    ) or []

    context = f"""
CURRENT USER MESSAGE
====================
{message}

RECENT CONVERSATION
===================
{format_conversation_history(history)}

CURRENT GRAPH INTENT
====================
{state.get("intent", "general")}

CHECKOUT ID
===========
{state.get("checkout_id")}

CHECKOUT STATUS
==============
{state.get("checkout_status")}

ORDER CREATED
=============
{state.get("order_created")}

ORDER ID
========
{state.get("order_id")}

CURRENT ENTITIES
================
{state.get("entities", {})}

Determine what the user means NOW.

Do not create a new order merely because old entities exist.
"""

    try:

        result = structured_intent_llm.invoke(
            [
                SystemMessage(
                    content=INTENT_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=context
                ),
            ]
        )

        if isinstance(
            result,
            IntentDecision,
        ):
            return result

    except Exception as exc:

        print(
            "[INTENT LLM ERROR]"
            f" {type(exc).__name__}: {exc}"
        )

    # Fail closed.
    #
    # A failed AI intent call must NEVER create an order.
    return IntentDecision(
        intent="general",
        order_action="none",
        confidence=0.0,
    )


# =========================================================
# Product Change Detection
# =========================================================


def _product_changed(
    previous_name: Any,
    current_name: Any,
) -> bool:

    previous = _normalize_text(
        previous_name
    )

    current = _normalize_text(
        current_name
    )

    if not previous or not current:
        return False

    return (
        previous.casefold()
        != current.casefold()
    )


# =========================================================
# Checkout ID
# =========================================================


def _ensure_checkout_id(
    state: GraphState,
) -> str:

    existing = _normalize_text(
        state.get("checkout_id")
    )

    if existing:
        return existing

    return str(
        uuid.uuid4()
    )


# =========================================================
# New Checkout Reset
# =========================================================


def _start_new_checkout(
    entities: dict[str, Any],
) -> dict[str, Any]:

    preserved: dict[str, Any] = {}

    # Explicitly remove transaction-specific state.
    #
    # The new user request will populate these fields.
    #
    for key in (
        "product_id",
        "product_name",
        "quantity",
        "address_id",
        "address_text",
        "payment_method",
        "order_id",
    ):
        entities.pop(
            key,
            None,
        )

    return preserved


# =========================================================
# Missing Fields
# =========================================================


def get_missing_fields(
    intent: str,
    entities: dict[str, Any],
    checkout_status: Any = None,
) -> list[str]:

    if intent == "product_search":

        if not _has_value(
            entities.get("product_name")
        ):
            return ["product_name"]

        return []

    if intent == "order_create":

        if not _has_value(
            entities.get("product_name")
        ):

            return ["product_name"]

        quantity = entities.get(
            "quantity"
        )

        if (
            quantity is None
            or not isinstance(
                quantity,
                int,
            )
            or quantity <= 0
        ):

            return ["quantity"]

        if not _has_value(
            entities.get("address_id")
        ):

            return ["address_selection"]

        if not _has_value(
            entities.get("payment_method")
        ):

            return ["payment_method"]

        return []

    if intent == "order_tracking":

        if not _has_value(
            entities.get("order_id")
        ):
            return ["order_id"]

        return []

    if intent == "order_cancel":

        if not _has_value(
            entities.get("order_id")
        ):
            return ["order_id"]

        return []

    return []


# =========================================================
# Entity Validation
# =========================================================


def _normalize_entities(
    entities: dict[str, Any],
) -> dict[str, Any]:

    result = dict(
        entities
    )

    # -----------------------------------------------------
    # Product name
    # -----------------------------------------------------

    if "product_name" in result:

        value = _normalize_text(
            result.get("product_name")
        )

        if value:
            result["product_name"] = value
        else:
            result.pop(
                "product_name",
                None,
            )

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    if result.get("quantity") is not None:

        try:

            quantity = int(
                result["quantity"]
            )

            if quantity > 0:
                result["quantity"] = quantity
            else:
                result.pop(
                    "quantity",
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            result.pop(
                "quantity",
                None,
            )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    if result.get("address_id") is not None:

        try:

            address_id = int(
                result["address_id"]
            )

            if address_id > 0:
                result["address_id"] = address_id
            else:
                result.pop(
                    "address_id",
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            result.pop(
                "address_id",
                None,
            )

    # -----------------------------------------------------
    # Order ID
    # -----------------------------------------------------

    if result.get("order_id") is not None:

        try:

            order_id = int(
                result["order_id"]
            )

            if order_id > 0:
                result["order_id"] = order_id
            else:
                result.pop(
                    "order_id",
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            result.pop(
                "order_id",
                None,
            )

    # -----------------------------------------------------
    # Address text
    # -----------------------------------------------------

    if "address_text" in result:

        address_text = _normalize_text(
            result.get("address_text")
        )

        if address_text:
            result["address_text"] = address_text
        else:
            result.pop(
                "address_text",
                None,
            )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------
    #
    # Do NOT attempt to understand payment using a large
    # hardcoded keyword table here.
    #
    # The LLM performs semantic interpretation.
    #
    # We only normalize whitespace/case.
    # Backend validation remains authoritative.
    # -----------------------------------------------------

    if result.get("payment_method") is not None:

        payment = _normalize_text(
            result.get("payment_method")
        )

        if payment:
            result["payment_method"] = (
                payment.casefold()
            )
        else:
            result.pop(
                "payment_method",
                None,
            )

    return result


# =========================================================
# Entity Node
# =========================================================


def entity_node(
    state: GraphState,
) -> GraphState:

    message = (
        state.get(
            "message",
            "",
        )
        or ""
    ).strip()

    conversation_history = (
        state.get(
            "conversation_history",
            [],
        )
        or []
    )

    existing_entities = dict(
        state.get(
            "entities",
            {},
        )
        or {}
    )

    original_intent = state.get(
        "intent",
        "general",
    )

    # =====================================================
    # CURRENT-TURN AI INTENT
    # =====================================================

    intent_decision = (
        resolve_current_turn_intent(
            state=state,
            message=message,
        )
    )

    current_intent = (
        intent_decision.intent
    )

    order_action = (
        intent_decision.order_action
    )

    # =====================================================
    # TRANSACTION STATE
    # =====================================================

    previous_checkout_status = (
        state.get(
            "checkout_status"
        )
    )

    previous_order_created = bool(
        state.get(
            "order_created",
            False,
        )
    )

    previous_order_id = state.get(
        "order_id"
    )

    previous_checkout_id = (
        state.get(
            "checkout_id"
        )
    )

    # =====================================================
    # COMPLETED TRANSACTION SAFETY
    # =====================================================
    #
    # If the current AI decision is general/support/etc.,
    # preserve the completed transaction.
    #
    # DO NOT restart it.
    #
    # This directly prevents:
    #
    # "Thank you"
    #
    # from being interpreted as another order.
    # =====================================================

    completed_transaction = (
        previous_order_created
        or previous_checkout_status
        in {
            "completed",
            "order_created",
            "success",
        }
    )

    # =====================================================
    # START NEW ORDER
    # =====================================================

    new_order = (
        current_intent
        == "order_create"
        and order_action
        == "start_new_order"
    )

    if new_order:

        # A genuinely new purchase starts a fresh checkout.
        existing_entities = (
            _start_new_checkout(
                existing_entities
            )
        )

        checkout_id = str(
            uuid.uuid4()
        )

        checkout_status = (
            "collecting"
        )

        order_created = False

        previous_order_id = None

    else:

        # Continue existing transaction.
        checkout_id = (
            _normalize_text(
                previous_checkout_id
            )
            or (
                _ensure_checkout_id(
                    state
                )
                if current_intent
                == "order_create"
                else None
            )
        )

        checkout_status = (
            previous_checkout_status
        )

        order_created = (
            previous_order_created
        )

    # =====================================================
    # AI ENTITY EXTRACTION
    # =====================================================

    extracted = extract_entities(
        state=state,
        message=message,
    )

    extracted_entities = (
        extracted.model_dump(
            exclude_none=True
        )
    )

    # =====================================================
    # MERGE
    # =====================================================
    #
    # Existing state first.
    # New AI information then updates only values actually
    # understood from the current message.
    # =====================================================

    entities = dict(
        existing_entities
    )

    for key, value in extracted_entities.items():

        if value is not None:
            entities[key] = value

    # =====================================================
    # DETERMINISTIC QUANTITY SAFETY
    # =====================================================
    #
    # Numeric quantities are safe to validate deterministically.
    # This does not decide intent.
    # =====================================================

    explicit_quantity = detect_quantity(
        message,
        allow_plain_number=True,
    )

    if explicit_quantity is not None:

        entities["quantity"] = (
            explicit_quantity
        )

    # =====================================================
    # ADDRESS ID SAFETY
    # =====================================================

    explicit_address_id = (
        detect_address_id(
            message
        )
    )

    if explicit_address_id is not None:

        entities["address_id"] = (
            explicit_address_id
        )

        entities.pop(
            "address_text",
            None,
        )

    # =====================================================
    # ORDER ID SAFETY
    # =====================================================

    explicit_order_id = (
        detect_order_id(
            message
        )
    )

    if explicit_order_id is not None:

        entities["order_id"] = (
            explicit_order_id
        )

    # =====================================================
    # FRONTEND ADDRESS
    # =====================================================
    #
    # Frontend selection is authoritative.
    # =====================================================

    selected_address_id = (
        state.get(
            "selected_address_id"
        )
    )

    if selected_address_id is not None:

        try:

            normalized_address_id = int(
                selected_address_id
            )

            if normalized_address_id > 0:

                entities["address_id"] = (
                    normalized_address_id
                )

                entities.pop(
                    "address_text",
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            print(
                "[ENTITY] Invalid selected_address_id:",
                repr(
                    selected_address_id
                ),
            )

    # =====================================================
    # FRONTEND PAYMENT
    # =====================================================
    #
    # Frontend-selected payment is authoritative.
    #
    # The backend/payment layer remains responsible for
    # validating whether the method is actually available.
    # =====================================================

    selected_payment_method = (
        state.get(
            "selected_payment_method"
        )
    )

    if not selected_payment_method:

        # Backward compatibility with older API payloads.
        selected_payment_method = (
            state.get(
                "payment_method"
            )
        )

    if selected_payment_method:

        payment = _normalize_text(
            selected_payment_method
        )

        if payment:

            entities[
                "payment_method"
            ] = payment.casefold()

    # =====================================================
    # PRODUCT CONSISTENCY
    # =====================================================
    #
    # product_id is backend-authoritative.
    #
    # If the product changes, invalidate the old product ID.
    # =====================================================

    previous_product_name = (
        existing_entities.get(
            "product_name"
        )
    )

    previous_product_id = (
        existing_entities.get(
            "product_id"
        )
    )

    current_product_name = (
        entities.get(
            "product_name"
        )
    )

    product_changed = (
        _product_changed(
            previous_product_name,
            current_product_name,
        )
    )

    if product_changed:

        entities.pop(
            "product_id",
            None,
        )

    elif previous_product_id is not None:

        try:

            normalized_product_id = int(
                previous_product_id
            )

            if normalized_product_id > 0:

                entities["product_id"] = (
                    normalized_product_id
                )

        except (
            TypeError,
            ValueError,
        ):

            entities.pop(
                "product_id",
                None,
            )

    # =====================================================
    # PRODUCT ID SAFETY
    # =====================================================

    if entities.get(
        "product_id"
    ) is not None:

        try:

            product_id = int(
                entities[
                    "product_id"
                ]
            )

            if product_id > 0:

                entities[
                    "product_id"
                ] = product_id

            else:

                entities.pop(
                    "product_id",
                    None,
                )

        except (
            TypeError,
            ValueError,
        ):

            entities.pop(
                "product_id",
                None,
            )

    # =====================================================
    # NORMALIZE ALL ENTITIES
    # =====================================================

    entities = _normalize_entities(
        entities
    )

    # =====================================================
    # PRODUCT NAME SAFETY
    # =====================================================

    product_name = _normalize_text(
        entities.get(
            "product_name"
        )
    )

    if product_name:

        entities[
            "product_name"
        ] = product_name

    else:

        entities.pop(
            "product_name",
            None,
        )

        # Never carry a product ID without its product.
        entities.pop(
            "product_id",
            None,
        )

    # =====================================================
    # ORDER ID
    # =====================================================

    order_id = entities.get(
        "order_id"
    )

    if (
        order_id is None
        and not new_order
        and previous_order_id is not None
        and current_intent
        in {
            "order_tracking",
            "order_cancel",
        }
    ):

        try:

            order_id = int(
                previous_order_id
            )

            if order_id > 0:

                entities[
                    "order_id"
                ] = order_id

        except (
            TypeError,
            ValueError,
        ):
            pass

    # =====================================================
    # COMPLETED ORDER PRESERVATION
    # =====================================================
    #
    # "Thank you", "okay", etc. must not erase the order
    # state or turn it into a new transaction.
    # =====================================================

    if (
        completed_transaction
        and not new_order
    ):

        if previous_order_id is not None:

            entities[
                "order_id"
            ] = previous_order_id

        order_id = (
            previous_order_id
            or entities.get(
                "order_id"
            )
        )

        order_created = True

        if not checkout_status:

            checkout_status = (
                "completed"
            )

    # =====================================================
    # MISSING FIELDS
    # =====================================================

    missing_fields = (
        get_missing_fields(
            intent=current_intent,
            entities=entities,
            checkout_status=checkout_status,
        )
    )

    # =====================================================
    # MIRROR VALUES
    # =====================================================

    product_id = entities.get(
        "product_id"
    )

    quantity = entities.get(
        "quantity"
    )

    address_id = entities.get(
        "address_id"
    )

    payment_method = entities.get(
        "payment_method"
    )

    # =====================================================
    # CHECKOUT STATUS
    # =====================================================

    if new_order:

        checkout_status = (
            "collecting"
        )

    elif (
        current_intent
        == "order_create"
    ):

        if missing_fields:

            checkout_status = (
                "collecting"
            )

        else:

            checkout_status = (
                "ready"
            )

    # IMPORTANT:
    #
    # Entity node does NOT set order_created=True merely
    # because all fields exist.
    #
    # Only the backend create_order operation can establish
    # that an order was actually created.
    #
    # Therefore:
    #
    # fields complete != order created
    #
    # =====================================================

    if not previous_order_created and not new_order:

        order_created = False

    # =====================================================
    # BILL PRESERVATION
    # =====================================================
    #
    # Entity node does not calculate or modify billing.
    #
    # Backend-generated billing stays in GraphState.
    # =====================================================

    billing = state.get(
        "billing"
    )

    bill = state.get(
        "bill"
    )

    # =====================================================
    # FINAL DEBUG
    # =====================================================

    final_entities = dict(
        entities
    )

    print(
        "\n"
        "====================================================\n"
        "[ENTITY NODE]\n"
        "====================================================\n"
        f"message          = {message!r}\n"
        f"intent_before    = {original_intent!r}\n"
        f"intent_after     = {current_intent!r}\n"
        f"order_action     = {order_action!r}\n"
        f"confidence       = {intent_decision.confidence!r}\n"
        f"new_order        = {new_order}\n"
        f"checkout_id      = {checkout_id!r}\n"
        f"checkout_status  = {checkout_status!r}\n"
        f"order_created    = {order_created}\n"
        f"order_id         = {order_id!r}\n"
        f"product_id       = {product_id!r}\n"
        f"product_name     = {product_name!r}\n"
        f"quantity         = {quantity!r}\n"
        f"address_id       = {address_id!r}\n"
        f"payment_method   = {payment_method!r}\n"
        f"missing_fields   = {missing_fields!r}\n"
        f"entities         = {final_entities!r}\n"
        "====================================================\n"
    )

    # =====================================================
    # RETURN GRAPH STATE UPDATE
    # =====================================================

    result: GraphState = {
        "intent": current_intent,

        "entities": final_entities,

        "checkout_id": checkout_id,

        "checkout_status": checkout_status,

        "order_created": order_created,

        "order_id": order_id,

        "product_id": product_id,

        "product_name": product_name,

        "quantity": quantity,

        "address_id": address_id,

        "selected_payment_method": (
            payment_method
        ),

        # Backward compatibility.
        "payment_method": payment_method,

        "missing_fields": missing_fields,
    }

    # -----------------------------------------------------
    # Preserve authoritative billing.
    #
    # Entity node never modifies it.
    # -----------------------------------------------------

    if billing is not None:
        result["billing"] = billing

    if bill is not None:
        result["bill"] = bill

    return result


# =========================================================
# Compatibility Helpers
# =========================================================


def resolve_transaction_intent(
    state: GraphState,
    entities: dict[str, Any],
    message: str,
) -> str:

    return resolve_current_turn_intent(
        state=state,
        message=message,
    ).intent


def _is_new_order_request(
    message: str,
) -> bool:
    """
    Deprecated.

    New-order decisions belong to the AI intent classifier.
    """
    return False


def _is_explicit_tracking_request(
    message: str,
) -> bool:
    """
    Deprecated.

    Tracking decisions belong to the AI intent classifier.
    """
    return False


def _is_explicit_cancel_request(
    message: str,
) -> bool:
    """
    Deprecated.

    Cancellation decisions belong to the AI intent classifier.
    """
    return False


def _is_explicit_support_request(
    message: str,
) -> bool:
    """
    Deprecated.

    Support decisions belong to the AI intent classifier.
    """
    return False


def _is_payment_selection(
    message: str,
) -> bool:
    """
    Compatibility helper.

    Payment interpretation itself is performed by the AI.
    """
    return bool(
        message
        and message.strip()
    )


def _is_address_selection(
    state: GraphState,
    message: str,
) -> bool:
    """
    Compatibility helper.

    Actual selection is authoritative from frontend state.
    """

    if state.get(
        "selected_address_id"
    ) is not None:

        return True

    return (
        detect_address_id(
            message
        )
        is not None
    )


def _is_active_order_checkout(
    state: GraphState,
    entities: dict[str, Any],
    message: str,
) -> bool:
    """
    Compatibility helper.

    Active checkout is based on transaction state rather than
    stale product/quantity entities.
    """

    checkout_status = (
        state.get(
            "checkout_status"
        )
    )

    if checkout_status in {
        "collecting",
        "ready",
    }:

        return True

    return (
        state.get(
            "intent"
        )
        == "order_create"
        and not state.get(
            "order_created",
            False,
        )
    )