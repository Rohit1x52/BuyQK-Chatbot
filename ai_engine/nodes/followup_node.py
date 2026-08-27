from __future__ import annotations

"""
BuyQK AI - Phase 2 Missing Information / Follow-up Node

This node consumes the missing_fields already produced by Entity Node.

It does not:
    - classify intent
    - extract products
    - resolve product IDs
    - mutate the cart
    - create orders
    - calculate prices
    - validate backend facts

It only:
    1. selects one already-declared missing conversational field
    2. generates one natural-language question for that field
    3. marks the graph as waiting for the user's answer

Address and payment selection remain on the existing Planner/Tool
workflow because those steps load application-owned choices such as
saved addresses and available payment methods.
"""

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# These are not user-language rules. They are existing graph fields
# whose UI/backend interaction must remain unchanged.
EXTERNALLY_HANDLED_FIELDS = {
    "address_selection",
    "payment_method",
}


FOLLOWUP_SYSTEM_PROMPT = """
You are the BuyQK AI follow-up question generator.

The application has already determined the current missing field.
Your only job is to ask the user for that ONE field.

Rules:
- Ask exactly one concise question.
- Ask only for current_missing_field.
- Use the conversation and existing entities as context.
- Do not ask again for information that is already known.
- Do not invent product names, quantities, IDs, addresses, payments,
  prices, stock, or other facts.
- Do not execute any action.
- Return only the question text.
- No JSON, markdown, bullets, explanations, or multiple questions.
""".strip()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<analysis>.*?</analysis>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"^\s*(?:assistant|final\s+answer)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip().strip("`").strip() or None


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    content = getattr(value, "content", None)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue

            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)

        return "\n".join(parts)

    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text

        nested = value.get("content")
        if isinstance(nested, str):
            return nested

    return str(value)


def _normalize_missing_fields(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []

    result: list[str] = []

    for item in value:
        if not isinstance(item, str):
            continue

        field = item.strip()

        if field and field not in result:
            result.append(field)

    return result


def _select_missing_field(
    state: GraphState,
    missing_fields: list[str],
) -> str | None:
    current = state.get("current_missing_field")

    if isinstance(current, str):
        current = current.strip()

        if (
            current
            and current in missing_fields
            and current not in EXTERNALLY_HANDLED_FIELDS
        ):
            return current

    for field in missing_fields:
        if field not in EXTERNALLY_HANDLED_FIELDS:
            return field

    return None


def _fallback_question(field: str) -> str:
    label = field.replace("_", " ").strip()

    if not label:
        return "Could you provide the missing information?"

    return f"Could you provide your {label}?"


def _build_prompt(
    state: GraphState,
    field: str,
) -> str:
    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    history = state.get("conversation_history", [])
    if not isinstance(history, list):
        history = []

    context = {
        "current_message": state.get("message", ""),
        "current_missing_field": field,
        "missing_fields": state.get("missing_fields", []),
        "active_task": state.get("active_task"),
        "task_status": state.get("task_status"),
        "entities": entities,
        "order_items": state.get("order_items", []),
        "selected_product": state.get("selected_product"),
        "conversation_history": history,
    }

    return (
        FOLLOWUP_SYSTEM_PROMPT
        + "\n\nCURRENT CONTEXT\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            default=str,
            indent=2,
        )
        + "\n\nGenerate one question:"
    )


def _generate_question(
    state: GraphState,
    field: str,
) -> str:
    try:
        llm = get_llm()

        response = llm.invoke(
            [
                SystemMessage(
                    content=FOLLOWUP_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=_build_prompt(
                        state,
                        field,
                    )
                ),
            ]
        )

        text = _clean_text(
            _content_to_text(response)
        )

        if text:
            # The model is instructed to return one question.
            # If it adds multiple lines, keep only the first line.
            return text.splitlines()[0].strip()

    except Exception as exc:
        print(
            "[FOLLOWUP LLM ERROR]"
            f" {type(exc).__name__}: {exc}"
        )

    return _fallback_question(field)


def followup_node(
    state: GraphState,
) -> GraphState:
    """
    Produce one follow-up question when a graph-declared
    conversational field is missing.

    If the missing fields belong to the existing address/payment
    selection workflow, do not intercept them.
    """

    missing_fields = _normalize_missing_fields(
        state.get("missing_fields", [])
    )

    field = _select_missing_field(
        state,
        missing_fields,
    )

    if field is None:
        return {
            "current_missing_field": None,
            "follow_up_question": None,
            "awaiting_user_input": False,
            "next_missing": (
                missing_fields[0]
                if missing_fields
                else None
            ),
        }

    question = _generate_question(
        state,
        field,
    )

    return {
        "current_missing_field": field,
        "follow_up_question": question,
        "awaiting_user_input": True,
        "next_missing": field,
    }


__all__ = [
    "followup_node",
]

