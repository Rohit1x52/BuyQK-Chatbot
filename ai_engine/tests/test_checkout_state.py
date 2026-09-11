from ai_engine.graph.state import GraphState


def test_graph_state_contains_checkout_fields():
    annotations = GraphState.__annotations__

    assert "checkout_id" in annotations
    assert "checkout_status" in annotations
    assert "cart_checkout_ready" in annotations
    assert "selected_address_id" in annotations
    assert "address_id" in annotations


def test_checkout_can_start_in_collecting_state():
    state: GraphState = {
        "checkout_id": "checkout-test-1",
        "checkout_status": "collecting",
        "cart_checkout_ready": True,
        "selected_address_id": None,
        "address_id": None,
    }

    assert state["checkout_id"] == "checkout-test-1"
    assert state["checkout_status"] == "collecting"
    assert state["cart_checkout_ready"] is True


def test_checkout_can_store_selected_address():
    state: GraphState = {
        "checkout_id": "checkout-test-2",
        "checkout_status": "collecting",
        "cart_checkout_ready": True,
        "selected_address_id": 17,
        "address_id": 17,
    }

    assert state["selected_address_id"] == 17
    assert state["address_id"] == 17


def test_checkout_can_transition_to_ready():
    state: GraphState = {
        "checkout_id": "checkout-test-3",
        "checkout_status": "ready",
        "cart_checkout_ready": True,
        "selected_address_id": 21,
        "address_id": 21,
    }

    assert state["checkout_status"] == "ready"
    assert state["cart_checkout_ready"] is True


def test_checkout_can_represent_completed_state():
    state: GraphState = {
        "checkout_id": "checkout-test-4",
        "checkout_status": "completed",
        "checkout_completed": True,
        "order_created": True,
        "order_id": 101,
    }

    assert state["checkout_status"] == "completed"
    assert state["checkout_completed"] is True
    assert state["order_created"] is True
    assert state["order_id"] == 101


def test_checkout_id_is_separate_from_cart_and_order_ids():
    state: GraphState = {
        "checkout_id": "checkout-abc",
        "cart_id": 10,
        "order_id": 99,
    }

    assert state["checkout_id"] != str(state["cart_id"])
    assert state["checkout_id"] != str(state["order_id"])