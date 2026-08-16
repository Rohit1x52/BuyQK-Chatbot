# Purpose:
# Build the BuyQK LangGraph workflow.
#
# MVP flow:
#
# START
#   ↓
# intent
#   ↓
# entity
#   ↓
# decision
#   ↓
# tool
#   ↓
# response
#   ↓
# END


from langgraph.graph import (
    StateGraph,
    START,
    END,
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
# Build Graph
# =========================================================

def build_graph(db=None):
    """
    Build and compile the BuyQK LangGraph workflow.

    Returns:
        Compiled LangGraph application.
    """

    graph = StateGraph(
        GraphState
    )

    # -----------------------------------------------------
    # Register nodes
    # -----------------------------------------------------

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

    # Wrap `tool_node` so it reads `db` from the incoming state dict.
    # LangGraph will call the wrapper with a single `state` argument;
    # the wrapper extracts `db` and forwards it to the real function.
    def _tool_wrapper(state):
        db_from_state = state.get("db")
        return tool_node(state, db_from_state)

    graph.add_node(
        "tool",
        _tool_wrapper,
    )

    graph.add_node(
        "response",
        response_node,
    )

    # -----------------------------------------------------
    # Define workflow
    # -----------------------------------------------------

    graph.add_edge(
        START,
        "intent",
    )

    graph.add_edge(
        "intent",
        "entity",
    )

    graph.add_edge(
        "entity",
        "decision",
    )

    graph.add_edge(
        "decision",
        "tool",
    )

    graph.add_edge(
        "tool",
        "response",
    )

    graph.add_edge(
        "response",
        END,
    )

    # -----------------------------------------------------
    # Compile
    # -----------------------------------------------------

    return graph.compile()


# =========================================================
# Default Compiled Graph
# =========================================================

app = build_graph()