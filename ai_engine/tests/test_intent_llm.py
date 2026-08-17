# ai_engine/tests/test_intent_llm.py
#
# Purpose:
# Test LLM-powered BuyQK intent classification.


from ai_engine.nodes.intent_node import (
    classify_intent,
)


def main():

    print()
    print("=" * 60)
    print(
        "BUYQK LLM INTENT TEST"
    )
    print("=" * 60)

    test_cases = [
        (
            "Find Amul milk",
            "product_search",
        ),
        (
            "I want to buy 2 packets of milk",
            "order_create",
        ),
        (
            "Where is my order 123?",
            "order_tracking",
        ),
        (
            "Cancel my order 123",
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

    passed = 0

    for message, expected in test_cases:

        actual = classify_intent(
            message
        )

        print()
        print(
            f"Message: {message}"
        )

        print(
            f"Expected: {expected}"
        )

        print(
            f"Actual:   {actual}"
        )

        if actual != expected:

            raise AssertionError(
                f"Intent mismatch for: "
                f"'{message}'"
            )

        print(
            "✓ Passed"
        )

        passed += 1

    print()
    print("=" * 60)
    print(
        "✅ LLM INTENT TEST PASSED"
    )
    print("=" * 60)

    print()
    print(
        f"Passed: "
        f"{passed}/{len(test_cases)}"
    )


if __name__ == "__main__":
    main()