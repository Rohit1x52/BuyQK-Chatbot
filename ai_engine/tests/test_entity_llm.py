# Purpose:
# Test LLM-powered entity extraction.


from ai_engine.nodes.entity_node import (
    extract_entities,
)


def main():

    print()
    print("=" * 60)
    print(
        "BUYQK LLM ENTITY TEST"
    )
    print("=" * 60)

    test_cases = [
        (
            "I want 2 Amul milk",
            {
                "product_name": "Amul milk",
                "quantity": 2,
            },
        ),
        (
            "Where is order 123?",
            {
                "order_id": 123,
            },
        ),
        (
            "Deliver it to address 45",
            {
                "address_id": 45,
            },
        ),
        (
            "Find Amul milk",
            {
                "product_name": "Amul milk",
            },
        ),
        (
            "Hello",
            {},
        ),
    ]

    passed = 0

    for message, expected in test_cases:

        result = extract_entities(
            message
        )

        actual = result.model_dump(
            exclude_none=True
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

        for key, expected_value in expected.items():

            if actual.get(key) != expected_value:

                raise AssertionError(
                    f"Entity mismatch for "
                    f"'{message}'\n"
                    f"Field: {key}\n"
                    f"Expected: {expected_value}\n"
                    f"Actual: {actual.get(key)}"
                )

        for key in actual:

            if key not in expected:

                raise AssertionError(
                    f"Unexpected entity "
                    f"'{key}' for '{message}'"
                )

        print(
            "✓ Passed"
        )

        passed += 1

    print()
    print("=" * 60)
    print(
        "✅ LLM ENTITY TEST PASSED"
    )
    print("=" * 60)

    print()
    print(
        f"Passed: "
        f"{passed}/{len(test_cases)}"
    )


if __name__ == "__main__":
    main()