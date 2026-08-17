# =========================================================
# BuyQK AI - Decision Node
# =========================================================
#
# Purpose:
# Determine the next action in the BuyQK LangGraph workflow.
#
# Responsibilities:
# - Consume the AI's current-turn intent
# - Validate transactional state deterministically
# - Check required checkout information
# - Enforce checkout order
# - Select backend tools
# - Prevent stale checkout entities from creating new orders
#
# IMPORTANT:
#
# Natural-language intent is decided by the AI/entity node.
# This node must never infer a new order from stale entities.
#
# Example:
#
#     User: I want to buy Maggi 2-Minute Noodles
#     User: 5
#     User: Use selected address
#     User: COD
#
# The final turn MUST become:
#
#     intent    = order_create
#     tool_name = create_order
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Supported Tools
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

INTENT_TO_TOOL = {
    "product_search": "search_products",
    "order_create": "create_order",
    "order_tracking": "track_order",
    "order_cancel": "cancel_order",
    "customer_support": "create_support_ticket",
}


# =========================================================
# Checkout Fields
# =========================================================
#
# IMPORTANT:
# This order must never change.
#
# product
#     ↓
# quantity
#     ↓
# address
#     ↓
# payment
#
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
    Return True when a value is actually present.

    None       -> False
    ""         -> False
    "   "      -> False
    0          -> True
    5          -> True
    "cod"      -> True
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


# =========================================================
# Read Entities
# =========================================================

def _get_entities(
    state: GraphState,
) -> dict[str, Any]:
    """
    Always work with a copied entity dictionary.

    This prevents accidental mutation of GraphState.
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
# Resolve Address
# =========================================================

def _get_selected_address_id(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Address priority:

        1. selected_address_id
        2. entities.address_id

    Frontend-selected address is authoritative.
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
# Resolve Payment
# =========================================================

def _get_payment_method(
    state: GraphState,
    entities: dict[str, Any],
) -> Any:
    """
    Payment priority:

        1. state["payment_method"]
        2. entities["payment_method"]
        3. state["payment_state"]

    This supports all versions of the current checkout flow.
    """

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

    payment_state = state.get(
        "payment_state"
    )

    if _has_value(
        payment_state
    ):
        return payment_state

    return None


# =========================================================
# Calculate Checkout Missing Fields
# =========================================================

def _calculate_checkout_missing_fields(
    state: GraphState,
) -> list[str]:
    """
    Calculate checkout requirements from the actual state.

    DO NOT trust state["missing_fields"] here because it can
    be stale after a user selection.

    Required order:

        product_name
        quantity
        address_selection
        payment_method
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

    if not _has_value(
        product_name
    ):
        missing.append(
            "product_name"
        )

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    quantity = entities.get(
        "quantity"
    )

    # Quantity must be a positive integer.
    # Do not allow 0, negative values, floats, or arbitrary
    # strings to make checkout appear complete.
    quantity_is_valid = False

    if isinstance(
        quantity,
        int,
    ) and not isinstance(
        quantity,
        bool,
    ):
        quantity_is_valid = (
            quantity > 0
        )

    elif isinstance(
        quantity,
        str,
    ):
        try:
            parsed_quantity = int(
                quantity.strip()
            )
            quantity_is_valid = (
                parsed_quantity > 0
            )
        except (
            TypeError,
            ValueError,
        ):
            quantity_is_valid = False

    if not quantity_is_valid:
        missing.append(
            "quantity"
        )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    address_id = _get_selected_address_id(
        state,
        entities,
    )

    address_is_valid = False

    try:
        address_is_valid = (
            int(address_id) > 0
        )
    except (
        TypeError,
        ValueError,
    ):
        address_is_valid = False

    if not address_is_valid:
        missing.append(
            "address_selection"
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    payment_method = _get_payment_method(
        state,
        entities,
    )

    if isinstance(
        payment_method,
        str,
    ):
        payment_method = (
            payment_method
            .strip()
            .lower()
        )

    if not _has_value(
        payment_method
    ):
        missing.append(
            "payment_method"
        )

    return missing


# =========================================================
# Get Next Missing Checkout Field
# =========================================================

def _get_next_missing_field(
    missing_fields: list[str],
) -> str | None:
    """
    Enforce checkout order.

        product
        ↓
        quantity
        ↓
        address
        ↓
        payment
    """

    for field in CHECKOUT_FIELDS:

        if field in missing_fields:
            return field

    return None


# =========================================================
# Checkout Complete
# =========================================================

def _checkout_is_complete(
    state: GraphState,
) -> bool:
    """
    Return True ONLY when every required checkout field
    exists.
    """

    missing_fields = (
        _calculate_checkout_missing_fields(
            state
        )
    )

    return len(
        missing_fields
    ) == 0


# =========================================================
# Detect Successful Previous Order
# =========================================================

def _previous_order_was_successful(
    state: GraphState,
) -> bool:
    """
    Detect whether create_order already succeeded.

    This is CRITICAL.

    Without this guard, the retained entities:

        product_name
        quantity
        address_id
        payment_method

    can cause the next user message to create the SAME
    order again.
    """

    # -----------------------------------------------------
    # Explicit tracking confirmation state
    # -----------------------------------------------------

    if state.get(
        "awaiting_order_tracking_confirmation"
    ):
        return True

    # -----------------------------------------------------
    # Order ID already created
    # -----------------------------------------------------

    if _has_value(
        state.get("order_id")
    ):
        tool_result = state.get(
            "tool_result"
        )

        if isinstance(
            tool_result,
            dict,
        ):
            if (
                tool_result.get("type")
                == "order_success"
            ):
                return True

    # -----------------------------------------------------
    # Tool result
    # -----------------------------------------------------

    tool_result = state.get(
        "tool_result"
    )

    if isinstance(
        tool_result,
        dict,
    ):
        if (
            tool_result.get("type")
            == "order_success"
        ):
            return True

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

    metadata = state.get(
        "metadata",
        {},
    ) or {}

    if isinstance(
        metadata,
        dict,
    ):
        if (
            metadata.get("type")
            == "order_success"
        ):
            return True

    return False


# =========================================================
# Detect Active Order Checkout
# =========================================================

def _is_active_order_checkout(
    state: GraphState,
) -> bool:
    """
    Determine whether the CURRENT user turn is an order-creation turn.

    IMPORTANT:
    Natural-language intent is decided by the AI upstream.

    This function must NOT infer order creation merely because old
    product/quantity/address/payment entities still exist.

    Those entities describe known data. They do not describe what
    the user wants to do NOW.

    Therefore:

        current intent = order_create
            -> active checkout

        current intent != order_create
            -> not active checkout

    A previous successful order never changes a new message into
    order_create.
    """

    intent = state.get(
        "intent",
        "general",
    )

    if intent != "order_create":
        return False

    # If a previous order was completed, only the AI's current
    # order_create decision can reopen checkout. The current intent
    # is therefore the authority for this turn.
    return True


# =========================================================
# Current-Turn Transaction Intents
# =========================================================

def _is_tracking_request(
    state: GraphState,
) -> bool:
    """
    Tracking intent is already decided by the AI.
    """
    return state.get(
        "intent",
        "general",
    ) == "order_tracking"


def _is_cancel_request(
    state: GraphState,
) -> bool:
    """
    Cancellation intent is already decided by the AI.
    """
    return state.get(
        "intent",
        "general",
    ) == "order_cancel"


# =========================================================
# Decision Node
# =========================================================

def decision_node(
    state: GraphState,
) -> GraphState:
    """
    Decide the next graph action.

    Priority:

        1. Current AI order intent / active checkout
        2. Current AI tracking intent
        3. Current AI cancellation intent
        4. General conversation
        5. Other AI-selected tool

    =====================================================

    CRITICAL CHECKOUT RULE:

        If checkout is complete:

            tool_name = create_order

        If address is missing:

            tool_name = list_saved_addresses

        If payment is missing:

            tool_name = list_payment_methods

        If product/quantity is missing:

            tool_name = None

    =====================================================
    """

    # =====================================================
    # Read State
    # =====================================================

    intent = state.get(
        "intent",
        "general",
    )

    intent_before = state.get(
        "intent_before"
    )

    intent_after = state.get(
        "intent_after"
    )

    entities = _get_entities(
        state
    )

    # =====================================================
    # Calculate REAL Checkout State
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
        len(
            missing_fields
        ) == 0
    )

    active_checkout = (
        _is_active_order_checkout(
            state
        )
    )

    # =====================================================
    # DEBUG
    # =====================================================
    #
    # Keep this during development.
    #
    # For your current Maggi test you should see:
    #
    # active_checkout = True
    # checkout_complete = True
    # missing_fields = []
    # tool_name = create_order
    #
    # =====================================================

    print(
        "\n"
        "[DECISION NODE]"
        "\n"
        f"  intent_before    = "
        f"{intent_before!r}"
        "\n"
        f"  intent            = "
        f"{intent!r}"
        "\n"
        f"  intent_after      = "
        f"{intent_after!r}"
        "\n"
        f"  new_order         = "
        f"{state.get('new_order')!r}"
        "\n"
        f"  checkout_turn     = "
        f"{state.get('checkout_turn')!r}"
        "\n"
        f"  active_checkout   = "
        f"{active_checkout!r}"
        "\n"
        f"  checkout_complete = "
        f"{checkout_complete!r}"
        "\n"
        f"  missing_fields    = "
        f"{missing_fields!r}"
        "\n"
        f"  next_missing      = "
        f"{next_missing_field!r}"
        "\n"
        f"  product_name      = "
        f"{entities.get('product_name')!r}"
        "\n"
        f"  quantity          = "
        f"{entities.get('quantity')!r}"
        "\n"
        f"  address_id        = "
        f"{_get_selected_address_id(state, entities)!r}"
        "\n"
        f"  payment_method    = "
        f"{_get_payment_method(state, entities)!r}"
        "\n"
        f"  previous_success  = "
        f"{_previous_order_was_successful(state)!r}"
    )

    # =====================================================
    # 1. ACTIVE ORDER CHECKOUT
    # =====================================================

    if active_checkout:

        # -------------------------------------------------
        # Checkout COMPLETE
        # -------------------------------------------------
        #
        # THIS IS THE IMPORTANT FIX.
        #
        # When:
        #
        # product_name = Maggi 2-Minute Noodles
        # quantity     = 5
        # address_id   = 1
        # payment      = cod
        #
        # return:
        #
        #     intent = order_create
        #     tool   = create_order
        #
        # -------------------------------------------------

        if checkout_complete:

            print(
                "[DECISION NODE]"
                " -> COMPLETE CHECKOUT"
                " -> create_order"
            )

            return {
                "intent": "order_create",
                "tool_name": "create_order",
                "missing_fields": [],
                "next_missing_field": None,
            }

        # -------------------------------------------------
        # Checkout INCOMPLETE
        # -------------------------------------------------
        #
        # The response node is responsible for wording/UI,
        # but it must receive the authoritative backend data
        # needed by address/payment selectors.
        #
        # Therefore:
        #
        #   address missing
        #       -> list_saved_addresses
        #
        #   payment missing
        #       -> list_payment_methods
        #
        # Product/quantity are pure conversational inputs and
        # do not need a backend listing tool.
        # -------------------------------------------------

        if next_missing_field == "address_selection":
            tool_name = "list_saved_addresses"

        elif next_missing_field == "payment_method":
            tool_name = "list_payment_methods"

        else:
            tool_name = None

        print(
            "[DECISION NODE]"
            " -> INCOMPLETE CHECKOUT"
            f" -> waiting for {next_missing_field!r}"
            f" -> tool={tool_name!r}"
        )

        return {
            "intent": "order_create",
            "tool_name": tool_name,
            "missing_fields": missing_fields,
            "next_missing_field": (
                next_missing_field
            ),
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
    # 4. GENERAL
    # =====================================================

    if intent == "general":

        print(
            "[DECISION NODE]"
            " -> general conversation"
        )

        return {
            "tool_name": None,
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # 5. NORMAL INTENT → TOOL
    # =====================================================

    tool_name = INTENT_TO_TOOL.get(
        intent
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
        )

        return {
            "tool_name": None,
            "missing_fields": [],
            "next_missing_field": None,
        }

    # =====================================================
    # 6. TOOL SELECTED
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