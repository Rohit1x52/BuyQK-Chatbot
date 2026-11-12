from __future__ import annotations

from copy import deepcopy
from typing import Any

import logging

from sqlalchemy.orm import Session

from ai_engine.graph.builder import app
from ai_engine.memory.redis_memory import conversation_memory
from ai_engine.tools.results import ToolResult


MEMORY_MESSAGE_LIMIT = 10

logger = logging.getLogger("buyqk.runner")


PERSISTED_STATE_FIELDS = (


    "checkout_id",
    "checkout_status",
    "order_created",
    "order_creation_attempted",
    "checkout_completed",
    "order_id",


    "product_id",
    "product_name",
    "quantity",
    "selected_product",
    "product_search_results",


    "address_id",
    "selected_address_id",
    "address_action",
    "address_label",
    "address_line_2",
    "address_city",
    "address_state",
    "address_postal_code",


    "delivery_preference",


    "selected_payment_method",
    "payment_method",
    "billing_payment_method",


    "bill",
    "billing",
    "billing_items",

    "subtotal",
    "delivery_charge",
    "discount",
    "tax",
    "total_amount",
    "currency",


    "tool_name",
    "execution_result",


    "context",
    "planner",
    "planner_args",
    "planner_decision",
    "planned_action",
    "planned_tool",
    "planned_arguments",
    "planner_confidence",


    "policy_result",
    "policy_error",
    "policy",
    "decision",
    "decision_route",


    "tool_args",


    "order_reference",
    "order_reference_type",
    "awaiting_order_tracking_order_id",
    "awaiting_order_tracking_confirmation",


    "cancellation_reason",
    "cancellation_eligibility",
    "refund_eligibility",
    "awaiting_cancellation_reason",


    "detected_intents",
    "intent_entities",
    "intent_statuses",
    "pending_intents",
    "multi_intent",
    "orchestration_directive",
    "multi_intent_queue",
    "active_intent",
    "active_intent_index",
    "multi_intent_status",
    "multi_intent_initialized",
    "multi_intent_results",
    "active_intent_message",
    "multi_intent_error",
    "current_intent",
    "intent",
    "task_id",
    "task_ids",
    "task_graph",
    "task_dependencies",
    "task_outputs",
    "task_errors",
    "task_attempts",
    "ready_tasks",
    "running_tasks",
    "blocked_tasks",
    "cancelled_tasks",
    "task_execution_order",
    "task_execution_mode",
    "task_scheduler_status",
    "task_deadlock_detected",
    "task_cycle_detected",
    "task_outcome",
    "task_completed",
    "task_failed",
    "requires_confirmation",
    "user_confirmed",
    "interrupt_id",
    "interrupt_type",
    "interrupt_reason",
    "interrupt_payload",
    "interrupt_status",
    "resume_from_node",
    "checkpoint_id",
    "checkpoint_namespace",
    "confirmation_type",
    "confirmation_payload",
    "confirmation_expires_at",
    "execution_id",
    "parent_execution_id",
    "idempotency_key",
    "execution_status",
    "execution_attempt",
    "error_class",
    "error_code",
    "error_message",
    "error_details",
    "error_retryable",
    "recovery_action",
    "recovery_status",
    "retry_count",
    "max_retries",
    "retry_after_seconds",
    "fallback_used",
    "escalation_required",
    "tool_execution_id",
    "tool_idempotency_key",
    "tool_authorization",
    "tool_validation_errors",
    "tool_audit",
    "conversation_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "current_node",
    "node_execution_history",
    "execution_metadata",


    "active_task",
    "task_status",


    "current_missing_field",
    "follow_up_question",
    "awaiting_user_input",
    "next_missing",


    "commerce_vertical",


    "restaurant_id",
    "restaurant_name",
    "menu_id",
    "menu_items",


    "pharmacy_id",
    "pharmacy_name",
    "prescription_required",
    "prescription_status",


    "product_specifications",
    "product_variants",
    "comparison_results",


    "service_id",
    "service_name",
    "booking_date",
    "booking_start_time",
    "booking_end_time",
    "available_slots",
    "available_professionals",
    "professional_id",
    "professional_name",
    "booking_id",
    "booking_status",
    "payment_status",


    "user_goal",
    "detected_language",
    "references",


    "order_items",


    "cart_id",
    "cart_status",
    "cart_items",
    "cart_summary",
    "cart_action",
    "cart_result",
    "cart_checkout_ready",


    "transaction_error",


    "support_issue_type",
    "support_description",
    "support_transaction_id",
    "support_evidence_url",
    "support_verification",
    "support_resolved",
    "support_ticket_id",
    "support_ticket_reference",
    "support_status",
    "support_escalation_required",


    "merchant_id",
    "business_name",
    "category",
    "phone",
    "email",
    "address_text",
    "merchant_documents",
    "merchant_document_type",
    "merchant_document_reference",
    "merchant_document_status",
    "merchant_onboarding_status",
    "merchant_verification_status",
    "merchant_approval_status",


    "rider_id",
    "name",
    "vehicle_type",
    "license_number",
    "government_id",
    "bank_details",
    "rider_documents",
    "rider_document_type",
    "rider_document_reference",
    "rider_document_status",
    "rider_onboarding_status",
    "rider_verification_status",
    "rider_approval_status",


    "documents",
    "document_type",
    "document_reference",
    "onboarding_status",
    "verification_status",
    "approval_status",
)


def _safe_dict(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        return {}

    return deepcopy(
        value
    )


def _safe_list(
    value: Any,
) -> list[Any]:
    if not isinstance(
        value,
        list,
    ):
        return []

    return deepcopy(
        value
    )


def _extract_message_metadata(
    message: Any,
) -> dict[str, Any]:
    if not isinstance(
        message,
        dict,
    ):
        return {}

    metadata = message.get(
        "metadata"
    )

    return _safe_dict(
        metadata
    )


def _restore_previous_state(
    conversation_history: list[dict[str, Any]],
) -> dict[str, Any]:
    if not conversation_history:
        return {}


    for message in reversed(
        conversation_history
    ):

        if not isinstance(
            message,
            dict,
        ):
            continue

        if message.get(
            "role"
        ) != "assistant":
            continue

        metadata = _extract_message_metadata(
            message
        )

        if not metadata:
            continue

        restored: dict[str, Any] = {}


        for field in PERSISTED_STATE_FIELDS:

            if field in metadata:

                restored[field] = deepcopy(
                    metadata[field]
                )


        entities = metadata.get(
            "entities"
        )

        if isinstance(
            entities,
            dict,
        ):

            restored[
                "entities"
            ] = deepcopy(
                entities
            )


        missing_fields = metadata.get(
            "missing_fields"
        )

        if isinstance(
            missing_fields,
            list,
        ):

            restored[
                "missing_fields"
            ] = deepcopy(
                missing_fields
            )


        if (
            "next_missing"
            in metadata
        ):

            restored[
                "next_missing"
            ] = metadata[
                "next_missing"
            ]


        frontend_metadata = metadata.get(
            "frontend_metadata"
        )

        if isinstance(
            frontend_metadata,
            dict,
        ):

            restored[
                "frontend_metadata"
            ] = deepcopy(
                frontend_metadata
            )

        return restored

    return {}


def _build_initial_state(
    *,
    message: str,
    session_id: str,
    user_id: int,
    conversation_history: list[dict[str, Any]],
    previous_state: dict[str, Any],
    selected_address_id: int | None,
    payment_method: str | None,
    checkout_id: str | None,
    evidence_url: str | None = None,
    commerce_vertical: str | None = None,
    comparison_product_ids: list[int] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = deepcopy(
        previous_state
    )


    if (
        checkout_id is not None
        and str(checkout_id).strip()
    ):

        state[
            "checkout_id"
        ] = str(
            checkout_id
        ).strip()


    if evidence_url is not None and str(evidence_url).strip():
        state["support_evidence_url"] = str(evidence_url).strip()

    if commerce_vertical is not None:
        normalized_vertical = str(commerce_vertical).strip().casefold()
        if normalized_vertical:
            state["commerce_vertical"] = normalized_vertical
        else:
            state.pop("commerce_vertical", None)

    if comparison_product_ids is not None:
        state["comparison_product_ids"] = list(comparison_product_ids)


    state[
        "message"
    ] = message


    state["awaiting_user_input"] = False
    state["task_outcome"] = None
    state["interrupt_status"] = None

    state[
        "session_id"
    ] = session_id

    state[
        "user_id"
    ] = user_id


    state[
        "conversation_history"
    ] = conversation_history


    state[
        "entities"
    ] = _safe_dict(
        state.get(
            "entities",
            {},
        )
    )


    if selected_address_id is not None:

        state[
            "selected_address_id"
        ] = selected_address_id

        state[
            "address_id"
        ] = selected_address_id


    if (
        payment_method is not None
        and str(
            payment_method
        ).strip()
    ):

        clean_payment_method = str(
            payment_method
        ).strip()

        state[
            "payment_method"
        ] = clean_payment_method

        state[
            "selected_payment_method"
        ] = clean_payment_method


    state[
        "tool_name"
    ] = None

    state[
        "tool_args"
    ] = {}

    state[
        "tool_result"
    ] = None

    state[
        "response"
    ] = None


    state[
        "metadata"
    ] = {}


    state.setdefault(
        "active_task",
        None,
    )

    state.setdefault(
        "task_status",
        "idle",
    )

    state.setdefault(
        "execution_result",
        None,
    )

    state.setdefault(
        "selected_product",
        None,
    )

    state.setdefault(
        "missing_fields",
        [],
    )

    state.setdefault(
        "current_missing_field",
        None,
    )

    state.setdefault(
        "follow_up_question",
        None,
    )

    state.setdefault(
        "awaiting_user_input",
        False,
    )

    state.setdefault(
        "next_missing",
        None,
    )

    state.setdefault(
        "entities",
        {},
    )


    state.setdefault("detected_intents", [])
    state.setdefault("multi_intent_queue", [])
    state.setdefault("active_intent", None)
    state.setdefault("active_intent_index", None)
    state.setdefault("multi_intent_status", "idle")
    state.setdefault("multi_intent_initialized", False)
    state.setdefault("multi_intent_results", [])
    state.setdefault("active_intent_message", None)
    state.setdefault("multi_intent_error", None)


    state.setdefault(
        "commerce_vertical",
        None,
    )

    state.setdefault(
        "restaurant_id",
        None,
    )

    state.setdefault(
        "restaurant_name",
        None,
    )

    state.setdefault(
        "menu_id",
        None,
    )

    state.setdefault(
        "menu_items",
        [],
    )

    state.setdefault(
        "pharmacy_id",
        None,
    )

    state.setdefault(
        "pharmacy_name",
        None,
    )

    state.setdefault(
        "prescription_required",
        None,
    )

    state.setdefault(
        "prescription_status",
        None,
    )

    state.setdefault(
        "product_specifications",
        None,
    )

    state.setdefault(
        "product_variants",
        [],
    )

    state.setdefault(
        "comparison_results",
        [],
    )

    state.setdefault(
        "order_created",
        False,
    )

    state.setdefault(
        "order_creation_attempted",
        False,
    )

    state.setdefault(
        "checkout_completed",
        False,
    )

    state.setdefault(
        "cart_items",
        [],
    )

    state.setdefault(
        "order_items",
        [],
    )

    state.setdefault(
        "references",
        {},
    )


    for field in (
        "merchant_id",
        "business_name",
        "category",
        "phone",
        "email",
        "address_text",
        "merchant_document_type",
        "merchant_document_reference",
        "merchant_document_status",
        "merchant_onboarding_status",
        "merchant_verification_status",
        "merchant_approval_status",
        "rider_id",
        "name",
        "vehicle_type",
        "license_number",
        "government_id",
        "bank_details",
        "rider_document_type",
        "rider_document_reference",
        "rider_document_status",
        "rider_onboarding_status",
        "rider_verification_status",
        "rider_approval_status",
        "document_type",
        "document_reference",
        "onboarding_status",
        "verification_status",
        "approval_status",
    ):
        state.setdefault(field, None)

    for field in (
        "merchant_documents",
        "rider_documents",
        "documents",
    ):
        state.setdefault(field, [])

    return state


def _build_memory_metadata(
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}


    for field in PERSISTED_STATE_FIELDS:

        if field not in result:
            continue

        value = result.get(
            field
        )


        if field == "db":
            continue

        try:


            if isinstance(value, ToolResult):
                metadata[
                    field
                ] = value.to_dict()
            else:
                metadata[
                    field
                ] = deepcopy(
                    value
                )

        except Exception:


            continue


    metadata[
        "entities"
    ] = _safe_dict(
        result.get(
            "entities",
            {},
        )
    )


    metadata[
        "missing_fields"
    ] = _safe_list(
        result.get(
            "missing_fields",
            [],
        )
    )


    if (
        "next_missing"
        in result
    ):

        metadata[
            "next_missing"
        ] = result.get(
            "next_missing"
        )


    frontend_metadata = result.get(
        "metadata"
    )

    if isinstance(
        frontend_metadata,
        dict,
    ):

        metadata[
            "frontend_metadata"
        ] = deepcopy(
            frontend_metadata
        )

    return metadata


def _update_conversation_state(
    result: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(result)


    intent = str(
        updated.get(
            "intent"
        )
        or ""
    ).strip().lower()

    planner = updated.get(
        "planner"
    )

    if not isinstance(
        planner,
        dict,
    ):

        planner = {}

    action = str(
        planner.get(
            "action"
        )
        or ""
    ).strip().lower()

    missing = updated.get(
        "missing_fields"
    )

    if not isinstance(
        missing,
        list,
    ):

        missing = []

    order_created = bool(
        updated.get(
            "order_created",
            False,
        )
    )

    checkout_completed = bool(
        updated.get(
            "checkout_completed",
            False,
        )
    )

    tool_result = updated.get(
        "tool_result"
    )

    transaction_error = updated.get(
        "transaction_error"
    )


    if (
        intent
        and intent != "general"
    ):

        updated[
            "active_task"
        ] = intent

    elif action in {
        "answer",
        "end_conversation",
    }:


        if (
            not updated.get(
                "active_task"
            )
        ):

            updated[
                "active_task"
            ] = None


    support_completed = bool(
        updated.get("support_resolved")
        or updated.get("support_ticket_id") is not None
    )

    if support_completed:
        updated[
            "task_status"
        ] = "completed"

    elif (
        order_created
        or checkout_completed
    ):

        updated[
            "task_status"
        ] = "completed"

    elif transaction_error:

        updated[
            "task_status"
        ] = "failed"

    elif missing:

        updated[
            "task_status"
        ] = "collecting"

    elif (
        tool_result is not None
        or action
        not in {
            "",
            "answer",
            "ask_clarification",
        }
    ):

        updated[
            "task_status"
        ] = "executing"

    elif (
        intent
        and intent != "general"
    ):

        updated[
            "task_status"
        ] = "active"

    else:

        updated[
            "task_status"
        ] = "idle"


    try:
        updated[
            "execution_result"
        ] = deepcopy(tool_result)
    except Exception:
        updated[
            "execution_result"
        ] = tool_result


    selected_product = updated.get(
        "selected_product"
    )

    if isinstance(
        selected_product,
        dict,
    ):
        updated[
            "selected_product"
        ] = deepcopy(
            selected_product
        )
    elif selected_product is None:
        updated[
            "selected_product"
        ] = None


    updated[
        "missing_fields"
    ] = list(
        missing
    )

    return updated


def _thread_config(
    session_id: str,
    user_id: int,
    db: Session,
) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": session_id,
            "user_id": str(user_id),
            "db": db,
        }
    }


def _snapshot_interrupts(snapshot: Any) -> list[Any]:
    tasks = getattr(snapshot, "tasks", None)
    if not isinstance(tasks, (list, tuple)):
        return []

    interrupts: list[Any] = []
    for task in tasks:
        task_interrupts = getattr(task, "interrupts", None)
        if isinstance(task_interrupts, (list, tuple)):
            interrupts.extend(task_interrupts)
    return interrupts


def _snapshot_values(snapshot: Any) -> dict[str, Any]:
    values = getattr(snapshot, "values", None)
    return dict(values) if isinstance(values, dict) else {}


def _get_checkpoint_snapshot(config: dict[str, Any]) -> Any | None:
    if getattr(app, "checkpointer", None) is None:
        return None

    get_state = getattr(app, "get_state", None)
    if not callable(get_state):
        return None
    return get_state(config)


def _invoke_graph(
    initial_state: dict[str, Any],
    config: dict[str, Any],
    resume_value: Any = None,
) -> dict[str, Any]:
    snapshot = _get_checkpoint_snapshot(config)
    interrupts = _snapshot_interrupts(snapshot) if snapshot is not None else []

    if interrupts:
        from langgraph.types import Command

        value = resume_value
        if value is None:
            value = initial_state.get("message")
        resume_updates = {
            "message": initial_state.get("message"),
            "interrupt_status": None,
        }
        for field in (
            "selected_address_id",
            "address_id",
            "payment_method",
            "selected_payment_method",
            "checkout_id",
            "support_evidence_url",
            "commerce_vertical",
            "comparison_product_ids",
        ):
            if field in initial_state:
                resume_updates[field] = initial_state[field]
        result = app.invoke(
            Command(update=resume_updates, resume=value),
            config=config,
        )
    else:
        result = app.invoke(initial_state, config=config)

    if not isinstance(result, dict):
        raise RuntimeError(
            "BuyQK AI graph returned an invalid state."
        )

    return result


def _is_interrupted(result: dict[str, Any]) -> bool:
    if result.get("__interrupt__"):
        return True

    if result.get("interrupt_status") in {
        "pending",
        "waiting",
        "interrupted",
    }:
        return True

    return False


def _normalize_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    tool_result = result.get("tool_result")
    if tool_result is None:
        return result

    if isinstance(tool_result, ToolResult):
        return result

    if isinstance(tool_result, dict):
        return result

    raise RuntimeError(
        "Graph produced an invalid tool_result. "
        "Expected ToolResult or dict, got "
        f"{type(tool_result).__name__}."
    )


def run_chat(
    message: str,
    session_id: str,
    user_id: int,
    db: Session,
    selected_address_id: int | None = None,
    payment_method: str | None = None,
    checkout_id: str | None = None,
    evidence_url: str | None = None,
    commerce_vertical: str | None = None,
    comparison_product_ids: list[int] | None = None,
    resume_value: Any = None,
) -> dict[str, Any]:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message is required.")

    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id is required.")

    if user_id is None:
        raise ValueError("user_id is required.")

    if db is None:
        raise ValueError("db session is required.")

    clean_message = message.strip()
    clean_session_id = session_id.strip()

    conversation_history = conversation_memory.get_recent_messages(
        session_id=clean_session_id,
        limit=MEMORY_MESSAGE_LIMIT,
    )
    conversation_history = _safe_list(conversation_history)

    previous_state = _restore_previous_state(conversation_history)

    initial_state = _build_initial_state(
        message=clean_message,
        session_id=clean_session_id,
        user_id=user_id,
        conversation_history=conversation_history,
        previous_state=previous_state,
        selected_address_id=selected_address_id,
        payment_method=payment_method,
        checkout_id=checkout_id,
        evidence_url=evidence_url,
        commerce_vertical=commerce_vertical,
        comparison_product_ids=comparison_product_ids,
    )

    config = _thread_config(
        session_id=clean_session_id,
        user_id=user_id,
        db=db,
    )

    result = _invoke_graph(
        initial_state=initial_state,
        config=config,
        resume_value=resume_value,
    )
    result = _normalize_tool_result(result)

    interrupted = _is_interrupted(result)

    if not interrupted:
        result = _update_conversation_state(result)

    response = result.get("response")
    if not isinstance(response, str) or not response.strip():
        if interrupted:
            response = None
        else:
            raise RuntimeError(
                "BuyQK AI graph completed without a response."
            )
    else:
        response = response.strip()

    memory_metadata = _build_memory_metadata(result)
    memory_metadata["interrupt_pending"] = interrupted

    if interrupted:
        memory_metadata["interrupt_status"] = (
            result.get("interrupt_status") or "pending"
        )

    conversation_memory.add_message(
        session_id=clean_session_id,
        role="user",
        content=clean_message,
    )

    conversation_memory.add_message(
        session_id=clean_session_id,
        role="assistant",
        content=response or "",
        metadata=memory_metadata,
    )

    conversation_memory.save_graph_state(
        session_id=clean_session_id,
        state_dict=memory_metadata,
    )
    conversation_memory.touch_session(clean_session_id)

    if interrupted:
        result["interrupt_pending"] = True
        result.setdefault("interrupt_status", "pending")

    return result


__all__ = [
    "run_chat",
    "PERSISTED_STATE_FIELDS",
    "_build_initial_state",
    "_build_memory_metadata",
    "_restore_previous_state",
    "_update_conversation_state",
]
