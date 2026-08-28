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
from ai_engine.tools.results import ToolResult


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


# Unicode range for Devanagari script. This is a script check, not a vocabulary list.
_HINDI_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


# =========================================================
# Canonical Error Responses
# =========================================================

# These are the only customer-facing error categories supported by the
# Response Node.  Backend/tool implementation details and raw exception
# messages must never be exposed to the user.
CANONICAL_ERROR_RESPONSES = {
    "not_found": (
        "I couldn't find the requested resource."
    ),
    "validation_error": (
        "The information provided is invalid or incomplete."
    ),
    "backend_error": (
        "I couldn't complete that request right now. Please try again."
    ),
    "conflict": (
        "I couldn't complete that request because it conflicts with the current state."
    ),
    "unauthorized": (
        "You are not authorized to perform this action."
    ),
}


CANONICAL_ERROR_TYPES = frozenset(
    CANONICAL_ERROR_RESPONSES
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
    """Return a presentation dictionary for the authoritative ToolResult."""
    result = state.get(
        "tool_result"
    )

    if isinstance(
        result,
        ToolResult,
    ):
        payload = result.to_dict()

        # The canonical ToolResult keeps business data under ``data``.
        # The Response Node works with the legacy flat presentation shape.
        if isinstance(
            result.data,
            dict,
        ):
            payload.update(
                result.data
            )

        # Keep the presentation layer backward-compatible with the old
        # flat ``error`` string while preserving the canonical ToolResult
        # object in GraphState.
        if result.error is not None:
            payload["error"] = result.error.message
            payload["error_code"] = result.error.code

        return payload

    if isinstance(
        result,
        dict,
    ):
        return dict(result)

    return None


def _get_tool_result_object(
    state: GraphState,
) -> ToolResult | None:
    """Return the canonical ToolResult object from GraphState."""
    result = state.get(
        "tool_result"
    )

    if isinstance(
        result,
        ToolResult,
    ):
        return result

    return None



def _extract_canonical_error_code(
    tool_result: Any,
) -> str | None:
    """
    Extract a canonical error code from a ToolResult presentation payload.

    The canonical ToolResult stores structured errors as ``error.code``.
    The presentation payload may also expose the backward-compatible
    flattened ``error_code`` field.

    Only the five supported canonical categories are accepted. Unknown
    codes deliberately return ``None`` so legacy fallback behavior remains
    available without accidentally presenting an internal error category.
    """

    if not isinstance(tool_result, dict):
        return None

    code = tool_result.get("error_code")

    if not isinstance(code, str):
        error = tool_result.get("error")

        if isinstance(error, dict):
            code = error.get("code")
        else:
            code = getattr(error, "code", None)

    if not isinstance(code, str):
        return None

    code = code.strip().lower()

    if code in CANONICAL_ERROR_TYPES:
        return code

    return None


def _canonical_error_response(
    tool_result: Any,
) -> str | None:
    """
    Return the fixed customer-facing response for a canonical error.

    The Response Node intentionally does not expose the backend's raw error
    message. The canonical category determines the customer-facing wording.
    """

    code = _extract_canonical_error_code(
        tool_result
    )

    if code is None:
        return None

    return CANONICAL_ERROR_RESPONSES[code]


# =========================================================
# Response Language
# =========================================================

_SUPPORTED_RESPONSE_LANGUAGES = frozenset(
    {
        "english",
        "hindi",
        "hinglish",
    }
)


def _normalize_response_language(value: Any) -> str | None:
    """
    Normalize an explicitly supplied response language.

    Language understanding itself is delegated to the LLM. This helper only
    validates the small set of response-language values supported by the
    application contract.
    """
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()

    aliases = {
        "en": "english",
        "eng": "english",
        "english": "english",
        "hi": "hindi",
        "hin": "hindi",
        "hindi": "hindi",
        "hinglish": "hinglish",
        "hi-en": "hinglish",
        "en-hi": "hinglish",
        "hindi-english": "hinglish",
    }

    return aliases.get(normalized)


def _parse_detected_response_language(value: Any) -> str | None:
    """
    Extract a supported language value from an LLM response.

    The LLM is responsible for understanding the actual language of the
    conversation. No language-vocabulary dictionary is maintained here.
    """
    text = _extract_text_content(value).strip()

    if not text:
        return None

    normalized = _normalize_response_language(text)
    if normalized:
        return normalized

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = None

    if isinstance(payload, dict):
        for key in ("response_language", "language", "detected_language"):
            language = _normalize_response_language(payload.get(key))
            if language:
                return language

    # Allow a model to return a small JSON object wrapped in markdown.
    match = re.search(
        r'"(?:response_language|language|detected_language)"\s*:\s*"([^"]+)"',
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return _normalize_response_language(match.group(1))

    return None


def _message_tokens(message: Any) -> list[str]:
    """Return normalized word tokens for deterministic language heuristics."""
    if not isinstance(message, str):
        return []

    return re.findall(
        r"[A-Za-z]+(?:'[A-Za-z]+)?",
        message.lower(),
    )


_ROMAN_HINDI_MARKERS = frozenset({
    "mujhe", "mujhko", "mera", "meri", "mere", "aap", "aapko",
    "kya", "kaise", "kaisa", "kitna", "kitne", "kitni",
    "chahiye", "chaahiye", "karo", "karna", "kar", "do", "hai",
    "hain", "tha", "thi", "the", "mein", "me", "ko", "se",
    "par", "pe", "wala", "wali", "wale", "yeh", "yah", "woh",
    "wo", "aur", "bhi", "nahi", "nahin", "haan", "ji", "dikhao",
    "batao", "bhejo", "kaunsa", "kaunsi", "kitni", "chahunga",
    "chahenge",
})

_ENGLISH_MIX_MARKERS = frozenset({
    "please", "help", "need", "want", "find", "show", "order",
    "cart", "add", "remove", "product", "size", "quantity",
    "payment", "address",
})


_RESPONSE_LANGUAGE_SYSTEM_PROMPT = """
You are the language-understanding component of BuyQK AI.

Determine the language in which BuyQK should respond to the user.

Return exactly one JSON object:
{"response_language":"english"}
or
{"response_language":"hindi"}
or
{"response_language":"hinglish"}

Definitions:
- english: the user is communicating primarily in English.
- hindi: the user is communicating primarily in Hindi, including Hindi
  written with Latin/Roman characters.
- hinglish: the user substantially mixes Hindi and English in the same
  conversational message.

Important:
- Understand the complete message semantically. Do not rely on a fixed
  keyword list.
- Product names, brand names, numbers, units, names, URLs, SKUs, and other
  domain terms do not by themselves determine the response language.
- Roman-script Hindi is Hindi when the underlying sentence is predominantly
  Hindi.
- Use conversation history when the current message is too short or
  language-neutral to determine the language on its own.
- A short follow-up such as a number, quantity, confirmation, or selection
  should inherit the language of the relevant recent conversation.
- Do not use the assistant's own previous wording as the primary signal when
  a user's recent message provides a clearer signal.
- If there is not enough evidence, choose english.
- Return JSON only.
"""


def _detect_response_language(
    state: GraphState,
) -> str:
    """Detect the response language once for the current turn.

    Explicit graph state wins. For direct/unit callers, a small deterministic
    linguistic signal handles clear Roman-Hindi/Hinglish cases before the LLM
    classifier is used for ambiguous messages.
    """
    if not isinstance(state, dict):
        return "english"

    explicit = _normalize_response_language(state.get("response_language"))
    if explicit:
        return explicit

    current = state.get("message", "")
    tokens = set(_message_tokens(current))

    # Devanagari is unambiguous Hindi.
    if isinstance(current, str) and _HINDI_DEVANAGARI_RE.search(current):
        return "hindi"

    hindi_hits = tokens & _ROMAN_HINDI_MARKERS
    english_mix_hits = tokens & _ENGLISH_MIX_MARKERS

    # Clear mixed Roman-Hindi + English usage is Hinglish.
    if hindi_hits and english_mix_hits:
        return "hinglish"

    # Clear Roman-Hindi without English mixing is Hindi.
    if hindi_hits:
        return "hindi"

    history = state.get("conversation_history", [])
    recent_history = list(history)[-8:] if isinstance(history, (list, tuple)) else []

    # Ambiguous/neutral messages can inherit a language from explicit recent
    # user turns without making another model call.
    for item in reversed(recent_history):
        if isinstance(item, dict):
            text = item.get("message") or item.get("content") or item.get("text") or ""
        else:
            text = getattr(item, "content", item if isinstance(item, str) else "")

        if not isinstance(text, str) or not text.strip():
            continue

        prior_tokens = set(_message_tokens(text))
        if _HINDI_DEVANAGARI_RE.search(text):
            return "hindi"
        if prior_tokens & _ROMAN_HINDI_MARKERS:
            if prior_tokens & _ENGLISH_MIX_MARKERS:
                return "hinglish"
            return "hindi"
        if prior_tokens:
            return "english"

    # English is the safe default for language-neutral messages.
    return "english"


# =========================================================
# Language presentation helpers
# =========================================================

_LANGUAGE_INSTRUCTIONS = {
    "english": (
        "Respond in English. Keep the response concise, professional, and natural."
    ),
    "hindi": (
        "Respond in natural Hindi. Keep the response concise and professional. "
        "Preserve product names, IDs, quantities, prices, statuses, and other "
        "authoritative values exactly as supplied."
    ),
    "hinglish": (
        "Respond in natural Hinglish using Roman-script Hindi with English "
        "shopping terms where natural. Preserve product names, IDs, quantities, "
        "prices, statuses, and other authoritative values exactly as supplied."
    ),
}


def _response_language_for_generation(state: GraphState) -> str:
    """
    Return the already-established response language without making another
    LLM call.

    response_node() establishes response_language once per turn. Direct unit
    callers that do not provide it safely use English rather than triggering
    a hidden second LLM request.
    """
    if isinstance(state, dict):
        language = _normalize_response_language(
            state.get("response_language")
        )
        if language:
            return language

    return "english"


def _language_instruction(state: GraphState) -> str:
    """Return the presentation instruction for an already-selected language."""
    language = _response_language_for_generation(state)
    return _LANGUAGE_INSTRUCTIONS[language]


def _adapt_deterministic_response(
    response: Any,
    state: GraphState,
) -> str:
    """
    Adapt deterministic fallback wording to the selected language.

    This function never changes authoritative backend values. It only maps
    Response Node's own fixed fallback phrases; product names and other
    supplied values are preserved when they occur in a context-specific
    response.
    """
    text = _extract_text_content(response).strip()
    if not text:
        return ""

    language = _response_language_for_generation(state)
    if language == "english":
        return text

    # Context-specific responses containing authoritative product names need
    # to retain those values while changing only the surrounding wording.
    if language == "hindi":
        replacements = (
            ("has been added to your cart.", "aapke cart mein add kar diya gaya hai."),
            ("has been removed from your cart.", "aapke cart se remove kar diya gaya hai."),
            ("The item has been added to your cart.", "Item aapke cart mein add kar diya gaya hai."),
            ("The item has been removed from your cart.", "Item aapke cart se remove kar diya gaya hai."),
            ("Your cart has been cleared.", "Aapka cart clear kar diya gaya hai."),
            ("Your cart is empty.", "Aapka cart empty hai."),
            ("Here is your current cart.", "Yeh aapka current cart hai."),
            ("Your cart has been updated.", "Aapka cart update kar diya gaya hai."),
            ("Your cart request was completed.", "Aapka cart request complete ho gaya hai."),
            ("The request was completed.", "Request complete ho gayi hai."),
            ("I couldn't complete that request.", "Main yeh request complete nahi kar saka."),
            ("I couldn't find matching products.", "Mujhe matching products nahi mile."),
            ("I found these matching products: ", "Mujhe yeh matching products mile: "),
            ("How many would you like?", "Aapko kitni quantity chahiye?"),
            ("Please specify the quantity.", "Kripya quantity specify kijiye."),
            ("How many packs of ", "Aapko kitne packs of "),
            (" would you like?", " chahiye?"),
            ("Please select a delivery address.", "Kripya delivery address select kijiye."),
            ("Please select a payment method.", "Kripya payment method select kijiye."),
            ("Which product would you like?", "Aap kaunsa product chahenge?"),
        )
    else:
        replacements = (
            ("has been added to your cart.", "aapke cart mein add ho gaya hai."),
            ("has been removed from your cart.", "aapke cart se remove ho gaya hai."),
            ("The item has been added to your cart.", "Item aapke cart mein add ho gaya hai."),
            ("The item has been removed from your cart.", "Item aapke cart se remove ho gaya hai."),
            ("Your cart has been cleared.", "Aapka cart clear ho gaya hai."),
            ("Your cart is empty.", "Aapka cart empty hai."),
            ("Here is your current cart.", "Yeh aapka current cart hai."),
            ("Your cart has been updated.", "Aapka cart update ho gaya hai."),
            ("Your cart request was completed.", "Aapka cart request complete ho gaya hai."),
            ("The request was completed.", "Request complete ho gayi hai."),
            ("I couldn't complete that request.", "Yeh request complete nahi ho paayi."),
            ("I couldn't find matching products.", "Matching products nahi mile."),
            ("I found these matching products: ", "Yeh matching products mile: "),
            ("How many would you like?", "Kitni quantity chahiye?"),
            ("Please specify the quantity.", "Quantity specify kijiye."),
            ("How many packs of ", "Kitne packs of "),
            (" would you like?", " chahiye?"),
            ("Please select a delivery address.", "Delivery address select kijiye."),
            ("Please select a payment method.", "Payment method select kijiye."),
            ("Which product would you like?", "Kaunsa product chahiye?"),
        )

    adapted = text
    for source, target in replacements:
        adapted = adapted.replace(source, target)

    return adapted


def _context_value(
    state: GraphState,
    field: str,
) -> Any:
    """Return a known conversational value from state or entities.

    Direct GraphState values take precedence over entity values.
    """
    if not isinstance(state, dict):
        return None

    direct = state.get(field)
    if _has_value(direct):
        return direct

    entities = _get_entities(state)
    value = entities.get(field)
    if _has_value(value):
        return value

    return None


def _context_aware_response_context(
    state: GraphState,
    missing_fields: list[str],
    next_missing: str | None,
) -> dict[str, Any]:
    """
    Build presentation context from the information already known
    by the graph.

    This helper does not decide workflow or mutate state.
    """

    entities = _get_entities(state)

    known_fields: dict[str, Any] = {}

    candidate_fields = (
        "product_name",
        "product_id",
        "quantity",
        "size",
        "variant",
        "brand",
        "address_selection",
        "payment_method",
    )

    for field in candidate_fields:
        value = _context_value(
            state,
            field,
        )

        if _has_value(value):
            known_fields[field] = value

    return {
        "known_fields": known_fields,
        "entities": entities,
        "missing_fields": list(missing_fields),
        "next_missing": next_missing,
        "current_message": state.get(
            "message",
            "",
        ),
    }


def _context_aware_missing_field_fallback(
    state: GraphState,
    next_missing: str | None,
) -> str:
    """Build a deterministic missing-field question from known graph state."""
    product_name = _context_value(state, "product_name")
    product_text = str(product_name).strip() if _has_value(product_name) else None

    if next_missing == "product_name":
        return "Which product would you like?"

    if next_missing == "quantity":
        if product_text:
            return (
                f"How many packs of {product_text} would you like? "
                "Please specify the quantity."
            )
        return "How many would you like?"

    if next_missing in {"size", "variant_size", "product_size"}:
        if product_text:
            return f"Which size of {product_text} would you like?"
        return "Which size would you like?"

    if next_missing == "address_selection":
        return "Please select a delivery address."

    if next_missing == "payment_method":
        return "Please select a payment method."

    return _checkout_fallback(next_missing)


def _localized_context_fallback(
    state: GraphState,
    next_missing: str | None,
) -> str:
    """Return a context-aware fallback in the detected conversation language.

    Direct callers/tests may invoke this helper without going through
    response_node(), so establish the language once on a shallow state copy.
    No additional LLM call is made here.
    """
    if not isinstance(state, dict):
        state = {}

    selected = _detect_response_language(state)
    localized_state = dict(state)
    localized_state["response_language"] = selected

    return _adapt_deterministic_response(
        _context_aware_missing_field_fallback(
            localized_state,
            next_missing,
        ),
        localized_state,
    )


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
        tool_result = {}

    methods = tool_result.get(
        "methods"
    )

    if not isinstance(
        methods,
        list,
    ) or not methods:
        from backend.services.order_service import PAYMENT_METHODS
        return PAYMENT_METHODS

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

Generate the response in the supplied response_language. Do not translate
authoritative values unless appropriate for natural user-facing wording.

If backend/tool results provide options, use only those options.

Keep the response concise and natural.

Response language:
- Generate the final response in the response_language supplied in the
  current state/context.
- Follow the detected language naturally.
- Do not translate product names, brand names, IDs, SKUs, URLs, or other
  authoritative backend values unless the user-facing context requires it.

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
    """Generate wording for the graph-selected missing field."""
    existing = state.get("follow_up_question")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()

    context = {
        "current_message": state.get("message", ""),
        "conversation_history": state.get("conversation_history", []),
        "entities": _get_entities(state),
        "missing_fields": missing_fields,
        "next_missing": next_missing,
        "backend_options": _get_tool_result(state),
        "response_language": _response_language_for_generation(state),
        "language_instruction": _language_instruction(state),
    }
    try:
        response = llm.invoke([
            SystemMessage(content=CHECKOUT_RESPONSE_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
        ])
        text = _sanitize_user_response(response)
        if text:
            return text.splitlines()[0].strip()
    except Exception as exc:
        print(f"[CHECKOUT RESPONSE ERROR] {type(exc).__name__}: {exc}")

    return _localized_context_fallback(state, next_missing)


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
- recognize the canonical error category when provided
- not_found: explain that the requested resource could not be found
- validation_error: explain that the supplied information is invalid or incomplete
- backend_error: give a generic service error without exposing internals
- conflict: explain that the requested operation conflicts with the current state
- unauthorized: explain that the user is not authorized
- never expose raw backend exceptions or internal implementation details

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
        "response_language": _response_language_for_generation(state),
        "language_instruction": _language_instruction(state),
    }

    prompt = f"""
Generate the final user-facing BuyQK response.

Current state:

{_serialize_data(context)}

Remember:
- backend/tool data is authoritative
- graph workflow is authoritative
- generate the response in the supplied response_language
- do not infer response language from hardcoded vocabulary
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

    return _adapt_deterministic_response(
        _general_fallback(
            state.get(
                "message",
                "",
            )
        ),
        state,
    )


# =========================================================
# Step 2 — Successful Tool Responses
# =========================================================


def _success_response_from_tool(
    tool_result: dict[str, Any],
    tool_name: str | None = None,
) -> str:
    """Generate deterministic responses for successful shopping operations."""

    if not isinstance(tool_result, dict):
        return "The request was completed."

    if tool_result.get("success") is not True:
        canonical_response = _canonical_error_response(
            tool_result
        )

        if canonical_response:
            return canonical_response

        return "I couldn't complete that request."

    result_type = tool_result.get("type")
    action = tool_result.get("action")

    # =====================================================
    # SEARCH PRODUCTS
    # =====================================================

    if (
        tool_name == "search_products"
        or tool_result.get("tool") == "search_products"
        or result_type == "product_search"
    ):
        products = tool_result.get(
            "products",
            [],
        )

        if not isinstance(products, list):
            return "I couldn't find matching products."

        names: list[str] = []

        for product in products:
            if isinstance(product, dict):
                name = product.get("name")
            else:
                name = getattr(
                    product,
                    "name",
                    None,
                )

            if (
                isinstance(name, str)
                and name.strip()
            ):
                names.append(
                    name.strip()
                )

        if names:
            return (
                "I found these matching products: "
                + ", ".join(names)
                + "."
            )

        return "I couldn't find matching products."

    # =====================================================
    # ADD TO CART
    # =====================================================

    if (
        tool_name == "add_to_cart"
        or tool_result.get("tool") == "add_to_cart"
        or (
            result_type in {
                "cart_add",
                "cart_updated",
            }
            and action in {
                "add_item",
                "add_to_cart",
            }
        )
    ):
        product_name = tool_result.get(
            "product_name"
        )

        quantity = tool_result.get(
            "quantity"
        )

        if (
            isinstance(product_name, str)
            and product_name.strip()
        ):
            if quantity is not None:
                return (
                    f"{quantity} × "
                    f"{product_name.strip()} "
                    "has been added to your cart."
                )

            return (
                f"{product_name.strip()} "
                "has been added to your cart."
            )

        return "The item has been added to your cart."

    # =====================================================
    # REMOVE FROM CART
    # =====================================================

    if (
        tool_name == "remove_from_cart"
        or tool_result.get("tool") == "remove_from_cart"
        or (
            result_type in {
                "cart_remove",
                "cart_updated",
            }
            and action in {
                "remove_item",
                "remove_from_cart",
            }
        )
    ):
        product_name = tool_result.get(
            "product_name"
        )

        if (
            isinstance(product_name, str)
            and product_name.strip()
        ):
            return (
                f"{product_name.strip()} "
                "has been removed from your cart."
            )

        return (
            "The item has been removed from your cart."
        )

    # =====================================================
    # GET CART
    # =====================================================

    if (
        tool_name == "get_cart"
        or tool_result.get("tool") == "get_cart"
        or result_type in {
            "cart_view",
            "cart",
        }
    ):
        cart = tool_result.get(
            "cart"
        )

        if isinstance(
            cart,
            dict,
        ):
            items = cart.get(
                "items"
            )

            if (
                isinstance(items, list)
                and not items
            ):
                return "Your cart is empty."

        return "Here is your current cart."

    # =====================================================
    # GENERIC SUCCESS
    # =====================================================

    return "The request was completed."


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
        "response_language": _response_language_for_generation(state),
        "language_instruction": _language_instruction(state),
    }

    prompt = f"""
Generate the final user-facing response from this BuyQK tool result.

State:

{_serialize_data(context)}

Rules:

1. Treat tool_result as authoritative.
2. If success is false and a canonical error_code is present, use the canonical category response and do not expose the raw error message.
3. Canonical error categories are exactly: not_found, validation_error, backend_error, conflict, unauthorized.
4. If the category is not canonical, preserve the existing safe fallback behavior.
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
11. For product search, explicitly mention the returned product names when names are present in tool_result.products. Do not replace them with a generic statement.

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

        canonical_response = _canonical_error_response(
            tool_result
        )

        if canonical_response:
            return canonical_response

        error = (
            tool_result.get(
                "error"
            )
            or tool_result.get(
                "message"
            )
        )

        # Legacy fallback: preserve existing behavior when a result does
        # not carry one of the supported canonical error categories.
        if error:
            return str(
                error
            )

        return (
            "I couldn't complete that request."
        )

    # -----------------------------------------------------
    # Cart add / remove
    # -----------------------------------------------------

    if (
        tool_result.get("tool") == "add_to_cart"
        or (
            result_type in {"cart_add", "cart_updated"}
            and tool_result.get("action") in {
                None,
                "add_item",
                "add_to_cart",
            }
        )
    ):
        product_name = tool_result.get("product_name")
        quantity = tool_result.get("quantity")
        if isinstance(product_name, str) and product_name.strip():
            if quantity is not None:
                return f"{quantity} × {product_name.strip()} has been added to your cart."
            return f"{product_name.strip()} has been added to your cart."
        return "The item has been added to your cart."

    if (
        tool_result.get("tool") == "remove_from_cart"
        or (
            result_type in {"cart_remove", "cart_updated"}
            and tool_result.get("action") in {
                "remove_item",
                "remove_from_cart",
            }
        )
    ):
        product_name = tool_result.get("product_name")
        if isinstance(product_name, str) and product_name.strip():
            return f"{product_name.strip()} has been removed from your cart."
        return "The item has been removed from your cart."

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

        if order_id is not None:

            parts.append(
                "Would you like me to track your order?"
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

        if isinstance(products, list) and products:
            names: list[str] = []
            for product in products:
                if isinstance(product, dict):
                    name = product.get("name")
                else:
                    name = getattr(product, "name", None)
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())

            if names:
                # Product names are copied from the authoritative tool result;
                # no catalog value is embedded in the Response Node.
                return "I found these matching products: " + ", ".join(names) + "."

            return "I found matching products for you."

        return "I couldn't find matching products."

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
        canonical_response = _canonical_error_response(
            tool_result
        )

        if canonical_response:
            return canonical_response

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

    # Language is presentation context. Detect it once so every response
    # path uses the same language decision.
    response_language = _detect_response_language(state)

    # Keep the original graph state immutable while making the detected
    # language available to all presentation helpers.
    presentation_state = dict(state)
    presentation_state["response_language"] = response_language

    tool_result_object = _get_tool_result_object(presentation_state)
    tool_result = _get_tool_result(presentation_state)

    missing_fields = _get_missing_fields(presentation_state)
    next_missing = _get_next_missing(
        presentation_state,
        missing_fields,
    )

    metadata = dict(
        presentation_state.get("metadata", {}) or {}
    )

    # ---------------------------------------------------------
    # Phase 2 follow-up question
    #
    # The Follow-up Node owns missing-field selection and question
    # generation. Response Node only presents the result.
    # ---------------------------------------------------------
    follow_up_question = state.get(
        "follow_up_question"
    )
    awaiting_user_input = bool(
        presentation_state.get("awaiting_user_input")
    )
    current_missing_field = state.get(
        "current_missing_field"
    )

    if (
        awaiting_user_input
        and isinstance(
            follow_up_question,
            str,
        )
        and follow_up_question.strip()
    ):
        question = follow_up_question.strip()

        metadata.update(
            {
                "type": "follow_up",
                "question": question,
                "field": current_missing_field,
                "missing_fields": missing_fields,
                "awaiting_user_input": True,
            }
        )

        return {
            "response": question,
            "response_language": response_language,
            "tool_result": tool_result_object,
            "metadata": metadata,
            "missing_fields": missing_fields,
            "next_missing": current_missing_field,
            "current_missing_field": current_missing_field,
            "follow_up_question": question,
            "awaiting_user_input": True,
        }

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
            presentation_state,
            tool_result,
        )

        # Order success is transactional output. Do not spend another
        # LLM call just to paraphrase it; this also keeps checkout usable
        # when the LLM provider is rate-limited.
        response = _tool_fallback(tool_result)
        response = _sanitize_user_response(response)

        return {
            "response": response,
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        # Canonical/current CartService result types.
        "cart_add",
        "cart_remove",
        "cart_update",
        "cart_clear",
        "cart_view",
        "cart_checkout",
        # Backward-compatible result types.
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
            response = _success_response_from_tool(
                tool_result,
                tool_name,
            )

            # Step 2 success paths are deterministic. Other cart
            # operations retain their existing presentation behavior.
            if not response:
                response = _generate_tool_response(presentation_state)

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
            "response_language": response_language,
            "tool_result": tool_result_object,
            "metadata": cart_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

        # checkout_cart starts checkout but does not create an order.
        if tool_result.get("type") in {"cart_checkout_ready", "cart_checkout"}:
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
    # Canonical tool error
    #
    # Handle canonical failures before checkout UI rendering. A failed
    # operation must never be presented as if the checkout step succeeded.
    # ---------------------------------------------------------
    if (
        isinstance(tool_result, dict)
        and tool_result.get("success") is False
        and _extract_canonical_error_code(tool_result) is not None
    ):
        response = _canonical_error_response(tool_result)
        failure_metadata = _clean_checkout_metadata(
            metadata,
            next_missing,
        )

        failure_metadata["missing_fields"] = missing_fields

        if next_missing is not None:
            failure_metadata["next_missing"] = next_missing
        else:
            failure_metadata.pop("next_missing", None)

        return {
            "response": response or "I couldn't complete that request.",
            "tool_result": tool_result_object,
            "metadata": failure_metadata,
            "missing_fields": missing_fields,
            "next_missing": next_missing,
        }

    # ---------------------------------------------------------
    # 3. Checkout UI
    #
    # The graph has already selected next_missing.
    # Response Node only renders it.
    # A stable fallback is used when the presentation LLM is unavailable.
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
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        response = _generate_tool_response(presentation_state)

        if not response:
            response = _tool_fallback(tool_result)

        tracking_metadata = _tool_metadata(
            presentation_state,
            missing_fields,
        )

        response = _sanitize_user_response(response)

        if not response:
            response = _tool_fallback(tool_result)

        return {
            "response": response,
            "response_language": response_language,
            "tool_result": tool_result_object,
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
            # Step 2: successful product search is deterministic.
            # Product identities come directly from Tool Node output.
            response = _success_response_from_tool(
                tool_result,
                tool_name,
            )

            if not response:
                response = _tool_fallback(tool_result)
        else:
            response = _success_response_from_tool(
                tool_result,
                tool_name,
            )

            if not response:
                response = "I couldn't find matching products."

        response = _sanitize_user_response(response)

        if not response:
            response = _tool_fallback(tool_result)

        return {
            "response": response,
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        reason = str(policy_error.get("reason") or "").strip()
        try:
            response = _sanitize_user_response(
                _generate_llm_response({
                    **state,
                    "policy_error": policy_error,
                    "policy_failure_reason": reason,
                })
            )
        except Exception:
            response = ""
        if not response:
            response = str(
                policy_error.get("message")
                or "I could not continue with that request."
            )
        return {
            "response": response,
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        # Canonical error categories always take precedence over legacy
        # result-type fallbacks. This guarantees consistent customer-facing
        # behavior regardless of which tool produced the failure.
        response = _canonical_error_response(
            tool_result
        )

        if not response:
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
                _canonical_error_response(tool_result)
                or str(
                    tool_result.get("error")
                    or tool_result.get("message")
                    or "I couldn't complete that request."
                )
            )

        return {
            "response": response,
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        response = _generate_tool_response(presentation_state)

        if not response:
            response = _tool_fallback(tool_result)

        tool_metadata = _tool_metadata(
            presentation_state,
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
            "response_language": response_language,
            "tool_result": tool_result_object,
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
        response = _sanitize_user_response(_generate_llm_response(presentation_state))
        return {
            "response": response or "How can I help you?",
            "tool_result": tool_result_object,
            "metadata": {},
            "missing_fields": [],
            "next_missing": None,
        }

    # ---------------------------------------------------------
    # 9. General conversation
    # ---------------------------------------------------------
    response = _sanitize_user_response(
        _generate_llm_response(presentation_state)
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
            "response_language": response_language,
        "tool_result": tool_result_object,
        "metadata": metadata,
        "missing_fields": missing_fields,
        "next_missing": next_missing,
    }

# =========================================================
# Backward-Compatible Public API
# =========================================================

def generate_response(
    state: GraphState,
) -> GraphState:
    """
    Backward-compatible public wrapper.

    Existing tests and callers may import generate_response().
    The production implementation remains response_node().
    """

    return response_node(state)


__all__ = [
    "response_node",
    "generate_response",
    "_success_response_from_tool",
    "_generate_llm_response",
    "_generate_tool_response",
    "_tool_fallback",
    "_detect_response_language",
    "_language_instruction",
    "_adapt_deterministic_response",
    "_localized_context_fallback",
    "_context_aware_missing_field_fallback",
    "_context_aware_response_context",
    "_context_value",
]
