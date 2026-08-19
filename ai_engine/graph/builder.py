# =========================================================
# BuyQK AI - Graph Builder
# =========================================================
#
# Phase 2 Architecture
#
# Workflow:
#
# START
#   ↓
# context
#   ↓
# intent
#   ↓
# entity
#   ↓
# planner
#   ↓
# policy
#   ↓
# decision
#   ├───────────────┐
#   │               │
#   │ tool_name     │ no tool
#   ↓               ↓
# tool           response
#   ↓               ↓
# response         END
#   ↓
#  END
#
#
# =========================================================
#
# ARCHITECTURAL RESPONSIBILITIES
#
# Context Node:
#     Loads/normalizes conversation context.
#
# Intent Node:
#     Understands the user's high-level intent.
#
# Entity Node:
#     Extracts/updates entities from the user's message.
#
# Planner Node:
#     Determines the proposed next action/capability.
#
# Policy Node:
#     Validates whether the proposed action is allowed.
#
# Decision Node:
#     Converts the approved plan into executable routing state.
#
# Tool Node:
#     Executes the selected backend capability.
#
# Response Node:
#     Presents the result to the user.
#
#
# =========================================================
#
# IMPORTANT
#
# The graph itself does NOT:
#
#     - interpret user language
#     - infer intent
#     - extract entities
#     - decide what the user wants
#     - decide whether an order should be created
#     - validate payment
#     - validate stock
#     - calculate billing
#     - decide business authorization
#     - invent transaction state
#
# Those responsibilities belong to the appropriate AI,
# policy, tool, and backend layers.
#
#
# =========================================================
#
# TRANSACTIONAL TRUTH
#
# Backend/tool results remain authoritative for:
#
#     - product price
#     - stock
#     - payment validity
#     - address validity
#     - order ID
#     - order status
#     - bill
#     - total
#     - delivery charge
#     - tax
#     - discount
#
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

from ai_engine.nodes.context_node import (
    context_node,
)

from ai_engine.nodes.intent_node import (
    intent_node,
)

from ai_engine.nodes.entity_node import (
    entity_node,
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
# Decision Routing
# =========================================================


def _route_after_decision(
    state: GraphState,
) -> str:
    """
    Route the workflow after decision_node.

    The decision node is responsible for converting the
    approved planning/policy state into executable routing
    information.

    The graph only performs structural routing.

    Returns:

        "tool"
            when a tool has been selected.

        "response"
            when no backend operation is required.
    """

    tool_name = state.get(
        "tool_name"
    )

    if isinstance(
        tool_name,
        str,
    ):

        if tool_name.strip():

            return "tool"

    return "response"


# =========================================================
# Tool Wrapper
# =========================================================


def _create_tool_wrapper(
    default_db: Any = None,
):
    """
    Create the tool-node wrapper.

    The runtime database session should normally come from
    GraphState.

    default_db exists only for backwards compatibility with
    callers that still construct the graph with build_graph(db).
    """

    def _tool_wrapper(
        state: GraphState,
    ):
        db = state.get(
            "db"
        )

        if db is None:

            db = default_db

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
    Build and compile the BuyQK Phase-2 LangGraph workflow.

    Parameters
    ----------
    db:
        Optional compatibility database session.

        Runtime requests should preferably provide the database
        session through GraphState.

    Returns
    -------
    Compiled LangGraph application.
    """

    graph = StateGraph(
        GraphState
    )

    # =====================================================
    # Register Phase-2 Nodes
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
    # Context
    # =====================================================
    #
    # START → Context
    #
    # Context is responsible for loading/normalizing the
    # information required by the AI understanding layer.
    #
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
    # Entity → Planner
    # =====================================================
    #
    # At this point the graph should contain:
    #
    #     context
    #     intent
    #     entities
    #     conversation history
    #
    # The planner uses these inputs to propose the next
    # capability/action.
    #
    # =====================================================

    graph.add_edge(
        "entity",
        "planner",
    )

    # =====================================================
    # Planner → Policy
    # =====================================================
    #
    # Planner proposes.
    #
    # Policy validates.
    #
    # The planner does not directly execute a backend action.
    #
    # =====================================================

    graph.add_edge(
        "planner",
        "policy",
    )

    # =====================================================
    # Policy → Decision
    # =====================================================
    #
    # Decision receives:
    #
    #     - intent
    #     - entities
    #     - planner state
    #     - policy state
    #     - checkout state
    #     - conversation context
    #
    # It converts the approved state into executable routing.
    #
    # =====================================================

    graph.add_edge(
        "policy",
        "decision",
    )

    # =====================================================
    # Decision → Tool OR Response
    # =====================================================
    #
    # The graph does not decide which tool to use.
    #
    # It only checks the routing value produced by
    # decision_node.
    #
    # =====================================================

    graph.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            "tool": "tool",
            "response": "response",
        },
    )

    # =====================================================
    # Tool → Response
    # =====================================================
    #
    # Tool execution produces authoritative backend state.
    #
    # Examples:
    #
    #     checkout_id
    #     checkout_status
    #     order_created
    #     order_id
    #     bill
    #     tool_result
    #
    # Response then presents that result.
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
# Runtime callers should inject db into GraphState.
#
# =========================================================

app = build_graph()