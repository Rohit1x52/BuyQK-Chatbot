# =========================================================
# BuyQK AI - Decision Node
# =========================================================
#
# Purpose:
# Determine the next safe action in the BuyQK LangGraph.
#
# Architecture:
#
#     User
#       ↓
#     Entity / AI Understanding
#       ↓
#     GraphState
#       ↓
#     Decision Node
#       ↓
#     Tool
#       ↓
#     Backend
#
#
# IMPORTANT:
#
# The AI/entity node decides WHAT THE USER MEANS.
#
# This node does NOT perform natural-language understanding.
#
# It only:
#
#   1. Consumes the AI's current-turn intent.
#   2. Validates authoritative transaction state.
#   3. Prevents stale state from triggering transactions.
#   4. Determines whether checkout is ready.
#   5. Selects the appropriate backend operation.
#
#
# Transactional safety:
#
#     checkout_id
#     checkout_status
#     order_created
#     order_id
#
# are treated as transaction-state information.
#
# The decision node NEVER calculates:
#
#     price
#     subtotal
#     tax
#     delivery charge
#     discount
#     total
#
# Billing belongs to the backend/order service.
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Supported Tools
# =========================================================
#
# These are application capabilities, not natural-language
# decisions.
#
# The AI determines the user's intent.
# The graph maps that intent to an available capability.
# =========================================================

SUPPORTED_TOOLS = {
    "search_products",
    "create_order",
    "track_order",
    "cancel_order",
    "create_support_ticket",
    "list_saved_addresses",
    "list_payment_methods",
}


# =========================================================
# Intent → Tool Mapping
# =========================================================
#
# This mapping is workflow configuration.
#
# It does NOT understand language.
#
# The AI/entity node has already determined the intent.
# =========================================================

INTENT_TO_TOOL = {
    "product_search": "search_products",
    "order_tracking": "track_order",
    "order_cancel": "cancel_order",
    "customer_support": "create_support_ticket",
}


# =========================================================
# Checkout Fields
# =========================================================
#
# These represent the application's required checkout
# dependencies.
#
# They are NOT natural-language rules.
#
# The entity node / AI provides the values.
# The decision node only verifies that the required state
# exists before allowing the transaction to proceed.
# =========================================================

CHECKOUT_FIELDS = (
    "product_name",
    "quantity",
    "address_selection",
    "payment_method",
)


# =========================================================
# Utility
# =========================================================


def _has_value(
    value: Any,
) -> bool:
    """
    Return True when a state value is actually present.

    This function does not interpret natural language.
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


# =========================================================
# Entity Access
# =========================================================


def _get_entities(
    state: GraphState,
) -> dict[str, Any]:
    """
    Return a defensive copy of the accumulated entity state.
    """

    entities = state.get(
        "entities",
        {},
    )

    if not isinstance(
        entities,
        dict,
    ):
        return {}

    return dict(
        entities
    )


# =========================================================
# Address Resolution
# =========================================================


def _get_selected_address_id(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Resolve the currently selected address.

    Priority:

        1. Frontend selected_address_id
        2. Accumulated entity address_id

    The frontend selection is authoritative because it contains
    an actual database address identifier.
    """

    selected_address_id = state.get(
        "selected_address_id"
    )

    if _has_value(
        selected_address_id
    ):
        return selected_address_id

    address_id = entities.get(
        "address_id"
    )

    if _has_value(
        address_id
    ):
        return address_id

    return None


# =========================================================
# Payment Resolution
# =========================================================


def _get_payment_method(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Resolve the selected payment method.

    Priority:

        1. selected_payment_method
        2. payment_method
        3. entity payment_method

    This function does not decide what the user means.

    AI/entity understanding has already happened upstream.

    Backend/payment services remain responsible for validating
    whether the selected method is actually available.
    """

    selected_payment_method = state.get(
        "selected_payment_method"
    )

    if _has_value(
        selected_payment_method
    ):
        return selected_payment_method

    payment_method = state.get(
        "payment_method"
    )

    if _has_value(
        payment_method
    ):
        return payment_method

    payment_method = entities.get(
        "payment_method"
    )

    if _has_value(
        payment_method
    ):
        return payment_method

    return None


# =========================================================
# Quantity Validation
# =========================================================


def _quantity_is_valid(
    quantity: Any,
) -> bool:
    """
    Validate that quantity is a positive integer.

    This is structural validation, not language understanding.
    """

    if isinstance(
        quantity,
        bool,
    ):
        return False

    if isinstance(
        quantity,
        int,
    ):
        return quantity > 0

    if isinstance(
        quantity,
        str,
    ):

        try:

            parsed = int(
                quantity.strip()
            )

            return parsed > 0

        except (
            TypeError,
            ValueError,
        ):

            return False

    return False


# =========================================================
# Address Validation
# =========================================================


def _address_is_valid(
    address_id: Any,
) -> bool:
    """
    Validate that an address identifier is usable.
    """

    if not _has_value(
        address_id
    ):
        return False

    try:

        return int(
            address_id
        ) > 0

    except (
        TypeError,
        ValueError,
    ):

        return False


# =========================================================
# Checkout Missing Fields
# =========================================================


def _calculate_checkout_missing_fields(
    state: GraphState,
) -> list[str]:
    """
    Validate the currently accumulated checkout state.

    This function does NOT inspect natural-language messages.

    It only validates state that has already been understood by
    the AI/entity node or supplied by the frontend.
    """

    entities = _get_entities(
        state
    )

    missing: list[str] = []

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    product_name = entities.get(
        "product_name"
    )

    product_id = (
        state.get(
            "product_id"
        )
        or entities.get(
            "product_id"
        )
    )

    #
    # Product name is the user-facing semantic value.
    #
    # Product ID is the authoritative backend identity.
    #
    if not _has_value(
        product_name
    ):

        missing.append(
            "product_name"
        )

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    quantity = (
        state.get(
            "quantity"
        )
        or entities.get(
            "quantity"
        )
    )

    if not _quantity_is_valid(
        quantity
    ):

        missing.append(
            "quantity"
        )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    address_id = (
        _get_selected_address_id(
            state,
            entities,
        )
    )

    if not _address_is_valid(
        address_id
    ):

        missing.append(
            "address_selection"
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    payment_method = (
        _get_payment_method(
            state,
            entities,
        )
    )

    if not _has_value(
        payment_method
    ):

        missing.append(
            "payment_method"
        )

    return missing


# =========================================================
# Next Missing Field
# =========================================================


def _get_next_missing_field(
    missing_fields: list[str],
) -> str | None:
    """
    Return the next unresolved checkout dependency.

    This is workflow sequencing, not natural-language
    interpretation.
    """

    for field in CHECKOUT_FIELDS:

        if field in missing_fields:

            return field

    return None


# =========================================================
# Checkout Completeness
# =========================================================


def _checkout_is_complete(
    state: GraphState,
) -> bool:
    """
    Return True only when all required checkout state exists.
    """

    missing_fields = (
        _calculate_checkout_missing_fields(
            state
        )
    )

    return not missing_fields


# =========================================================
# Transaction Identity
# =========================================================


def _get_checkout_id(
    state: GraphState,
) -> str | None:
    """
    Read the current checkout transaction identifier.

    The checkout ID is generated when a new checkout begins
    and remains stable throughout that checkout.
    """

    checkout_id = state.get(
        "checkout_id"
    )

    if not _has_value(
        checkout_id
    ):
        return None

    return str(
        checkout_id
    ).strip()


# =========================================================
# Order Created
# =========================================================


def _order_has_been_created(
    state: GraphState,
) -> bool:
    """
    Determine whether the current checkout has already
    successfully created an order.

    order_created is the primary transaction-state flag.

    order_id is additional evidence that a backend order
    exists.

    Neither value is inferred from the user's language.
    """

    if bool(
        state.get(
            "order_created",
            False,
        )
    ):
        return True

    order_id = state.get(
        "order_id"
    )

    if _has_value(
        order_id
    ):

        try:

            return int(
                order_id
            ) > 0

        except (
            TypeError,
            ValueError,
        ):

            pass

    return False


# =========================================================
# Completed Checkout
# =========================================================


def _checkout_is_already_completed(
    state: GraphState,
) -> bool:
    """
    Determine whether the current checkout transaction has
    already been completed.

    IMPORTANT:

    This function does NOT interpret the user's current message.

    The AI has already determined the current intent.

    This function only protects the transaction from accidental
    duplicate execution.
    """

    if _order_has_been_created(
        state
    ):
        return True

    checkout_status = state.get(
        "checkout_status"
    )

    if isinstance(
        checkout_status,
        str,
    ):

        normalized = (
            checkout_status
            .strip()
            .casefold()
        )

        #
        # These are transaction lifecycle states, not
        # user-language keywords.
        #
        if normalized in {
            "completed",
            "order_created",
            "success",
        }:

            return True

    return False


# =========================================================
# Active Checkout
# =========================================================


def _is_active_order_checkout(
    state: GraphState,
) -> bool:
    """
    Determine whether the CURRENT graph state represents an
    order-creation turn.

    CRITICAL:

    This function does NOT infer order creation from entities.

    For example:

        product_name = "Maggi"
        quantity = 3
        address_id = 2
        payment_method = "cod"

    does NOT automatically mean:

        create_order

    The AI must have already classified the current message as:

        intent = order_create

    Therefore:

        intent != order_create
            -> not an order-creation turn

        intent == order_create
            -> candidate order-creation turn
    """

    intent = state.get(
        "intent",
        "general",
    )

    return (
        intent
        == "order_create"
    )


# =========================================================
# Previous Transaction Guard
# =========================================================


def _should_block_order_creation(
    state: GraphState,
) -> bool:
    """
    Prevent duplicate order creation.

    This is deliberately deterministic.

    AI is responsible for understanding whether the user wants
    a NEW purchase.

    But once a backend transaction has already succeeded, the
    system must not blindly execute create_order again from
    stale state.

    A genuinely new checkout is represented by the entity node
    creating a new checkout_id and resetting order_created.
    """

    if not _checkout_is_already_completed(
        state
    ):
        return False

    #
    # The entity node resets order_created when it establishes
    # a genuinely new checkout.
    #
    # Therefore if order_created is still true here, this is
    # the same completed transaction and create_order must be
    # blocked.
    #
    return True


# =========================================================
# Tracking
# =========================================================


def _is_tracking_request(
    state: GraphState,
) -> bool:
    """
    Tracking intent is already determined by the AI.
    """

    return (
        state.get(
            "intent",
            "general",
        )
        == "order_tracking"
    )


# =========================================================
# Cancellation
# =========================================================


def _is_cancel_request(
    state: GraphState,
) -> bool:
    """
    Cancellation intent is already determined by the AI.
    """

    return (
        state.get(
            "intent",
            "general",
        )
        == "order_cancel"
    )


# =========================================================
# General Conversation
# =========================================================


def _is_general_request(
    state: GraphState,
) -> bool:
    """
    General intent is already determined by the AI.
    """

    return (
        state.get(
            "intent",
            "general",
        )
        == "general"
    )


# =========================================================
# Decision Node
# =========================================================


def decision_node(
    state: GraphState,
) -> GraphState:
    """
    Determine the next safe graph operation.

    The AI/entity node decides the user's current intent.

    This node validates and routes that decision.

    Routing priority:

        1. order_create
        2. order_tracking
        3. order_cancel
        4. general
        5. other supported AI intent

    =========================================================
    ORDER CREATE
    =========================================================

    order_create
        ↓
    transaction already created?
        ↓
       YES
        ↓
    DO NOT create again

    order_create
        ↓
    checkout incomplete?
        ↓
       YES
        ↓
    request required backend/frontend information

    order_create
        ↓
    checkout complete
        ↓
    create_order

    =========================================================
    """

    # =====================================================
    # Read State
    # =====================================================

    intent = state.get(
        "intent",
        "general",
    )

    entities = _get_entities(
        state
    )

    checkout_id = (
        _get_checkout_id(
            state
        )
    )

    checkout_status = (
        state.get(
            "checkout_status"
        )
    )

    order_created = bool(
        state.get(
            "order_created",
            False,
        )
    )

    order_id = state.get(
        "order_id"
    )

    # =====================================================
    # Calculate Transaction State
    # =====================================================

    missing_fields = (
        _calculate_checkout_missing_fields(
            state
        )
    )

    next_missing_field = (
        _get_next_missing_field(
            missing_fields
        )
    )

    checkout_complete = (
        not missing_fields
    )

    active_checkout = (
        _is_active_order_checkout(
            state
        )
    )

    transaction_completed = (
        _checkout_is_already_completed(
            state
        )
    )

    block_order_creation = (
        _should_block_order_creation(
            state
        )
    )

    # =====================================================
    # Debug
    # =====================================================

    print(
        "\n"
        "====================================================\n"
        "[DECISION NODE]\n"
        "====================================================\n"
        f"  intent            = {intent!r}\n"
        f"  checkout_id      = {checkout_id!r}\n"
        f"  checkout_status  = {checkout_status!r}\n"
        f"  order_created    = {order_created!r}\n"
        f"  order_id         = {order_id!r}\n"
        f"  active_checkout  = {active_checkout!r}\n"
        f"  transaction_done = {transaction_completed!r}\n"
        f"  checkout_complete= {checkout_complete!r}\n"
        f"  missing_fields   = {missing_fields!r}\n"
        f"  next_missing     = {next_missing_field!r}\n"
        f"  product_name     = "
        f"{entities.get('product_name')!r}\n"
        f"  product_id       = "
        f"{state.get('product_id') or entities.get('product_id')!r}\n"
        f"  quantity         = "
        f"{state.get('quantity') or entities.get('quantity')!r}\n"
        f"  address_id       = "
        f"{_get_selected_address_id(state, entities)!r}\n"
        f"  payment_method   = "
        f"{_get_payment_method(state, entities)!r}\n"
        f"  block_create     = "
        f"{block_order_creation!r}\n"
        "====================================================\n"
    )

    # =====================================================
    # 1. ORDER CREATION
    # =====================================================

    if active_checkout:

        # -------------------------------------------------
        # DUPLICATE TRANSACTION PROTECTION
        # -------------------------------------------------
        #
        # This is the most important transaction guard.
        #
        # If create_order already succeeded for this checkout,
        # do not execute it again.
        #
        # No language-specific rule exists here.
        #
        # "Thank you"
        # "Thanks"
        # "Okay"
        # "Dhanyavaad"
        # etc.
        #
        # are NOT hardcoded.
        #
        # The AI determines their intent.
        #
        # This guard simply prevents an already-completed
        # transaction from being executed again.
        # -------------------------------------------------

        if block_order_creation:

            print(
                "[DECISION NODE]"
                " -> BLOCK duplicate order creation"
                f" | checkout_id={checkout_id!r}"
                f" | order_id={order_id!r}"
            )

            return {
                #
                # Do NOT route to create_order.
                #
                # Response node can explain/present the current
                # order state using the authoritative backend
                # result already present in GraphState.
                #
                "tool_name": None,
                "missing_fields": [],
                "next_missing_field": None,
                "checkout_status": (
                    checkout_status
                    or "completed"
                ),
                "order_created": True,
                "order_id": order_id,
            }

        # -------------------------------------------------
        # CHECKOUT COMPLETE
        # -------------------------------------------------
        #
        # Only the AI's current order_create intent AND a
        # complete checkout state allow create_order.
        #
        # No prices or billing values are calculated here.
        # -------------------------------------------------

        if checkout_complete:

            print(
                "[DECISION NODE]"
                " -> COMPLETE CHECKOUT"
                " -> create_order"
                f" | checkout_id={checkout_id!r}"
            )

            return {
                "intent": "order_create",
                "tool_name": "create_order",
                "missing_fields": [],
                "next_missing_field": None,
                "checkout_status": "ready",
            }

        # -------------------------------------------------
        # CHECKOUT INCOMPLETE
        # -------------------------------------------------
        #
        # Only backend-dependent information requires a
        # backend listing tool.
        #
        # Product/quantity are conversational state already
        # understood by the AI.
        # -------------------------------------------------

        if next_missing_field == (
            "address_selection"
        ):

            tool_name = (
                "list_saved_addresses"
            )

        elif next_missing_field == (
            "payment_method"
        ):

            tool_name = (
                "list_payment_methods"
            )

        else:

            tool_name = None

        print(
            "[DECISION NODE]"
            " -> INCOMPLETE CHECKOUT"
            f" -> missing={next_missing_field!r}"
            f" -> tool={tool_name!r}"
        )

        return {
            "intent": "order_create",
            "tool_name": tool_name,
            "missing_fields": missing_fields,
            "next_missing_field": (
                next_missing_field
            ),
            "checkout_status": "collecting",
        }

    # =====================================================
    # 2. TRACKING
    # =====================================================

    if _is_tracking_request(
        state
    ):

        print(
            "[DECISION NODE]"
            " -> track_order"
        )

        return {
            "intent": "order_tracking",
            "tool_name": "track_order",
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # 3. CANCELLATION
    # =====================================================

    if _is_cancel_request(
        state
    ):

        print(
            "[DECISION NODE]"
            " -> cancel_order"
        )

        return {
            "intent": "order_cancel",
            "tool_name": "cancel_order",
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # 4. GENERAL CONVERSATION
    # =====================================================

    if _is_general_request(
        state
    ):

        print(
            "[DECISION NODE]"
            " -> general conversation"
        )

        return {
            "intent": "general",
            "tool_name": None,
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # 5. OTHER AI-DETERMINED INTENT
    # =====================================================
    #
    # We deliberately do not map order_create here.
    #
    # order_create has already been handled above because it
    # requires transaction-state validation.
    # =====================================================

    tool_name = (
        INTENT_TO_TOOL.get(
            intent
        )
    )

    # =====================================================
    # Safety
    # =====================================================

    if (
        tool_name is None
        or tool_name not in SUPPORTED_TOOLS
    ):

        print(
            "[DECISION NODE]"
            " -> no supported tool"
            f" | intent={intent!r}"
        )

        return {
            "tool_name": None,
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # TOOL SELECTED
    # =====================================================

    print(
        "[DECISION NODE]"
        f" -> {tool_name}"
    )

    return {
        "tool_name": tool_name,
        "missing_fields": [],
        "next_missing_field": None,
    }