from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from ai_engine.graph.state import GraphState


# =========================================================
# Nodes
# =========================================================

from ai_engine.nodes.context_node import (
    context_node,
)

from ai_engine.nodes.intent_node import (
    intent_node,
)

from ai_engine.nodes.entity_node import (
    entity_node,
)

from ai_engine.nodes.followup_node import (
    followup_node,
)

from ai_engine.nodes.planner_node import (
    planner_node,
)

from ai_engine.nodes.policy_node import (
    policy_node,
)

from ai_engine.nodes.decision_node import (
    decision_node,
)

from ai_engine.nodes.tool_node import (
    tool_node,
)

from ai_engine.nodes.response_node import (
    response_node,
)

from ai_engine.nodes.multi_intent_node import (
    multi_intent_node,
)


# =========================================================
# Constants
# =========================================================

ROUTE_TOOL = "tool"
ROUTE_RESPONSE = "response"
ROUTE_PLANNER = "planner"


# =========================================================
# Conversational / Tool-less Actions
# =========================================================
#
# These actions must NEVER reach Tool Node.
#
# They are presentation/workflow actions.
#
# =========================================================

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


# =========================================================
# Checkout Required Fields
# =========================================================

CHECKOUT_REQUIRED_FIELDS = (
    "product_name",
    "quantity",
    "address_selection",
    "payment_method",
)


# =========================================================
# Helper: Normalize String
# =========================================================


def _normalize_string(
    value: Any,
) -> str | None:
    """
    Safely normalize a possible string value.
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


# =========================================================
# Helper: Normalize Missing Fields
# =========================================================


def _get_missing_fields(
    state: GraphState,
) -> list[str]:
    """
    Read missing_fields from GraphState.

    Always returns a clean list of strings.

    This function does NOT calculate missing fields.
    It only reads the value produced by the upstream
    workflow nodes.
    """

    value = state.get(
        "missing_fields"
    )

    if not isinstance(
        value,
        (list, tuple, set),
    ):
        return []

    result: list[str] = []

    for field in value:
        normalized = _normalize_string(
            field
        )

        if normalized:
            result.append(
                normalized
            )

    return result


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _get_entities(state: GraphState) -> dict[str, Any]:
    entities = state.get("entities")
    return dict(entities) if isinstance(entities, dict) else {}


# =========================================================
# Helper: Read Intent
# =========================================================


def _get_intent(
    state: GraphState,
) -> str | None:
    """
    Read normalized intent from state.
    """

    return _normalize_string(
        state.get("intent")
    )


# =========================================================
# Helper: Read Action
# =========================================================


def _get_action(
    state: GraphState,
) -> str | None:

    candidates = (
        state.get("action"),
        state.get("decision_action"),
    )

    for value in candidates:
        normalized = _normalize_string(
            value
        )

        if normalized:
            return normalized.upper()

    decision = state.get(
        "decision"
    )

    if isinstance(
        decision,
        dict,
    ):
        normalized = _normalize_string(
            decision.get("action")
        )

        if normalized:
            return normalized.upper()

    policy_result = state.get(
        "policy_result"
    )

    if isinstance(
        policy_result,
        dict,
    ):
        normalized = _normalize_string(
            policy_result.get("action")
        )

        if normalized:
            return normalized.upper()

    return None


# =========================================================
# Helper: Read Tool
# =========================================================


def _get_tool_name(
    state: GraphState,
) -> str | None:

    tool_name = _normalize_string(
        state.get("tool_name")
    )

    if tool_name:
        return tool_name.lower()

    decision = state.get(
        "decision"
    )

    if isinstance(
        decision,
        dict,
    ):
        tool_name = _normalize_string(
            decision.get("tool")
            or decision.get("tool_name")
        )

        if tool_name:
            return tool_name.lower()

    policy_result = state.get(
        "policy_result"
    )

    if isinstance(
        policy_result,
        dict,
    ):
        tool_name = _normalize_string(
            policy_result.get("tool")
            or policy_result.get("tool_name")
        )

        if tool_name:
            return tool_name.lower()

    return None


# =========================================================
# Helper: Awaiting User Input
# =========================================================


def _is_awaiting_user_input(
    state: GraphState,
) -> bool:
    return bool(
        state.get(
            "awaiting_user_input"
        )
    )


# =========================================================
# Helper: Checkout Incomplete
# =========================================================


def _checkout_has_blocking_missing_field(
    state: GraphState,
) -> bool:

    intent = _get_intent(
        state
    )

    action = _get_action(
        state
    )

    missing_fields = _get_missing_fields(
        state
    )

    checkout_intent = intent in {
        "order_create",
        "checkout",
        "checkout_cart",
        "cart_checkout",
    }

    checkout_action = action in {
        "START_CHECKOUT",
        "MODIFY_CHECKOUT",
        "CREATE_ORDER",
    }

    if not (
        checkout_intent
        or checkout_action
    ):
        return False

    
    blocking_fields = {
        "product_name",
        "quantity",
    }

    return bool(
        blocking_fields.intersection(
            missing_fields
        )
    )


# =========================================================
# Helper: Tool Allowed By Graph
# =========================================================


def _tool_is_safe_to_execute(
    state: GraphState,
) -> bool:

    action = _get_action(
        state
    )

    tool_name = _get_tool_name(
        state
    )

    if not tool_name:
        return False

    if action in TOOLLESS_ACTIONS:
        return False

    if _checkout_has_blocking_missing_field(
        state
    ):
        return False

    return True


# =========================================================
# Followup Routing
# =========================================================


def _route_after_followup(
    state: GraphState,
) -> str:
    queue = state.get("multi_intent_queue")
    active_index = state.get("active_intent_index")
    multi_status = _normalize_string(state.get("multi_intent_status"))

    active_task_waiting = (
        isinstance(queue, list)
        and bool(queue)
        and isinstance(active_index, int)
        and 0 <= active_index < len(queue)
        and multi_status == "waiting"
    )

    if _is_awaiting_user_input(state) or active_task_waiting:
        print(
            "[GRAPH ROUTE]"
            " followup -> response"
            " (awaiting user input)"
        )

        return ROUTE_RESPONSE

    return ROUTE_PLANNER


def _route_after_multi_intent(state: GraphState) -> str:
    if state.get("orchestration_directive") == "execute_active_intent":
        return "active"
    return ROUTE_RESPONSE


def _coordinate_after_response(state: GraphState) -> GraphState:
    tool_result = state.get("tool_result")
    tool_data = getattr(tool_result, "data", None)
    tool_success = getattr(tool_result, "success", None)
    result_type = None

    if isinstance(tool_result, dict):
        tool_data = tool_result.get("data")
        tool_success = tool_result.get("success")
        result_type = tool_result.get("type")

    if isinstance(tool_data, dict):
        result_type = result_type or tool_data.get("type")

    metadata = state.get("metadata")
    metadata_type = metadata.get("type") if isinstance(metadata, dict) else None
    waiting = bool(state.get("awaiting_user_input")) or result_type in {
        "address_selection",
        "payment_selection",
    } or metadata_type in {
        "address_selection",
        "payment_selection",
        "product_input",
        "quantity_input",
    }

    if waiting:
        outcome = None
    elif tool_success is False or state.get("transaction_error"):
        outcome = {"status": "failed"}
    else:
        outcome = {"status": "completed"}

    coordinated = multi_intent_node(
        {
            **state,
            "awaiting_user_input": waiting,
            "task_outcome": outcome,
        }
    )
    updates = dict(coordinated)
    updates["awaiting_user_input"] = waiting

    if coordinated.get("orchestration_directive") == "execute_active_intent":
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
            }
        )

    return updates


def _route_after_multi_intent_response(state: GraphState) -> str:
    if state.get("orchestration_directive") == "execute_active_intent":
        return "active"
    return "end"


# =========================================================
# Decision Routing
# =========================================================


def _route_after_decision(
    state: GraphState,
) -> str:

    action = _get_action(
        state
    )

    tool_name = _get_tool_name(
        state
    )

    if (
        action == "SEARCH_PRODUCTS"
        and not tool_name
        and _get_intent(state) == "product_search"
        and _has_value(
            _get_entities(state).get("product_name")
        )
    ):
        tool_name = "search_products"

    decision_route = _normalize_string(
        state.get("decision_route")
    )

    if action in TOOLLESS_ACTIONS:
        print(
            "[GRAPH ROUTE]"
            f" action={action}"
            " -> response"
            " (tool-less action)"
        )

        return ROUTE_RESPONSE

    if decision_route:
        normalized_route = (
            decision_route.lower()
        )

        if normalized_route == ROUTE_TOOL:

            if _tool_is_safe_to_execute(
                state
            ):
                return ROUTE_TOOL

            print(
                "[GRAPH ROUTE]"
                " decision requested tool"
                " but safety guard rejected it"
                " -> response"
            )

            return ROUTE_RESPONSE

        if normalized_route == ROUTE_RESPONSE:
            return ROUTE_RESPONSE

    if tool_name:

        if _tool_is_safe_to_execute(
            state
        ):
            return ROUTE_TOOL

        print(
            "[GRAPH ROUTE]"
            f" tool={tool_name}"
            " rejected by safety guard"
            " -> response"
        )

        return ROUTE_RESPONSE

    return ROUTE_RESPONSE


# =========================================================
# Tool Wrapper
# =========================================================


def _create_tool_wrapper(
    default_db: Any = None,
):
    def _tool_wrapper(
        state: GraphState,
        config: RunnableConfig,
    ) -> GraphState:

        configurable = config.get("configurable", {})
        db = configurable.get("db") if isinstance(configurable, dict) else None

        if db is None:
            db = default_db

        if (
            _get_intent(state) == "product_search"
            and _get_action(state) == "SEARCH_PRODUCTS"
            and not _get_tool_name(state)
            and _has_value(
                _get_entities(state).get("product_name")
            )
        ):
            state = dict(state)
            state["tool_name"] = "search_products"

        if not _tool_is_safe_to_execute(
            state
        ):
            print(
                "[TOOL WRAPPER]"
                " Tool execution blocked by graph safety guard."
            )

            return {
                "tool_name": None,
                "tool_result": None,
                "decision_route": ROUTE_RESPONSE,
            }

        return tool_node(
            state,
            db,
        )

    return _tool_wrapper


# =========================================================
# Build Graph
# =========================================================


def build_graph(
    db: Any = None,
    checkpointer: Any = None,
):

    # =====================================================
    # State Graph
    # =====================================================

    graph = StateGraph(
        GraphState
    )

    # =====================================================
    # Register Nodes
    # =====================================================

    graph.add_node(
        "context",
        context_node,
    )

    graph.add_node(
        "intent",
        intent_node,
    )

    graph.add_node(
        "multi_intent",
        multi_intent_node,
    )

    graph.add_node(
        "multi_intent_after_response",
        _coordinate_after_response,
    )

    graph.add_node(
        "entity",
        entity_node,
    )

    graph.add_node(
        "followup",
        followup_node,
    )

    graph.add_node(
        "planner",
        planner_node,
    )

    graph.add_node(
        "policy",
        policy_node,
    )

    graph.add_node(
        "decision",
        decision_node,
    )

    graph.add_node(
        "tool",
        _create_tool_wrapper(
            db
        ),
    )

    graph.add_node(
        "response",
        response_node,
    )

    # =====================================================
    # START → Context
    # =====================================================

    graph.add_edge(
        START,
        "context",
    )

    # =====================================================
    # Context → Intent
    # =====================================================

    graph.add_edge(
        "context",
        "intent",
    )

    # =====================================================
    # Intent → Entity
    # =====================================================

    graph.add_edge(
        "intent",
        "multi_intent",
    )

    graph.add_conditional_edges(
        "multi_intent",
        _route_after_multi_intent,
        {
            "active": "entity",
            ROUTE_RESPONSE: "response",
        },
    )

    # =====================================================
    # Entity → Followup
    # =====================================================

    graph.add_edge(
        "entity",
        "followup",
    )

    # =====================================================
    # Followup → Response OR Planner
    # =====================================================
    
    graph.add_conditional_edges(
        "followup",
        _route_after_followup,
        {
            ROUTE_RESPONSE: "response",
            ROUTE_PLANNER: "planner",
        },
    )

    # =====================================================
    # Planner → Policy
    # =====================================================

    graph.add_edge(
        "planner",
        "policy",
    )

    # =====================================================
    # Policy → Decision
    # =====================================================

    graph.add_edge(
        "policy",
        "decision",
    )

    # =====================================================
    # Decision → Tool OR Response
    # =====================================================

    graph.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            ROUTE_TOOL: "tool",
            ROUTE_RESPONSE: "response",
        },
    )

    # =====================================================
    # Tool → Response
    # =====================================================
    
    graph.add_edge(
        "tool",
        "response",
    )

    # =====================================================
    # Response → coordinator → next task OR END
    # =====================================================

    graph.add_edge(
        "response",
        "multi_intent_after_response",
    )

    graph.add_conditional_edges(
        "multi_intent_after_response",
        _route_after_multi_intent_response,
        {
            "active": "entity",
            "end": END,
        },
    )

    # =====================================================
    # Compile with Durable Checkpointer
    # =====================================================

    if checkpointer is None:
        try:
            from ai_engine.checkpointer.durable_redis_saver import get_durable_checkpointer
            checkpointer = get_durable_checkpointer()
        except Exception:
            checkpointer = None

    if checkpointer:
        return graph.compile(checkpointer=checkpointer)

    return graph.compile()

app = build_graph()


# =========================================================
# Public API
# =========================================================

__all__ = [
    "app",
    "build_graph",
]