# =========================================================
# BuyQK AI - Graph Builder
# =========================================================
#
# Purpose:
# Build the BuyQK LangGraph workflow.
#
# Workflow:
#
# START
#   ↓
# intent
#   ↓
# entity
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
# IMPORTANT:
#
# The graph itself does NOT decide:
#
#   - what the user wants
#   - whether checkout is active
#   - whether an order should be created
#   - which backend operation is required
#
# Those decisions belong to the AI/nodes.
#
# decision_node produces:
#
#     tool_name
#
# If tool_name is present:
#
#     decision → tool → response
#
# If tool_name is None:
#
#     decision → response
#
# This prevents general messages such as:
#
#     "Hi"
#     "Thank you"
#     "Okay"
#
# from accidentally executing backend tools.
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

from ai_engine.nodes.intent_node import (
    intent_node,
)

from ai_engine.nodes.entity_node import (
    entity_node,
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
# Tool Routing
# =========================================================

def _route_after_decision(
    state: GraphState,
) -> str:
    """
    Route the workflow after decision_node.

    The decision node is authoritative for deciding whether
    a backend tool must execute.

    Returns:

        "tool"
            when a valid tool has been selected.

        "response"
            when no backend operation is required.

    The graph does not infer intent or reconstruct checkout
    state here.
    """

    tool_name = state.get("tool_name")

    if isinstance(tool_name, str) and tool_name.strip():
        return "tool"

    return "response"


# =========================================================
# Build Graph
# =========================================================

def build_graph(
    db: Any = None,
):
    """
    Build and compile the BuyQK LangGraph workflow.

    Parameters:
        db:
            Optional database session.

            The preferred source of the database session is
            the GraphState itself. This argument exists for
            compatibility with callers that provide a default
            database session while constructing the graph.

    Returns:
        Compiled LangGraph application.
    """

    graph = StateGraph(
        GraphState
    )

    # =====================================================
    # Register Nodes
    # =====================================================

    graph.add_node(
        "intent",
        intent_node,
    )

    graph.add_node(
        "entity",
        entity_node,
    )

    graph.add_node(
        "decision",
        decision_node,
    )

    # =====================================================
    # Tool Wrapper
    # =====================================================
    #
    # tool_node requires the database session explicitly.
    #
    # GraphState is the authoritative runtime state, so the
    # wrapper first attempts to read db from state.
    #
    # The optional build_graph(db=...) value is only a
    # compatibility fallback.
    #
    # =====================================================

    def _tool_wrapper(
        state: GraphState,
    ):
        db_from_state = state.get("db")

        if db_from_state is None:
            db_from_state = db

        return tool_node(
            state,
            db_from_state,
        )

    graph.add_node(
        "tool",
        _tool_wrapper,
    )

    graph.add_node(
        "response",
        response_node,
    )

    # =====================================================
    # Workflow
    # =====================================================

    # START → Intent
    graph.add_edge(
        START,
        "intent",
    )

    # Intent → Entity
    graph.add_edge(
        "intent",
        "entity",
    )

    # Entity → Decision
    graph.add_edge(
        "entity",
        "decision",
    )

    # =====================================================
    # Decision → Tool OR Response
    # =====================================================
    #
    # IMPORTANT:
    #
    # Do NOT use:
    #
    #     decision → tool
    #
    # unconditionally.
    #
    # decision_node is responsible for determining whether
    # a backend operation is actually required.
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
    # The tool node updates GraphState with authoritative
    # backend information such as:
    #
    #   checkout_id
    #   checkout_status
    #   order_created
    #   order_id
    #   bill
    #
    # response_node then interprets that state for the user.
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

app = build_graph()