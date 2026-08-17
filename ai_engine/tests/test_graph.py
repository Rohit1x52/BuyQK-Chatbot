# Purpose:
# Tests the BuyQK MVP LangGraph AI engine independently
# from FastAPI.
#
# Tests:
# 1. Intent classification
# 2. Entity extraction
# 3. Decision routing
# 4. Missing-information handling
# 5. Response generation
# 6. Full graph execution for non-tool flows
# 7. Tool selection for supported intents
#
# Run from the project root:
#
#     python -m ai_engine.tests.test_graph
#
# Or with pytest:
#
#     pytest ai_engine/tests/test_graph.py -v


from ai_engine.graph.state import GraphState

from ai_engine.nodes.intent_node import (
    intent_node,
    classify_intent,
)

from ai_engine.nodes.entity_node import (
    entity_node,
)

from ai_engine.nodes.decision_node import (
    decision_node,
)

from ai_engine.nodes.response_node import (
    response_node,
)

from ai_engine.nodes.decision_node import (
    SUPPORTED_TOOLS,
)

from ai_engine.graph.runner import (
    run_chat,
)


# =========================================================
# Test Helpers
# =========================================================

def print_test(
    test_number: int,
    name: str,
):
    """
    Print a formatted test heading.
    """

    print()
    print("=" * 60)
    print(
        f"TEST {test_number}: {name}"
    )
    print("=" * 60)


def assert_equal(
    actual,
    expected,
    message: str,
):
    """
    Simple assertion helper with a readable error.
    """

    if actual != expected:

        raise AssertionError(
            f"{message}\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )


def assert_true(
    condition: bool,
    message: str,
):
    """
    Simple boolean assertion helper.
    """

    if not condition:

        raise AssertionError(
            message
        )


# =========================================================
# TEST 1
# Intent Classification
# =========================================================

def test_intent_classification():

    print_test(
        1,
        "Intent Classification",
    )

    test_cases = [
        (
            "Find Amul milk",
            "product_search",
        ),
        (
            "I want to buy milk",
            "order_create",
        ),
        (
            "Where is my order 123?",
            "order_tracking",
        ),
        (
            "Cancel order 123",
            "order_cancel",
        ),
        (
            "My payment failed",
            "customer_support",
        ),
        (
            "Hello",
            "general",
        ),
    ]

    for message, expected in test_cases:

        actual = classify_intent(
            message
        )

        assert_equal(
            actual,
            expected,
            f"Intent failed for: '{message}'",
        )

        print(
            f"✓ '{message}' → {actual}"
        )


# =========================================================
# TEST 2
# Entity Extraction
# =========================================================

def test_entity_extraction():

    print_test(
        2,
        "Entity Extraction",
    )

    # -----------------------------------------------------
    # Product + quantity
    # -----------------------------------------------------

    state: GraphState = {
        "message": "I want 2 Amul milk",
        "intent": "order_create",
    }

    result = entity_node(
        state
    )

    entities = result.get(
        "entities",
        {},
    )

    assert_equal(
        entities.get("quantity"),
        2,
        "Quantity extraction failed.",
    )

    assert_equal(
        entities.get("product_name"),
        "Amul milk",
        "Product-name extraction failed.",
    )

    print(
        f"✓ Product: {entities.get('product_name')}"
    )

    print(
        f"✓ Quantity: {entities.get('quantity')}"
    )

    # -----------------------------------------------------
    # Order ID
    # -----------------------------------------------------

    state = {
        "message": "Where is order 123?",
        "intent": "order_tracking",
    }

    result = entity_node(
        state
    )

    entities = result.get(
        "entities",
        {},
    )

    assert_equal(
        entities.get("order_id"),
        123,
        "Order ID extraction failed.",
    )

    print(
        f"✓ Order ID: {entities.get('order_id')}"
    )


# =========================================================
# TEST 3
# Missing Information
# =========================================================

def test_missing_information():

    print_test(
        3,
        "Missing Information Detection",
    )

    state: GraphState = {
        "message": "I want Amul milk",
        "intent": "order_create",
    }

    result = entity_node(
        state
    )

    missing_fields = result.get(
        "missing_fields",
        [],
    )

    assert_true(
        "quantity" in missing_fields,
        "Quantity should be detected as missing.",
    )

    print(
        f"✓ Missing fields: {missing_fields}"
    )


# =========================================================
# TEST 4
# Decision Routing
# =========================================================

def test_decision_routing():

    print_test(
        4,
        "Decision Routing",
    )

    # -----------------------------------------------------
    # Product search
    # -----------------------------------------------------

    state: GraphState = {
        "intent": "product_search",
        "entities": {
            "product_name": "Amul milk",
        },
        "missing_fields": [],
    }

    result = decision_node(
        state
    )

    assert_equal(
        result.get("tool_name"),
        "search_products",
        "Product search routing failed.",
    )

    print(
        "✓ product_search → search_products"
    )

    # -----------------------------------------------------
    # Order tracking
    # -----------------------------------------------------

    state = {
        "intent": "order_tracking",
        "entities": {
            "order_id": 123,
        },
        "missing_fields": [],
    }

    result = decision_node(
        state
    )

    assert_equal(
        result.get("tool_name"),
        "track_order",
        "Order tracking routing failed.",
    )

    print(
        "✓ order_tracking → track_order"
    )

    # -----------------------------------------------------
    # Order cancellation
    # -----------------------------------------------------

    state = {
        "intent": "order_cancel",
        "entities": {
            "order_id": 123,
        },
        "missing_fields": [],
    }

    result = decision_node(
        state
    )

    assert_equal(
        result.get("tool_name"),
        "cancel_order",
        "Order cancellation routing failed.",
    )

    print(
        "✓ order_cancel → cancel_order"
    )

    # -----------------------------------------------------
    # Missing quantity
    # -----------------------------------------------------

    state = {
        "intent": "order_create",
        "entities": {
            "product_name": "Amul milk",
        },
        "missing_fields": [
            "quantity",
        ],
    }

    result = decision_node(
        state
    )

    assert_equal(
        result.get("tool_name"),
        None,
        "Graph should not execute a tool when "
        "required information is missing.",
    )

    print(
        "✓ Missing quantity → no tool"
    )


# =========================================================
# TEST 5
# Response Node
# =========================================================

def test_response_node():

    print_test(
        5,
        "Response Generation",
    )

    # -----------------------------------------------------
    # Missing quantity
    # -----------------------------------------------------

    state: GraphState = {
        "intent": "order_create",
        "missing_fields": [
            "quantity",
        ],
        "tool_name": None,
    }

    result = response_node(
        state
    )

    response = result.get(
        "response",
        "",
    )

    assert_true(
        "how many" in response.lower(),
        "Missing-quantity response is incorrect.",
    )

    print(
        f"✓ Missing quantity → {response}"
    )

    # -----------------------------------------------------
    # General greeting
    # -----------------------------------------------------

    state = {
        "message": "Hello",
        "intent": "general",
        "missing_fields": [],
        "tool_name": None,
    }

    result = response_node(
        state
    )

    response = result.get(
        "response",
        "",
    )

    assert_true(
        len(response) > 0,
        "General response should not be empty.",
    )

    print(
        f"✓ General response → {response}"
    )


# =========================================================
# TEST 6
# Tool Selection Coverage
# =========================================================

def test_supported_tool_mapping():

    print_test(
        6,
        "Supported Tool Mapping",
    )

    expected_tools = {
        "search_products",
        "create_order",
        "track_order",
        "cancel_order",
        "create_support_ticket",
    }

    for tool in expected_tools:

        assert_true(
            tool in SUPPORTED_TOOLS,
            f"Missing supported tool: {tool}",
        )

        print(
            f"✓ {tool}"
        )


# =========================================================
# TEST 7
# Full Graph — General Conversation
# =========================================================

def test_full_graph_general():

    print_test(
        7,
        "Full Graph — General Conversation",
    )

    # -----------------------------------------------------
    # No database operation is required for a general
    # conversation, so we can test the complete graph
    # independently.
    #
    # db=None is safe for this particular path because the
    # tool node will never be reached.
    # -----------------------------------------------------

    result = run_chat(
        message="Hello",
        session_id="test-session-001",
        user_id=1,
        db=None,
    )

    assert_equal(
        result.get("intent"),
        "general",
        "Full graph intent failed.",
    )

    assert_true(
        len(
            result.get(
                "response",
                "",
            )
        ) > 0,
        "Full graph response is empty.",
    )

    assert_equal(
        result.get("tool_name"),
        None,
        "General conversation should not select a tool.",
    )

    print(
        f"✓ Intent: {result.get('intent')}"
    )

    print(
        f"✓ Tool: {result.get('tool_name')}"
    )

    print(
        f"✓ Response: {result.get('response')}"
    )


# =========================================================
# TEST 8
# Full Graph — Missing Information
# =========================================================

def test_full_graph_missing_quantity():

    print_test(
        8,
        "Full Graph — Missing Quantity",
    )

    result = run_chat(
        message="I want Amul milk",
        session_id="test-session-002",
        user_id=1,
        db=None,
    )

    assert_equal(
        result.get("intent"),
        "order_create",
        "Order-create intent was not detected.",
    )

    assert_true(
        "quantity"
        in result.get(
            "missing_fields",
            [],
        ),
        "Quantity should be missing.",
    )

    assert_equal(
        result.get("tool_name"),
        None,
        "Order tool should not execute "
        "without quantity.",
    )

    assert_true(
        len(
            result.get(
                "response",
                "",
            )
        ) > 0,
        "Clarification response is empty.",
    )

    print(
        f"✓ Intent: {result.get('intent')}"
    )

    print(
        f"✓ Missing: {result.get('missing_fields')}"
    )

    print(
        f"✓ Tool: {result.get('tool_name')}"
    )

    print(
        f"✓ Response: {result.get('response')}"
    )


# =========================================================
# TEST 9
# GraphState Integrity
# =========================================================

def test_graph_state_integrity():

    print_test(
        9,
        "GraphState Integrity",
    )

    state: GraphState = {
        "message": "Find Amul milk",
        "session_id": "test-session-003",
        "user_id": 1,
    }

    intent_result = intent_node(
        state
    )

    state.update(
        intent_result
    )

    entity_result = entity_node(
        state
    )

    state.update(
        entity_result
    )

    decision_result = decision_node(
        state
    )

    state.update(
        decision_result
    )

    assert_equal(
        state.get("intent"),
        "product_search",
        "State intent is incorrect.",
    )

    assert_equal(
        state.get(
            "entities",
            {},
        ).get("product_name"),
        "Amul milk",
        "State product entity is incorrect.",
    )

    assert_equal(
        state.get("tool_name"),
        "search_products",
        "State tool name is incorrect.",
    )

    print(
        "✓ message preserved"
    )

    print(
        "✓ intent populated"
    )

    print(
        "✓ entities populated"
    )

    print(
        "✓ tool_name populated"
    )


# =========================================================
# Test Runner
# =========================================================

def main():

    print()
    print("=" * 60)
    print(
        "BUYQK MVP AI ENGINE TEST"
    )
    print("=" * 60)

    tests = [
        test_intent_classification,
        test_entity_extraction,
        test_missing_information,
        test_decision_routing,
        test_response_node,
        test_supported_tool_mapping,
        test_full_graph_general,
        test_full_graph_missing_quantity,
        test_graph_state_integrity,
    ]

    passed = 0

    try:

        for test in tests:

            test()

            passed += 1

        print()
        print("=" * 60)
        print(
            "✅ ALL AI ENGINE TESTS PASSED"
        )
        print("=" * 60)

        print()
        print(
            f"Passed: {passed}/{len(tests)}"
        )

        print()
        print(
            "AI engine status:"
        )

        print(
            "  ✓ Intent classification"
        )

        print(
            "  ✓ Entity extraction"
        )

        print(
            "  ✓ Missing-field detection"
        )

        print(
            "  ✓ Decision routing"
        )

        print(
            "  ✓ Response generation"
        )

        print(
            "  ✓ Tool mapping"
        )

        print(
            "  ✓ Full graph execution"
        )

        print(
            "  ✓ GraphState integrity"
        )

    except Exception as exc:

        print()
        print("=" * 60)
        print(
            "❌ AI ENGINE TEST FAILED"
        )
        print("=" * 60)

        print()
        print(
            f"Error:\n{exc}"
        )

        raise


if __name__ == "__main__":
    main()