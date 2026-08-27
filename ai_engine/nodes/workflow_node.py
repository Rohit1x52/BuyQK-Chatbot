from __future__ import annotations

"""
BuyQK AI - Phase 3 Task / Workflow Manager

Purpose
-------
Maintain one active conversational workflow across turns.

The node does not execute tools, resolve backend facts, or replace the
existing Entity/Planner/Policy contracts. It uses the AI to determine
whether the current message continues the previous workflow, starts a new
workflow, switches to another workflow, or completes/ends one.

The workflow identity is semantic. It is not derived from a hardcoded
phrase list.
"""

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ai_engine.graph.state import GraphState
from ai_engine.llm.client import get_llm


# ============================================================
# Canonical workflow transitions
# ============================================================

WORKFLOW_TRANSITIONS = {
    "start",
    "continue",
    "switch",
    "complete",
    "idle",
}


# ============================================================
# Canonical workflow statuses
# ============================================================

WORKFLOW_STATUSES = {
    "idle",
    "active",
    "collecting_information",
    "ready_to_execute",
    "executing",
    "completed",
    "failed",
}


# ============================================================
# Workflow Manager Prompt
# ============================================================

WORKFLOW_SYSTEM_PROMPT = """
You are the BuyQK AI Task / Workflow Manager.

Your responsibility is to maintain the user's CURRENT conversational
workflow across turns.

A workflow is the user's ongoing goal, not merely the current message.
The current message may be incomplete by itself and can depend on the
previous workflow.

You receive:
- the current user message
- previous conversation history
- the previous active workflow, if any
- the current semantic intent
- the extracted entities
- missing information
- follow-up state
- checkout/cart/backend context

Determine:

1. whether the current message continues the previous workflow,
   starts a new workflow, switches to another workflow, completes
   the current workflow, or leaves the system idle

2. the stable semantic workflow name

3. the workflow lifecycle status

4. the user's current workflow goal

5. whether the previous workflow should be continued, replaced,
   completed, or cleared

IMPORTANT:

- Understand meaning, not exact wording.
- Do not depend on trigger phrases or keyword matching.
- A short reply can be a valid continuation when a previous workflow
  is waiting for information.
- Preserve the previous workflow when the current message supplies
  information for it.
- Only switch workflows when the current message establishes a
  genuinely different user goal.
- Do not erase useful workflow context merely because the current
  message contains only one field of information.
- Do not invent products, IDs, prices, stock, addresses, payment
  results, order results, or other backend facts.
- Do not execute any action.
- Do not decide whether a backend operation is allowed.
- Do not claim that a transaction succeeded.

WORKFLOW NAME:

Use a concise lowercase snake_case semantic name representing the
user's ongoing goal.

The workflow name is semantic and may be any meaningful task.
Examples include:
- grocery_order
- cart_management
- product_search
- order_tracking
- order_cancellation
- customer_support
- booking
- registration

These are examples only. Do not force an unrelated request into
one of these categories.

LIFECYCLE:

- idle:
  no active user task exists

- active:
  a workflow exists and is in progress

- collecting_information:
  the workflow is waiting for required information

- ready_to_execute:
  the workflow has the information required by the current graph

- executing:
  the workflow is currently being executed

- completed:
  the workflow has actually completed according to authoritative
  graph/backend state

- failed:
  the workflow has actually failed according to authoritative
  graph/backend state

TRANSITION:

- start:
  there was no active workflow and a new goal is established

- continue:
  the current message belongs to the existing workflow

- switch:
  the user establishes a different goal

- complete:
  the existing workflow has actually completed

- idle:
  no workflow should remain active

CRITICAL:

Do not mark a workflow as completed merely because the user supplied
another piece of information.

Do not mark a workflow as executing merely because an action may
eventually be executed.

Do not inherit lifecycle state from a previous workflow after a
switch.

Return ONLY valid JSON:

{
  "active_task": "semantic_workflow_name or null",
  "task_status": "idle|active|collecting_information|ready_to_execute|executing|completed|failed",
  "workflow_goal": "current user goal or null",
  "workflow_transition": "start|continue|switch|complete|idle",
  "reason": "short explanation"
}
""".strip()


# ============================================================
# Helpers
# ============================================================

def _content_to_text(value: Any) -> str:
    """Convert common LLM response content formats into plain text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        text = value.get("text")

        if isinstance(text, str):
            return text

        content = value.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            return _content_to_text(content)

    if isinstance(value, list):
        parts: list[str] = []

        for block in value:
            if isinstance(block, str):
                parts.append(block)
                continue

            if isinstance(block, dict):
                text = block.get("text")

                if isinstance(text, str):
                    parts.append(text)
                    continue

                nested = block.get("content")

                if isinstance(nested, str):
                    parts.append(nested)
                    continue

            text = getattr(block, "text", None)

            if isinstance(text, str):
                parts.append(text)

        return "\n".join(parts)

    nested = getattr(value, "content", None)

    if nested is not None and nested is not value:
        return _content_to_text(nested)

    return str(value)


def _clean_text(value: Any) -> str:
    """Remove common reasoning/markdown wrappers from LLM output."""

    text = _content_to_text(value).strip()

    if not text:
        return ""

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

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def _extract_json(value: Any) -> dict[str, Any]:
    """Extract the first valid JSON object from an LLM response."""

    text = _clean_text(value)

    if not text:
        raise ValueError(
            "Workflow manager returned empty output."
        )

    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    for index, char in enumerate(text):
        if char != "{":
            continue

        try:
            parsed, _ = decoder.raw_decode(text[index:])

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            continue

    raise ValueError(
        "Workflow manager returned invalid JSON."
    )


def _normalize_name(value: Any) -> str | None:
    """Normalize a workflow name into lowercase snake_case."""

    if not isinstance(value, str):
        return None

    value = value.strip().casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    value = re.sub(
        r"_+",
        "_",
        value,
    )

    value = value.strip("_")

    return value or None


def _normalize_transition(value: Any) -> str | None:
    """Normalize and validate workflow transition."""

    if not isinstance(value, str):
        return None

    value = (
        value.strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return (
        value
        if value in WORKFLOW_TRANSITIONS
        else None
    )


def _normalize_status(value: Any) -> str | None:
    """Normalize and validate workflow status."""

    if not isinstance(value, str):
        return None

    value = (
        value.strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return (
        value
        if value in WORKFLOW_STATUSES
        else None
    )


def _normalize_goal(value: Any) -> str | None:
    """Normalize workflow goal."""

    if value is None:
        return None

    text = str(value).strip()

    return text or None


# ============================================================
# Prompt construction
# ============================================================

def _build_prompt(state: GraphState) -> str:
    """Build the semantic workflow context for the LLM."""

    history = state.get(
        "conversation_history",
        [],
    )

    if not isinstance(history, list):
        history = []

    entities = state.get(
        "entities",
        {},
    )

    if not isinstance(entities, dict):
        entities = {}

    workflow_context = state.get(
        "workflow_context",
        {},
    )

    if not isinstance(workflow_context, dict):
        workflow_context = {}

    context = {
        "current_message": state.get(
            "message",
            "",
        ),

        "conversation_history": history,

        "previous_workflow": {
            "active_task": state.get(
                "active_task"
            ),

            "task_status": state.get(
                "task_status"
            ),

            "workflow_goal": state.get(
                "workflow_goal"
            ),

            "workflow_transition": state.get(
                "workflow_transition"
            ),

            "workflow_context": workflow_context,
        },

        "current_understanding": {
            "intent": state.get(
                "intent"
            ),

            "user_goal": state.get(
                "user_goal"
            ),

            "detected_language": state.get(
                "detected_language"
            ),

            "references": state.get(
                "references",
                {},
            ),

            "entities": entities,

            "order_items": state.get(
                "order_items",
                [],
            ),

            "missing_fields": state.get(
                "missing_fields",
                [],
            ),

            "current_missing_field": state.get(
                "current_missing_field"
            ),

            "awaiting_user_input": bool(
                state.get(
                    "awaiting_user_input"
                )
            ),
        },

        "transaction_context": {
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

            "cart_status": state.get(
                "cart_status"
            ),

            "cart_items": state.get(
                "cart_items",
                [],
            ),

            "transaction_error": state.get(
                "transaction_error"
            ),
        },
    }

    return (
        WORKFLOW_SYSTEM_PROMPT
        + "\n\nCURRENT STATE\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            default=str,
            indent=2,
        )
        + "\n\nReturn the workflow decision JSON only."
    )


# ============================================================
# Safe fallback
# ============================================================

def _fallback_workflow(
    state: GraphState,
) -> dict[str, Any]:
    """
    Safe fallback when the workflow LLM fails.

    The fallback preserves an existing workflow and never invents
    a new workflow from arbitrary text.
    """

    previous = _normalize_name(
        state.get("active_task")
    )

    intent = _normalize_name(
        state.get("intent")
    )

    missing = state.get(
        "missing_fields"
    )

    if not isinstance(missing, list):
        missing = []

    previous_status = _normalize_status(
        state.get("task_status")
    )

    awaiting = bool(
        state.get(
            "awaiting_user_input"
        )
    )

    # --------------------------------------------------------
    # Existing workflow waiting for information
    # --------------------------------------------------------

    if previous and awaiting:
        status = (
            "collecting_information"
            if missing
            else "ready_to_execute"
        )

        return {
            "active_task": previous,

            "task_status": status,

            "workflow_goal": (
                _normalize_goal(
                    state.get(
                        "workflow_goal"
                    )
                )
                or _normalize_goal(
                    state.get(
                        "user_goal"
                    )
                )
            ),

            "workflow_transition": "continue",

            "reason": (
                "Preserved the active workflow "
                "while processing the current turn."
            ),
        }

    # --------------------------------------------------------
    # Current semantic intent establishes a workflow
    # --------------------------------------------------------

    if intent and intent != "general":
        status = (
            "collecting_information"
            if missing
            else "ready_to_execute"
        )

        if previous and previous != intent:
            transition = "switch"

        elif previous:
            transition = "continue"

        else:
            transition = "start"

        return {
            "active_task": intent,

            "task_status": status,

            "workflow_goal": _normalize_goal(
                state.get(
                    "user_goal"
                )
            ),

            "workflow_transition": transition,

            "reason": (
                "Used the current semantic intent "
                "as a safe fallback workflow identity."
            ),
        }

    # --------------------------------------------------------
    # Preserve an existing workflow
    # --------------------------------------------------------

    if (
        previous
        and previous_status
        not in {
            "completed",
            "failed",
        }
    ):
        status = previous_status

        if status == "idle":
            status = "active"

        return {
            "active_task": previous,

            "task_status": status,

            "workflow_goal": (
                _normalize_goal(
                    state.get(
                        "workflow_goal"
                    )
                )
                or _normalize_goal(
                    state.get(
                        "user_goal"
                    )
                )
            ),

            "workflow_transition": "continue",

            "reason": (
                "Preserved the existing workflow "
                "because no new goal was established."
            ),
        }

    # --------------------------------------------------------
    # No active workflow
    # --------------------------------------------------------

    return {
        "active_task": None,

        "task_status": "idle",

        "workflow_goal": None,

        "workflow_transition": "idle",

        "reason": (
            "No active workflow was established."
        ),
    }


# ============================================================
# Main Workflow Node
# ============================================================

def workflow_node(
    state: GraphState,
) -> GraphState:
    """
    Maintain the semantic workflow across conversation turns.

    The node:

    1. asks the LLM to understand the workflow
    2. validates its output
    3. applies authoritative backend state
    4. prevents previous workflow state from leaking into a
       newly started/switched workflow
    5. records workflow history/context
    """

    try:
        response = get_llm().invoke(
            [
                SystemMessage(
                    content=WORKFLOW_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=_build_prompt(
                        state
                    )
                ),
            ]
        )

        raw = _extract_json(response)

        active_task = _normalize_name(
            raw.get("active_task")
        )

        task_status = _normalize_status(
            raw.get("task_status")
        )

        workflow_goal = _normalize_goal(
            raw.get("workflow_goal")
        )

        transition = _normalize_transition(
            raw.get(
                "workflow_transition"
            )
        )

        previous_task = _normalize_name(
            state.get("active_task")
        )

        missing = state.get(
            "missing_fields",
            [],
        )

        if not isinstance(missing, list):
            missing = []

        # ----------------------------------------------------
        # Preserve an active workflow when the user is
        # answering a follow-up question.
        # ----------------------------------------------------

        if (
            not active_task
            and previous_task
            and bool(
                state.get(
                    "awaiting_user_input"
                )
            )
        ):
            active_task = previous_task
            transition = "continue"

        # ----------------------------------------------------
        # Backend truth has highest priority.
        # ----------------------------------------------------

        if (
            bool(
                state.get(
                    "order_created"
                )
            )
            or state.get(
                "checkout_status"
            ) == "completed"
        ):
            task_status = "completed"
            transition = "complete"

        elif isinstance(
            state.get(
                "transaction_error"
            ),
            dict,
        ):
            task_status = "failed"

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # If the workflow STARTED or SWITCHED, do not allow
        # awaiting_user_input from the PREVIOUS workflow to
        # overwrite the lifecycle returned for the NEW
        # workflow.
        # ----------------------------------------------------

        elif transition in {
            "start",
            "switch",
        }:
            if task_status is None:
                task_status = (
                    "collecting_information"
                    if missing
                    else "active"
                )

        # ----------------------------------------------------
        # Existing workflow continuation.
        # ----------------------------------------------------

        elif missing or bool(
            state.get(
                "awaiting_user_input"
            )
        ):
            task_status = (
                "collecting_information"
            )

        # ----------------------------------------------------
        # Active workflow with no missing information.
        # ----------------------------------------------------

        elif active_task:
            task_status = (
                task_status
                or "ready_to_execute"
            )

        # ----------------------------------------------------
        # No workflow.
        # ----------------------------------------------------

        else:
            task_status = "idle"
            transition = "idle"

        # ----------------------------------------------------
        # Goal handling.
        #
        # On a switch/start, do not inherit the previous
        # workflow goal if the LLM did not provide a new one.
        # ----------------------------------------------------

        if not workflow_goal:
            if transition in {
                "start",
                "switch",
            }:
                workflow_goal = _normalize_goal(
                    state.get(
                        "user_goal"
                    )
                )
            else:
                workflow_goal = (
                    _normalize_goal(
                        state.get(
                            "workflow_goal"
                        )
                    )
                    or _normalize_goal(
                        state.get(
                            "user_goal"
                        )
                    )
                )

        result = {
            "active_task": active_task,

            "task_status": task_status,

            "workflow_goal": workflow_goal,

            "workflow_transition": (
                transition
                or (
                    "continue"
                    if active_task
                    else "idle"
                )
            ),

            "workflow_reason": (
                str(
                    raw.get(
                        "reason"
                    )
                    or ""
                ).strip()
                or None
            ),
        }

    except Exception as exc:
        print(
            "[WORKFLOW LLM FALLBACK] "
            f"{type(exc).__name__}: {exc}"
        )

        fallback = _fallback_workflow(
            state
        )

        result = {
            **fallback,
            "workflow_reason": fallback.get(
                "reason"
            ),
        }

    # ========================================================
    # Workflow history
    # ========================================================

    previous_history = state.get(
        "workflow_history",
        [],
    )

    if not isinstance(
        previous_history,
        list,
    ):
        previous_history = []

    event = {
        "message": state.get(
            "message",
            "",
        ),

        "active_task": result.get(
            "active_task"
        ),

        "task_status": result.get(
            "task_status"
        ),

        "workflow_transition": result.get(
            "workflow_transition"
        ),

        "workflow_goal": result.get(
            "workflow_goal"
        ),
    }

    workflow_history = (
        previous_history
        + [event]
    )[-10:]

    # ========================================================
    # Workflow context
    # ========================================================

    workflow_context = state.get(
        "workflow_context",
        {},
    )

    if not isinstance(
        workflow_context,
        dict,
    ):
        workflow_context = {}

    workflow_context = dict(
        workflow_context
    )

    workflow_context.update(
        {
            "active_task": result.get(
                "active_task"
            ),

            "task_status": result.get(
                "task_status"
            ),

            "workflow_goal": result.get(
                "workflow_goal"
            ),

            "last_intent": state.get(
                "intent"
            ),

            "last_entities": state.get(
                "entities",
                {},
            ),

            "missing_fields": state.get(
                "missing_fields",
                [],
            ),
        }
    )

    # ========================================================
    # Debug output
    # ========================================================

    print(
        "\n============================================================\n"
        "[WORKFLOW NODE]\n"
        f"  active_task        = "
        f"{result.get('active_task')!r}\n"
        f"  task_status        = "
        f"{result.get('task_status')!r}\n"
        f"  workflow_goal      = "
        f"{result.get('workflow_goal')!r}\n"
        f"  transition         = "
        f"{result.get('workflow_transition')!r}\n"
        f"  missing_fields     = "
        f"{state.get('missing_fields', [])!r}\n"
        "============================================================"
    )

    return {
        **result,
        "workflow_history": workflow_history,
        "workflow_context": workflow_context,
    }


__all__ = [
    "workflow_node",
    "WORKFLOW_TRANSITIONS",
    "WORKFLOW_STATUSES",
]