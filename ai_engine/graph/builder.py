# =========================================================
# BuyQK AI - Graph Builder
# =========================================================
#
# Phase 3 Architecture
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
#   ├──────────────────────┐
#   │                      │
#   │ tool_name            │ no tool
#   ↓                      ↓
# tool                  response
#   ↓                      ↓
# response               END
#   ↓
#  END
#
#
# Phase 3 cart operations use the SAME graph pipeline:
#
# User
#   ↓
# Entity
#   ↓
# Planner
#   ↓
# Policy
#   ↓
# Decision
#   ↓
# Tool
#   ↓
# Cart Service
#   ↓
# Response
#
# The graph does NOT contain business logic for:
#
#   - adding cart items
#   - removing cart items
#   - changing quantities
#   - calculating totals
#   - validating stock
#   - creating orders
#
# Those responsibilities remain in the appropriate service/tool
# layers.
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

    The decision node converts the approved planner/policy
    state into executable routing information.

    The graph itself does not determine which capability
    should execute.

    It only checks whether decision_node produced a valid
    tool_name.

    Returns:
        "tool":
            A backend capability should execute.

        "response":
            No backend capability is required.
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
    Create the Tool Node wrapper.

    Runtime database sessions should come from GraphState.

    default_db exists for backwards compatibility with callers
    that construct the graph using build_graph(db).

    Phase 3 cart operations continue to use the same Tool Node.
    The Tool Node delegates actual cart mutations to
    backend/services/cart_service.py.
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
    Build and compile the BuyQK LangGraph workflow.

    Supports:
        Phase 2:
            - checkout
            - order creation
            - tracking
            - cancellation
            - address
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

    # =====================================================
    # Create State Graph
    # =====================================================

    graph = StateGraph(
        GraphState
    )

    # =====================================================
    # Register Nodes
    # =====================================================
    #
    # Phase 3 does NOT require separate cart graph nodes.
    #
    # Cart behavior travels through:
    #
    #     Entity
    #       ↓
    #     Planner
    #       ↓
    #     Policy
    #       ↓
    #     Decision
    #       ↓
    #     Tool
    #
    # This prevents duplicated routing logic.
    #
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
    # Entity → Planner
    # =====================================================
    #
    # Entity Node may now produce Phase 3 information such as:
    #
    #     intent = "cart"
    #
    #     cart_action = "add_item"
    #
    #     product_name = "Maggi"
    #
    #     quantity = 2
    #
    # or:
    #
    #     cart_action = "clear_cart"
    #
    # The graph does not interpret these values.
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
    # Planner proposes a capability.
    #
    # Examples:
    #
    #     add_to_cart
    #     remove_from_cart
    #     update_cart_item
    #     clear_cart
    #     show_cart
    #     checkout_cart
    #
    # The planner does NOT execute them.
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
    # Policy determines whether the proposed capability is
    # allowed.
    #
    # Decision then converts the approved state into the
    # executable routing state.
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
    # The graph only performs structural routing.
    #
    # If decision_node produces:
    #
    #     tool_name = "add_to_cart"
    #
    # the graph routes to Tool Node.
    #
    # If decision_node produces no tool_name:
    #
    #     Response Node
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
    # Tool Node executes the approved capability.
    #
    # Phase 3 examples:
    #
    #     add_to_cart
    #          ↓
    #     cart_service.add_item()
    #
    #     remove_from_cart
    #          ↓
    #     cart_service.remove_item()
    #
    #     update_cart_item
    #          ↓
    #     cart_service.update_quantity()
    #
    #     clear_cart
    #          ↓
    #     cart_service.clear_cart()
    #
    #     show_cart
    #          ↓
    #     cart_service.get_cart()
    #
    #     checkout_cart
    #          ↓
    #     cart validation / checkout preparation
    #
    # Tool results remain authoritative.
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
# Runtime callers should inject the SQLAlchemy session into
# GraphState:
#
#     state["db"] = db
#
# This preserves request-level database ownership.
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