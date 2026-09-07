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

ROUTE_TOOL = "tool"
ROUTE_RESPONSE = "response"


def _normalize_action(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value.upper().replace("-", "_").replace(" ", "_") if value else None


def _normalize_tool(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value.casefold() if value else None


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
    # Phase 3 cart capabilities.
    "add_to_cart",
    "remove_from_cart",
    "update_cart_item",
    "clear_cart",
    "show_cart",
    "checkout_cart",
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


def _get_order_items(
    state: GraphState,
) -> list[dict[str, Any]]:
    """Return normalized order items from the authoritative state."""
    items = state.get("order_items")
    if isinstance(items, list):
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            quantity = item.get("quantity")
            product_name = item.get("product_name")
            product_id = item.get("product_id")
            if quantity is None:
                continue
            try:
                parsed_quantity = int(quantity)
            except (TypeError, ValueError):
                continue
            if parsed_quantity <= 0:
                continue
            order_item: dict[str, Any] = {"quantity": parsed_quantity}
            if product_id is not None:
                order_item["product_id"] = product_id
            elif _has_value(product_name):
                order_item["product_name"] = str(product_name).strip()
            else:
                continue
            normalized.append(order_item)
        if normalized:
            return normalized

    entities = _get_entities(state)
    raw_items = entities.get("items")
    if isinstance(raw_items, list):
        normalized = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            product_name = item.get("product_name")
            quantity = item.get("quantity")
            if quantity is None:
                continue
            try:
                parsed_quantity = int(quantity)
            except (TypeError, ValueError):
                continue
            if parsed_quantity <= 0:
                continue
            if not _has_value(product_name):
                continue
            normalized.append({
                "product_name": str(product_name).strip(),
                "quantity": parsed_quantity,
            })
        if normalized:
            return normalized

    product_name = entities.get("product_name")
    quantity = entities.get("quantity")

    if _has_value(product_name):
        try:
            parsed_quantity = int(quantity)
        except (TypeError, ValueError):
            parsed_quantity = None
        if parsed_quantity is not None and parsed_quantity > 0:
            return [{"product_name": str(product_name).strip(), "quantity": parsed_quantity}]

    return []


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

    order_items = _get_order_items(state)
    
    if not order_items:
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
    
        if not _has_value(
            product_name
        ):
            missing.append(
                "product_name"
            )
            
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


def _decision_result(*, route: str, allowed: bool, action: str | None,
                     tool: str | None, reason: Any = None,
                     **extra: Any) -> GraphState:
    """Build the stable DecisionNode contract consumed by graph/tests."""
    result: dict[str, Any] = {
        "decision": {
            "route": route,
            "allowed": allowed,
            "action": action,
            "tool": tool,
            "reason": reason,
        },
        "decision_route": route,
        "tool_name": tool,
        "policy_error": (
            None
            if allowed
            else {
                "allowed": False,
                "action": action,
                "reason": reason,
            }
        ),
    }
    result.update(extra)
    return result


def decision_node(state: GraphState) -> GraphState:
    """Route the authoritative Policy result to Tool or Response.

    The Policy node is the source of authorization.  Decision does not
    re-validate business rules and never executes a tool itself.
    """
    policy = state.get("policy_result")

    if not isinstance(policy, dict):
        # Compatibility with callers that pass a legacy policy object.
        policy = state.get("policy")

    if not isinstance(policy, dict):
        # Compatibility for the Phase-1/2 direct DecisionNode contract.
        # The normal graph path should provide policy_result.  For legacy
        # callers/tests, allow only deterministic read-only capabilities
        # when the required entity is already present.  Never infer a
        # transaction or cart mutation here.
        intent = str(state.get("intent") or "").strip().lower()
        entities = state.get("entities") or {}
        if not isinstance(entities, dict):
            entities = {}

        if intent == "product_search" and entities.get("product_name"):
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="SEARCH_PRODUCTS",
                tool="search_products",
                reason="legacy_direct_routing",
            )

        if intent == "order_tracking" and entities.get("order_id") is not None:
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="TRACK_ORDER",
                tool="track_order",
                reason="legacy_direct_routing",
            )

        if intent == "order_cancel" and entities.get("order_id") is not None:
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="CANCEL_ORDER",
                tool="cancel_order",
                reason="legacy_direct_routing",
            )

        print("[DECISION NODE] Missing policy_result")
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=None,
            tool=None,
            reason="missing_policy_result",
        )

    allowed = bool(policy.get("allowed", False))
    action = _normalize_action(policy.get("action"))
    tool = _normalize_tool(policy.get("tool") or policy.get("tool_name"))
    reason = policy.get("reason")

    # ---------------------------------------------------------
    # Checkout address discovery
    #
    # START_CHECKOUT / MODIFY_CHECKOUT is a workflow action. When
    # checkout reaches the address step, load the user's saved
    # addresses first. The frontend can then present BOTH:
    #
    #   1. saved addresses
    #   2. Add new address
    #
    # list_saved_addresses is read-only and authoritative for this UI.
    # ---------------------------------------------------------
    if action in {"START_CHECKOUT", "MODIFY_CHECKOUT"}:
        checkout_missing = _calculate_checkout_missing_fields(state)

        address_action = str(
            _get_entities(state).get("address_action") or ""
        ).strip().lower()

        if (
            "address_selection" in checkout_missing
            and address_action != "add"
        ):
            return _decision_result(
                route=ROUTE_TOOL,
                allowed=True,
                action="LIST_SAVED_ADDRESSES",
                tool="list_saved_addresses",
                reason="load_saved_addresses_for_checkout",
            )

    # ---------------------------------------------------------
    # Checkout payment discovery
    #
    # CREATE_ORDER must never be routed directly to the Tool node
    # when a payment method has not yet been selected.  The payment
    # method list is backend-authoritative and read-only.
    #
    # This check intentionally happens before the generic Policy
    # rejection branch so a structurally incomplete checkout can
    # continue through the payment-selection workflow.
    # ---------------------------------------------------------
    if action == "CREATE_ORDER" and not _has_value(
        _get_payment_method(
            state,
            _get_entities(state),
        )
    ):
        return _decision_result(
            route=ROUTE_TOOL,
            allowed=True,
            action="LIST_PAYMENT_METHODS",
            tool="list_payment_methods",
            reason="load_payment_methods_for_checkout",
        )

    # Conversational actions are never tool-routed, even if a malformed
    # policy payload contains a tool name.
    if action in {
        "ANSWER",
        "ASK_CLARIFICATION",
        "CONFIRM",
        "END_CONVERSATION",
        "START_CHECKOUT",
        "MODIFY_CHECKOUT",
    }:
        if tool is not None:
            return _decision_result(
                route=ROUTE_RESPONSE,
                allowed=False,
                action=action,
                tool=None,
                reason="tool_not_allowed_for_toolless_action",
            )
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=allowed,
            action=action,
            tool=None,
            reason=reason,
        )

    if not allowed:
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=action,
            tool=None,
            reason=reason or "policy_rejected",
        )

    # Canonical action/tool consistency.  Keep this mapping local to
    # routing; it does not interpret the user's language.
    canonical = {
        "CREATE_ORDER": "create_order",
        "TRACK_ORDER": "track_order",
        "CANCEL_ORDER": "cancel_order",
        "SEARCH_PRODUCTS": "search_products",
        "REQUEST_SUPPORT": "create_support_ticket",
        "LIST_PAYMENT_METHODS": "list_payment_methods",
        "LIST_SAVED_ADDRESSES": "list_saved_addresses",
        "ADD_NEW_ADDRESS": "add_new_address",
        "ADD_TO_CART": "add_to_cart",
        "REMOVE_FROM_CART": "remove_from_cart",
        "UPDATE_CART_ITEM": "update_cart_item",
        "CLEAR_CART": "clear_cart",
        "SHOW_CART": "show_cart",
        "CHECKOUT_CART": "checkout_cart",
    }.get(action)

    if canonical is not None:
        # CREATE_ORDER is always routed to the canonical backend
        # capability.  The decision node never substitutes another
        # tool for an authorized order-creation action.
        if action == "CREATE_ORDER":
            tool = "create_order"
        elif tool is None:
            tool = canonical
        elif tool != canonical:
            return _decision_result(
                route=ROUTE_RESPONSE,
                allowed=False,
                action=action,
                tool=None,
                reason=(
                    "cart_action_tool_mismatch"
                    if action in {
                        "ADD_TO_CART", "REMOVE_FROM_CART", "UPDATE_CART_ITEM",
                        "CLEAR_CART", "SHOW_CART", "CHECKOUT_CART",
                    }
                    else "action_tool_mismatch"
                ),
            )

    if tool is None:
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=True,
            action=action,
            tool=None,
            reason=reason,
        )

    # Never route an unsupported capability to the Tool node.
    # Policy remains authoritative for authorization; this is only a
    # structural routing guard against malformed/unknown tool names.
    if tool not in SUPPORTED_TOOLS:
        return _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=action,
            tool=None,
            reason="unsupported_tool",
        )

    return _decision_result(
        route=ROUTE_TOOL,
        allowed=True,
        action=action,
        tool=tool,
        reason=reason,
    )


__all__ = [
    "decision_node",
    "SUPPORTED_TOOLS",
    "INTENT_TO_TOOL",
    "ROUTE_TOOL",
    "ROUTE_RESPONSE",
]