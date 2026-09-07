# =========================================================
# BuyQK AI - Graph Builder
# =========================================================
#
# Phase 3 Architecture
#
# =========================================================
#
# WORKFLOW
#
# START
#   ↓
# context
#   ↓
# intent
#   ↓
# entity
#   ↓
# followup
#   ├───────────────┐
#   │               │
#   │ awaiting      │ ready
#   │ user input    │
#   ↓               ↓
# response        planner
#                   ↓
#                 policy
#                   ↓
#                 decision
#                /        \
#             tool       response
#              ↓
#           response
#              ↓
#             END
#
# =========================================================
#
# IMPORTANT
#
# The Graph Builder owns ONLY orchestration/routing.
#
# It does NOT:
#
#   - resolve products
#   - validate stock
#   - calculate prices
#   - calculate taxes
#   - calculate discounts
#   - calculate delivery charges
#   - modify cart state
#   - create orders
#   - modify backend state
#
# Those responsibilities remain inside:
#
#   Entity Node
#   Planner Node
#   Policy Node
#   Decision Node
#   Tool Node
#   Backend Services
#
# =========================================================


from __future__ import annotations

from typing import Any

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
    """
    Read the action selected by Decision/Policy.
    """

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
    """
    Read the canonical tool name from state.

    This does not execute anything.
    """

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
    """
    Return True when Followup Node explicitly says
    that the workflow is waiting for another user message.
    """

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
    """
    Determine whether checkout is missing a prerequisite
    that must be supplied before backend checkout tools can
    execute.

    Product and quantity are hard prerequisites.

    Address/payment are interactive checkout steps and can
    legitimately trigger their corresponding selection tools.
    """

    intent = _get_intent(
        state
    )

    action = _get_action(
        state
    )

    missing_fields = _get_missing_fields(
        state
    )

    # -----------------------------------------------------
    # Only apply this guard to order checkout flows.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Product and quantity are hard prerequisites.
    #
    # We must NEVER load addresses/payment methods or
    # execute create_order while either is missing.
    # -----------------------------------------------------

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
    """
    Structural safety guard before Tool Node execution.

    The Policy/Decision nodes remain authoritative for business
    authorization.

    This function only prevents obviously invalid graph routing.

    In particular:

        START_CHECKOUT
            +
        missing product/quantity
            =
        NEVER execute a backend tool.
    """

    action = _get_action(
        state
    )

    tool_name = _get_tool_name(
        state
    )

    # -----------------------------------------------------
    # No tool = no tool execution.
    # -----------------------------------------------------

    if not tool_name:
        return False

    # -----------------------------------------------------
    # Conversational actions are never tool-routed.
    # -----------------------------------------------------

    if action in TOOLLESS_ACTIONS:
        return False

    # -----------------------------------------------------
    # Checkout prerequisite guard.
    # -----------------------------------------------------

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
    """
    Route after Followup Node.

    Followup Node owns the question/clarification decision.

    If it says the system is waiting for user input,
    Response Node must present that question.

    Otherwise continue to Planner.
    """

    if _is_awaiting_user_input(
        state
    ):
        print(
            "[GRAPH ROUTE]"
            " followup -> response"
            " (awaiting user input)"
        )

        return ROUTE_RESPONSE

    return ROUTE_PLANNER


# =========================================================
# Decision Routing
# =========================================================


def _route_after_decision(
    state: GraphState,
) -> str:
    """
    Route after Decision Node.

    Decision Node is responsible for producing the authoritative
    decision contract.

    The graph performs structural safety checks before allowing
    Tool Node execution.

    Possible routes:

        tool
        response
    """

    action = _get_action(
        state
    )

    tool_name = _get_tool_name(
        state
    )

    decision_route = _normalize_string(
        state.get("decision_route")
    )

    # -----------------------------------------------------
    # 1. Conversational actions ALWAYS go to Response.
    # -----------------------------------------------------

    if action in TOOLLESS_ACTIONS:
        print(
            "[GRAPH ROUTE]"
            f" action={action}"
            " -> response"
            " (tool-less action)"
        )

        return ROUTE_RESPONSE

    # -----------------------------------------------------
    # 2. Explicit decision route.
    #
    # Only honor "tool" if structural safety passes.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 3. Compatibility fallback.
    #
    # Some older Decision Nodes only populate tool_name.
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 4. No executable tool.
    # -----------------------------------------------------

    return ROUTE_RESPONSE


# =========================================================
# Tool Wrapper
# =========================================================


def _create_tool_wrapper(
    default_db: Any = None,
):
    """
    Create the Tool Node wrapper.

    Runtime DB sessions are preferred from GraphState.

    default_db remains supported for backwards compatibility.
    """

    def _tool_wrapper(
        state: GraphState,
    ) -> GraphState:

        db = state.get(
            "db"
        )

        if db is None:
            db = default_db

        # -------------------------------------------------
        # Defensive guard.
        #
        # This is the final protection before backend execution.
        # -------------------------------------------------

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
):
    """
    Build and compile the BuyQK LangGraph workflow.

    Phase 2:
        - checkout
        - order creation
        - tracking
        - cancellation
        - addresses
        - payment
        - product search
        - conversation actions

    Phase 3:
        - add_to_cart
        - remove_from_cart
        - update_cart_item
        - clear_cart
        - show_cart
        - checkout_cart

    The graph itself contains only orchestration/routing logic.
    """

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
        "entity",
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
    #
    # IMPORTANT FIX:
    #
    # If Followup Node determines that user input is required,
    # Planner MUST NOT run.
    #
    # Example:
    #
    # User:
    #     "Mujhe Amul Full Cream Milk chahiye"
    #
    # Entity:
    #     missing_fields = ["product_name"]
    #
    # Followup:
    #     awaiting_user_input = True
    #
    # Route:
    #
    #     Followup
    #        ↓
    #     Response
    #
    # NOT:
    #
    #     Followup
    #        ↓
    #     Planner
    #        ↓
    #     list_saved_addresses
    #
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
    #
    # CRITICAL:
    #
    # Every tool execution must pass through Response.
    #
    # This guarantees that the graph cannot finish after
    # Tool Node without producing a user-facing response.
    #
    # =====================================================

    graph.add_edge(
        "tool",
        "response",
    )

    # =====================================================
    # Response → END
    # =====================================================

    graph.add_edge(
        "response",
        END,
    )

    # =====================================================
    # Compile
    # =====================================================

    return graph.compile()


# =========================================================
# Default Compiled Graph
# =========================================================
#
# The default graph does not own a database session.
#
# Runtime callers should inject:
#
#     state["db"] = db
#
# =========================================================

app = build_graph()


# =========================================================
# Public API
# =========================================================

__all__ = [
    "app",
    "build_graph",
]