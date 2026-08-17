# Purpose:
# Test LLM-powered BuyQK response generation.


from ai_engine.nodes.response_node import (
    generate_response,
)


def run_test(
    name: str,
    state: dict,
    required_text: str | None = None,
):
    """
    Run one response-generation test.
    """

    print()
    print("-" * 60)
    print(
        f"TEST: {name}"
    )
    print("-" * 60)

    response = generate_response(
        state
    )

    print(
        f"Response: {response}"
    )

    if not response:

        raise AssertionError(
            "Response should not be empty."
        )

    if required_text:

        if required_text.lower() not in response.lower():

            raise AssertionError(
                f"Expected response to contain: "
                f"'{required_text}'"
            )

    print(
        "✓ Passed"
    )


def main():

    print()
    print("=" * 60)
    print(
        "BUYQK LLM RESPONSE TEST"
    )
    print("=" * 60)

    # =====================================================
    # TEST 1 — General
    # =====================================================

    run_test(
        "General Conversation",
        {
            "message": "Hello",
            "intent": "general",
            "entities": {},
            "missing_fields": [],
            "tool_name": None,
            "tool_result": None,
        },
    )

    # =====================================================
    # TEST 2 — Missing Quantity
    # =====================================================

    run_test(
        "Missing Quantity",
        {
            "message": "I want Amul milk",
            "intent": "order_create",
            "entities": {
                "product_name": "Amul milk",
            },
            "missing_fields": [
                "quantity",
            ],
            "tool_name": None,
            "tool_result": None,
        },
        required_text="how many",
    )

    # =====================================================
    # TEST 3 — Product Result
    # =====================================================

    run_test(
        "Product Search Result",
        {
            "message": "Find Amul milk",
            "intent": "product_search",
            "entities": {
                "product_name": "Amul milk",
            },
            "missing_fields": [],
            "tool_name": "search_products",
            "tool_result": {
                "success": True,
                "products": [
                    {
                        "name": "Amul Milk",
                        "price": 65,
                    }
                ],
            },
        },
        required_text="Amul Milk",
    )

    # =====================================================
    # TEST 4 — Order Tracking
    # =====================================================

    run_test(
        "Order Tracking",
        {
            "message": "Where is order 123?",
            "intent": "order_tracking",
            "entities": {
                "order_id": 123,
            },
            "missing_fields": [],
            "tool_name": "track_order",
            "tool_result": {
                "success": True,
                "order_id": 123,
                "status": "shipped",
            },
        },
        required_text="123",
    )

    # =====================================================
    # TEST 5 — Backend Failure
    # =====================================================

    run_test(
        "Backend Failure",
        {
            "message": "Find unavailable product",
            "intent": "product_search",
            "entities": {
                "product_name": "Unavailable Product",
            },
            "missing_fields": [],
            "tool_name": "search_products",
            "tool_result": {
                "success": False,
                "message": "Product is currently unavailable.",
            },
        },
        required_text="unavailable",
    )

    # =====================================================
    # Success
    # =====================================================

    print()
    print("=" * 60)
    print(
        "✅ LLM RESPONSE TEST PASSED"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()