"""
Phase 13 — Multi-intent orchestration node.

Coordinates detected intents and queue state. It does not execute backend
operations or infer transaction success.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

GraphState = dict[str, Any]

_VALID_OUTCOMES = {"completed", "failed"}
_WAIT_DIRECTIVES = {"wait_for_input", "await_input"}


def _intent_name(value: Any) -> str | None:
    if isinstance(value, str):
        name = value.strip()
    elif isinstance(value, dict):
        name = value.get("intent")
        name = name.strip() if isinstance(name, str) else ""
    else:
        name = ""
    return name or None


def _ordered_unique_intents(state: GraphState) -> list[str]:
    """Read detected intents without reclassifying the message."""
    candidates = state.get("detected_intents")
    if not isinstance(candidates, list) or not candidates:
        candidates = state.get("intents")

    if isinstance(candidates, list) and candidates:
        values = [_intent_name(item) for item in candidates]
    else:
        values = [_intent_name(state.get("intent"))]

    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _read_multi_state(state: GraphState) -> dict[str, Any]:
    value = state.get("multi_intent")
    return deepcopy(value) if isinstance(value, dict) else {}


def _existing_queue(
    state: GraphState,
    multi: dict[str, Any],
) -> list[str]:
    for candidate in (
        state.get("pending_intents"),
        multi.get("pending_intents"),
        multi.get("queue"),
    ):
        if isinstance(candidate, list):
            return [
                name
                for item in candidate
                if (name := _intent_name(item))
            ]
    return []


def _existing_statuses(
    state: GraphState,
    multi: dict[str, Any],
) -> dict[str, str]:
    value = state.get("intent_statuses")
    if not isinstance(value, dict):
        value = multi.get("intent_statuses")

    if not isinstance(value, dict):
        return {}

    return {
        key: status
        for key, status in value.items()
        if isinstance(key, str) and isinstance(status, str)
    }


def _outcome_status(state: GraphState) -> str | None:
    """Accept only explicit task outcome signals."""
    outcome = state.get("task_outcome")

    if isinstance(outcome, dict):
        status = outcome.get("status")
        if (
            isinstance(status, str)
            and status.strip().lower() in _VALID_OUTCOMES
        ):
            return status.strip().lower()

    if state.get("task_failed") is True:
        return "failed"

    if state.get("task_completed") is True:
        return "completed"

    return None


def _emit(
    state: GraphState,
    *,
    active: str | None,
    queue: list[str],
    statuses: dict[str, str],
    directive: str,
    multi: dict[str, Any],
) -> GraphState:
    """Return coordinator metadata using stable state-field names."""
    multi.update(
        active_intent=active,
        pending_intents=list(queue),
        queue=list(queue),
        intent_statuses=dict(statuses),
        directive=directive,
    )

    result: GraphState = {
        "active_intent": active,
        "current_intent": active,
        "pending_intents": list(queue),
        "intent_statuses": dict(statuses),
        "multi_intent": multi,
        "orchestration_directive": directive,
    }

    if active:
        result["intent"] = active

        intent_entities = state.get("intent_entities")
        if isinstance(intent_entities, dict):
            bucket = intent_entities.get(active)
            if isinstance(bucket, dict):
                result["entities"] = dict(bucket)
            elif active in intent_entities:
                # Do not borrow entities from another intent.
                result["entities"] = {}

    return result


def multi_intent_node(state: GraphState) -> GraphState:
    """
    Select or resume one task, advancing only after explicit completion.

    Directives:
      execute_active_intent
      wait_for_input
      stop_on_failure
      all_complete
      no_intent
    """
    multi = _read_multi_state(state)
    detected = _ordered_unique_intents(state)
    statuses = _existing_statuses(state, multi)

    active = (
        _intent_name(state.get("active_intent"))
        or _intent_name(state.get("current_intent"))
        or _intent_name(multi.get("active_intent"))
    )
    queue = _existing_queue(state, multi)

    # Initialize a new queue only when there is no persisted active task
    # or queue. This prevents a clarification reply from replacing the queue.
    if not active and not queue:
        if not detected:
            return _emit(
                state,
                active=None,
                queue=[],
                statuses=statuses,
                directive="no_intent",
                multi=multi,
            )

        active, queue = detected[0], detected[1:]

        for item in detected:
            statuses.setdefault(item, "pending")

        statuses[active] = "active"

    if active:
        statuses.setdefault(active, "active")
        if statuses.get(active) not in {"completed", "failed"}:
            statuses[active] = "active"

    # A current-turn flag overrides a stale persisted wait directive.
    if "awaiting_user_input" in state:
        awaiting = state.get("awaiting_user_input") is True
    else:
        awaiting = (
            state.get("orchestration_directive") in _WAIT_DIRECTIVES
            or multi.get("directive") in _WAIT_DIRECTIVES
        )

    if awaiting and active:
        return _emit(
            state,
            active=active,
            queue=queue,
            statuses=statuses,
            directive="wait_for_input",
            multi=multi,
        )

    outcome = _outcome_status(state)

    if active and outcome == "failed":
        statuses[active] = "failed"
        return _emit(
            state,
            active=active,
            queue=queue,
            statuses=statuses,
            directive="stop_on_failure",
            multi=multi,
        )

    if active and outcome == "completed":
        statuses[active] = "completed"
        active = None

    if active:
        # Without explicit completion, the current task remains active.
        return _emit(
            state,
            active=active,
            queue=queue,
            statuses=statuses,
            directive="execute_active_intent",
            multi=multi,
        )

    # Only a completed task reaches this point and advances the queue.
    while queue:
        next_intent = queue.pop(0)

        if statuses.get(next_intent) == "completed":
            continue

        if statuses.get(next_intent) == "failed":
            queue.insert(0, next_intent)
            return _emit(
                state,
                active=next_intent,
                queue=queue,
                statuses=statuses,
                directive="stop_on_failure",
                multi=multi,
            )

        active = next_intent
        statuses[active] = "active"
        break

    if active is None:
        return _emit(
            state,
            active=None,
            queue=[],
            statuses=statuses,
            directive="all_complete",
            multi=multi,
        )

    return _emit(
        state,
        active=active,
        queue=queue,
        statuses=statuses,
        directive="execute_active_intent",
        multi=multi,
    )