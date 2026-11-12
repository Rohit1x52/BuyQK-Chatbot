from __future__ import annotations

import logging
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ai_engine.graph.state import GraphState
from ai_engine.nodes.context_node import context_node
from ai_engine.nodes.intent_node import intent_node
from ai_engine.nodes.entity_node import entity_node
from ai_engine.nodes.followup_node import followup_node
from ai_engine.nodes.planner_node import planner_node
from ai_engine.nodes.policy_node import policy_node
from ai_engine.nodes.decision_node import decision_node
from ai_engine.nodes.tool_node import tool_node
from ai_engine.nodes.response_node import response_node
from ai_engine.nodes.multi_intent_node import multi_intent_node

logger = logging.getLogger("buyqk.graph")

ROUTE_TOOL = "tool"
ROUTE_RESPONSE = "response"
ROUTE_PLANNER = "planner"

TOOLLESS_ACTIONS = frozenset(
    {
        "ANSWER",
        "ASK_CLARIFICATION",
        "CONFIRM",
        "END_CONVERSATION",
        "START_CHECKOUT",
        "MODIFY_CHECKOUT",
    }
)

WAITING_RESULT_TYPES = frozenset(
    {
        "address_selection",
        "payment_selection",
        "product_input",
        "quantity_input",
        "confirmation",
        "user_confirmation",
        "clarification",
    }
)

CHECKOUT_INTENTS = frozenset(
    {
        "order_create",
        "checkout",
        "checkout_cart",
        "cart_checkout",
    }
)

BLOCKING_CHECKOUT_FIELDS = frozenset(
    {
        "product_name",
        "quantity",
    }
)

WAIT_DIRECTIVES = frozenset(
    {
        "wait_for_input",
        "await_input",
    }
)


def _normalize_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _get_missing_fields(state: GraphState) -> list[str]:
    value = state.get("missing_fields")
    if not isinstance(value, (list, tuple, set)):
        return []
    return [
        normalized
        for field in value
        if (normalized := _normalize_string(field))
    ]


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _get_entities(state: GraphState) -> dict[str, Any]:
    entities = state.get("entities")
    return dict(entities) if isinstance(entities, dict) else {}


def _get_intent(state: GraphState) -> str | None:
    candidates = (
        state.get("active_intent"),
        state.get("current_intent"),
        state.get("intent"),
    )
    for candidate in candidates:
        normalized = _normalize_string(candidate)
        if normalized:
            return normalized
    return None


def _get_action(state: GraphState) -> str | None:
    candidates = (
        state.get("action"),
        state.get("decision_action"),
    )
    for candidate in candidates:
        normalized = _normalize_string(candidate)
        if normalized:
            return normalized.upper()

    for key in ("decision", "policy_result"):
        value = state.get(key)
        if isinstance(value, dict):
            normalized = _normalize_string(value.get("action"))
            if normalized:
                return normalized.upper()
    return None


def _get_tool_name(state: GraphState) -> str | None:
    tool_name = _normalize_string(state.get("tool_name"))
    if tool_name:
        return tool_name.lower()

    for key in ("decision", "policy_result"):
        value = state.get(key)
        if isinstance(value, dict):
            tool_name = _normalize_string(
                value.get("tool") or value.get("tool_name")
            )
            if tool_name:
                return tool_name.lower()
    return None


def _get_tool_result(state: GraphState) -> tuple[bool | None, Any, str | None]:
    result = state.get("tool_result")
    if result is None:
        return None, None, None

    if isinstance(result, dict):
        success = result.get("success")
        data = result.get("data")
        result_type = result.get("type")
    else:
        success = getattr(result, "success", None)
        data = getattr(result, "data", None)
        result_type = getattr(result, "type", None)

    if isinstance(data, dict):
        result_type = result_type or data.get("type")

    return success if isinstance(success, bool) else None, data, _normalize_string(result_type)


def _is_awaiting_user_input(state: GraphState) -> bool:
    if state.get("awaiting_user_input") is True:
        return True

    if state.get("orchestration_directive") in WAIT_DIRECTIVES:
        return True

    multi = state.get("multi_intent")
    if isinstance(multi, dict) and multi.get("directive") in WAIT_DIRECTIVES:
        return True

    metadata = state.get("metadata")
    if isinstance(metadata, dict):
        if metadata.get("type") in WAITING_RESULT_TYPES:
            return True
        if metadata.get("awaiting_user_input") is True:
            return True

    _, _, result_type = _get_tool_result(state)
    return result_type in WAITING_RESULT_TYPES


def _checkout_has_blocking_missing_field(state: GraphState) -> bool:
    intent = _get_intent(state)
    action = _get_action(state)

    if intent not in CHECKOUT_INTENTS and action not in {
        "START_CHECKOUT",
        "MODIFY_CHECKOUT",
        "CREATE_ORDER",
    }:
        return False

    return bool(BLOCKING_CHECKOUT_FIELDS.intersection(_get_missing_fields(state)))


def _policy_explicitly_denied(state: GraphState) -> bool:
    if state.get("policy_error"):
        return True

    result = state.get("policy_result")
    if not isinstance(result, dict):
        return False

    if result.get("allowed") is False:
        return True
    if result.get("approved") is False:
        return True
    if result.get("authorized") is False:
        return True

    status = _normalize_string(result.get("status"))
    return bool(status and status.lower() in {"denied", "blocked", "rejected"})


def _tool_is_safe_to_execute(state: GraphState) -> bool:
    tool_name = _get_tool_name(state)
    action = _get_action(state)

    if not tool_name:
        return False
    if action in TOOLLESS_ACTIONS:
        return False
    if _checkout_has_blocking_missing_field(state):
        return False
    if _policy_explicitly_denied(state):
        return False
    if state.get("awaiting_user_input") is True:
        return False
    if state.get("requires_confirmation") is True and state.get("user_confirmed") is not True:
        return False

    return True


def _legacy_multi_intent_state(state: GraphState) -> dict[str, Any]:
    multi = state.get("multi_intent")
    multi = dict(multi) if isinstance(multi, dict) else {}

    active = _normalize_string(state.get("active_intent"))
    pending = state.get("pending_intents")
    statuses = state.get("intent_statuses")

    if active or isinstance(pending, list):
        return {
            **multi,
            "active_intent": active or multi.get("active_intent"),
            "pending_intents": list(pending) if isinstance(pending, list) else [],
            "intent_statuses": dict(statuses) if isinstance(statuses, dict) else {},
        }

    legacy_queue = state.get("multi_intent_queue")
    active_index = state.get("active_intent_index")

    if not isinstance(legacy_queue, list) or not legacy_queue:
        return multi

    normalized_queue: list[dict[str, Any]] = []
    for item in legacy_queue:
        if isinstance(item, dict):
            normalized_queue.append(dict(item))
        elif isinstance(item, str):
            normalized_queue.append({"intent": item})
    if not normalized_queue:
        return multi

    if not isinstance(active_index, int) or not 0 <= active_index < len(normalized_queue):
        active_index = 0

    active_item = normalized_queue[active_index]
    active = _normalize_string(active_item.get("intent"))
    pending_items = normalized_queue[active_index + 1:]
    pending = [
        name
        for item in pending_items
        if (name := _normalize_string(item.get("intent")))
    ]

    statuses = {}
    for index, item in enumerate(normalized_queue):
        name = _normalize_string(item.get("intent"))
        if not name:
            continue
        if index < active_index:
            statuses[name] = "completed"
        elif index == active_index:
            statuses[name] = "active"
        else:
            statuses[name] = "pending"

    return {
        **multi,
        "active_intent": active,
        "pending_intents": pending,
        "intent_statuses": statuses,
    }


def _route_after_followup(state: GraphState) -> str:
    multi = _legacy_multi_intent_state(state)
    active = _normalize_string(multi.get("active_intent"))
    pending = multi.get("pending_intents")
    directive = _normalize_string(state.get("orchestration_directive"))

    if _is_awaiting_user_input(state):
        logger.debug("followup_route=response reason=awaiting_user_input")
        return ROUTE_RESPONSE

    if active and directive in WAIT_DIRECTIVES:
        logger.debug("followup_route=response reason=coordinator_wait")
        return ROUTE_RESPONSE

    if isinstance(pending, list) and active and state.get("followup_required") is True:
        return ROUTE_RESPONSE

    return ROUTE_PLANNER


def _route_after_multi_intent(state: GraphState) -> str:
    if state.get("orchestration_directive") == "execute_active_intent":
        return "active"
    return ROUTE_RESPONSE


def _derive_task_outcome(state: GraphState, waiting: bool) -> dict[str, Any] | None:
    if waiting:
        return None

    explicit = state.get("task_outcome")
    if isinstance(explicit, dict):
        status = _normalize_string(explicit.get("status"))
        if status and status.lower() in {"completed", "failed"}:
            return dict(explicit)

    if state.get("task_failed") is True:
        return {"status": "failed", "source": "workflow"}

    if state.get("task_completed") is True:
        return {"status": "completed", "source": "workflow"}

    success, _, _ = _get_tool_result(state)
    if success is True:
        return {"status": "completed", "source": "tool_result"}
    if success is False:
        return {"status": "failed", "source": "tool_result"}

    action = _get_action(state)
    if action in {"ANSWER", "END_CONVERSATION"}:
        return {"status": "completed", "source": "tool_less_action"}

    if state.get("transaction_error"):
        return {"status": "failed", "source": "transaction_error"}

    return None


def _coordinate_after_response(state: GraphState) -> GraphState:
    waiting = _is_awaiting_user_input(state)
    outcome = _derive_task_outcome(state, waiting)
    normalized_multi = _legacy_multi_intent_state(state)

    coordinator_input = {
        **state,
        **normalized_multi,
        "awaiting_user_input": waiting,
    }
    if outcome is not None:
        coordinator_input["task_outcome"] = outcome
    else:
        coordinator_input.pop("task_outcome", None)

    coordinated = multi_intent_node(coordinator_input)
    updates = dict(coordinated)
    updates["awaiting_user_input"] = waiting

    active = _normalize_string(coordinated.get("active_intent"))
    pending = coordinated.get("pending_intents")
    statuses = coordinated.get("intent_statuses")
    directive = coordinated.get("orchestration_directive")

    if active or isinstance(pending, list):
        legacy_queue = []
        if active:
            legacy_queue.append(
                {
                    "intent": active,
                    "status": "active",
                }
            )
        for name in pending if isinstance(pending, list) else []:
            if isinstance(name, str):
                legacy_queue.append(
                    {
                        "intent": name,
                        "status": "pending",
                    }
                )

        updates["multi_intent_queue"] = legacy_queue
        updates["active_intent_index"] = 0 if active else None
        updates["multi_intent_status"] = (
            "waiting" if waiting else
            "active" if directive == "execute_active_intent" else
            "failed" if directive == "stop_on_failure" else
            "completed" if directive == "all_complete" else
            "idle"
        )
        updates["multi_intent_initialized"] = True
        if isinstance(statuses, dict):
            updates["intent_statuses"] = dict(statuses)

    if directive == "execute_active_intent":
        updates.update(
            {
                "tool_result": None,
                "tool_name": None,
                "tool_args": {},
                "planner_args": {},
                "policy_result": None,
                "policy_error": None,
                "decision": None,
                "decision_route": None,
                "metadata": {},
                "response": None,
                "awaiting_user_input": False,
                "task_outcome": None,
                "task_completed": False,
                "task_failed": False,
                "transaction_error": None,
                "followup_required": False,
            }
        )

    logger.info(
        "multi_intent_transition",
        extra={
            "active_intent": active,
            "pending_intent_count": len(pending) if isinstance(pending, list) else 0,
            "directive": directive,
            "waiting": waiting,
            "outcome": outcome.get("status") if outcome else None,
        },
    )
    return updates


def _route_after_multi_intent_response(state: GraphState) -> str:
    if state.get("orchestration_directive") == "execute_active_intent":
        return "active"
    return "end"


def _route_after_decision(state: GraphState) -> str:
    action = _get_action(state)
    tool_name = _get_tool_name(state)
    routable_state = state

    if (
        action == "SEARCH_PRODUCTS"
        and not tool_name
        and _get_intent(state) == "product_search"
        and _has_value(_get_entities(state).get("product_name"))
    ):
        tool_name = "search_products"
        routable_state = {**state, "tool_name": tool_name}

    decision_route = _normalize_string(state.get("decision_route"))

    if action in TOOLLESS_ACTIONS:
        logger.debug("decision_route=response reason=toolless_action action=%s", action)
        return ROUTE_RESPONSE

    if decision_route:
        normalized_route = decision_route.lower()
        if normalized_route == ROUTE_TOOL:
            if _tool_is_safe_to_execute(routable_state):
                return ROUTE_TOOL
            logger.warning(
                "tool_route_blocked",
                extra={
                    "intent": _get_intent(state),
                    "tool_name": tool_name,
                    "reason": "execution_guard",
                },
            )
            return ROUTE_RESPONSE
        if normalized_route == ROUTE_RESPONSE:
            return ROUTE_RESPONSE

    if tool_name and _tool_is_safe_to_execute(routable_state):
        return ROUTE_TOOL

    if tool_name:
        logger.warning(
            "tool_route_blocked",
            extra={
                "intent": _get_intent(state),
                "tool_name": tool_name,
                "reason": "execution_guard",
            },
        )

    return ROUTE_RESPONSE


def _create_tool_wrapper(default_db: Any = None) -> Callable[..., GraphState]:
    def _tool_wrapper(
        state: GraphState,
        config: RunnableConfig,
    ) -> GraphState:
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        db = configurable.get("db") if isinstance(configurable, dict) else None
        if db is None:
            db = default_db

        current_state = dict(state)

        if (
            _get_intent(current_state) == "product_search"
            and _get_action(current_state) == "SEARCH_PRODUCTS"
            and not _get_tool_name(current_state)
            and _has_value(_get_entities(current_state).get("product_name"))
        ):
            current_state["tool_name"] = "search_products"

        if not _tool_is_safe_to_execute(current_state):
            logger.warning(
                "tool_execution_rejected",
                extra={
                    "intent": _get_intent(current_state),
                    "tool_name": _get_tool_name(current_state),
                },
            )
            return {
                "tool_name": None,
                "tool_result": {
                    "success": False,
                    "type": "execution_blocked",
                    "error": "Tool execution did not pass graph-level safety checks.",
                },
                "decision_route": ROUTE_RESPONSE,
                "task_outcome": {"status": "failed", "source": "execution_guard"},
            }

        try:
            result = tool_node(current_state, db)
            if not isinstance(result, dict):
                logger.error(
                    "tool_node_invalid_output",
                    extra={"tool_name": _get_tool_name(current_state)},
                )
                return {
                    "tool_result": {
                        "success": False,
                        "type": "invalid_tool_output",
                        "error": "The tool returned an invalid result.",
                    },
                    "task_outcome": {"status": "failed", "source": "tool_contract"},
                }
            return result
        except Exception as exc:
            logger.exception(
                "tool_execution_exception",
                extra={
                    "intent": _get_intent(current_state),
                    "tool_name": _get_tool_name(current_state),
                    "error_type": type(exc).__name__,
                },
            )
            return {
                "tool_result": {
                    "success": False,
                    "type": "tool_execution_error",
                    "error": type(exc).__name__,
                },
                "transaction_error": type(exc).__name__,
                "task_outcome": {"status": "failed", "source": "tool_exception"},
            }

    return _tool_wrapper


def build_graph(
    db: Any = None,
    checkpointer: Any = None,
    *,
    require_checkpointer: bool = False,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
):
    graph = StateGraph(GraphState)

    graph.add_node("context", context_node)
    graph.add_node("intent", intent_node)
    graph.add_node("multi_intent", multi_intent_node)
    graph.add_node("multi_intent_after_response", _coordinate_after_response)
    graph.add_node("entity", entity_node)
    graph.add_node("followup", followup_node)
    graph.add_node("planner", planner_node)
    graph.add_node("policy", policy_node)
    graph.add_node("decision", decision_node)
    graph.add_node("tool", _create_tool_wrapper(db))
    graph.add_node("response", response_node)

    graph.add_edge(START, "context")
    graph.add_edge("context", "intent")
    graph.add_edge("intent", "multi_intent")

    graph.add_conditional_edges(
        "multi_intent",
        _route_after_multi_intent,
        {
            "active": "entity",
            ROUTE_RESPONSE: "response",
        },
    )

    graph.add_edge("entity", "followup")

    graph.add_conditional_edges(
        "followup",
        _route_after_followup,
        {
            ROUTE_RESPONSE: "response",
            ROUTE_PLANNER: "planner",
        },
    )

    graph.add_edge("planner", "policy")
    graph.add_edge("policy", "decision")

    graph.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            ROUTE_TOOL: "tool",
            ROUTE_RESPONSE: "response",
        },
    )

    graph.add_edge("tool", "response")
    graph.add_edge("response", "multi_intent_after_response")

    graph.add_conditional_edges(
        "multi_intent_after_response",
        _route_after_multi_intent_response,
        {
            "active": "entity",
            "end": END,
        },
    )

    if checkpointer is None:
        try:
            from ai_engine.checkpointer.durable_redis_saver import get_durable_checkpointer
            checkpointer = get_durable_checkpointer()
        except Exception:
            logger.exception("durable_checkpointer_initialization_failed")
            checkpointer = None

    if require_checkpointer and checkpointer is None:
        raise RuntimeError(
            "A durable checkpointer is required but could not be initialized."
        )

    compile_options: dict[str, Any] = {}
    if checkpointer is not None:
        compile_options["checkpointer"] = checkpointer
    if interrupt_before:
        compile_options["interrupt_before"] = interrupt_before
    if interrupt_after:
        compile_options["interrupt_after"] = interrupt_after

    return graph.compile(**compile_options)


app = build_graph()

__all__ = ["app", "build_graph"]
