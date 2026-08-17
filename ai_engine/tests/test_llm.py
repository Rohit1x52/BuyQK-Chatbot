# Purpose:
# Verify that the BuyQK LLM client can connect to Groq
# and generate a response.


from ai_engine.llm.client import (
    get_llm,
    get_llm_config,
)


def main():

    print()
    print("=" * 60)
    print(
        "BUYQK MVP LLM TEST"
    )
    print("=" * 60)

    # -----------------------------------------------------
    # Configuration
    # -----------------------------------------------------

    config = get_llm_config()

    print()
    print("LLM configuration:")
    print(
        f"  Provider: {config['provider']}"
    )
    print(
        f"  Model: {config['model']}"
    )
    print(
        f"  Temperature: {config['temperature']}"
    )
    print(
        f"  Max tokens: {config['max_tokens']}"
    )

    # -----------------------------------------------------
    # Get LLM
    # -----------------------------------------------------

    llm = get_llm()

    print()
    print(
        "✓ LLM client initialized"
    )

    # -----------------------------------------------------
    # Test request
    # -----------------------------------------------------

    response = llm.invoke(
        "You are BuyQK AI. "
        "Reply with exactly: "
        "BuyQK LLM connection successful."
    )

    # -----------------------------------------------------
    # Extract response
    # -----------------------------------------------------

    content = response.content

    print()
    print(
        "LLM response:"
    )

    print(
        content
    )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if not content:

        raise RuntimeError(
            "LLM returned an empty response."
        )

    print()
    print(
        "✓ LLM response received"
    )

    print()
    print("=" * 60)
    print(
        "✅ LLM TEST PASSED"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()