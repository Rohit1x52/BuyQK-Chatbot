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
    "search_services",
    "check_availability",
    "get_available_professionals",
    "create_booking",
    "get_booking",
    "cancel_booking",
    "process_booking_payment",
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
    """Return item records so checkout validation can inspect every line."""
    entities = _get_entities(state)
    for candidate in (state.get("order_items"), entities.get("items")):
        if isinstance(candidate, list) and candidate:
            return [item for item in candidate if isinstance(item, dict)]

    product_name = entities.get("product_name")
    quantity = entities.get("quantity")
    if _has_value(product_name) or quantity is not None:
        return [{"product_name": product_name, "quantity": quantity}]
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

    if order_items:
        for item in order_items:
            product_id = item.get("product_id")
            try:
                valid_product_id = int(product_id) > 0
            except (TypeError, ValueError):
                valid_product_id = False
            if not valid_product_id and not _has_value(item.get("product_name")):
                if "product_name" not in missing:
                    missing.append("product_name")
            if not _quantity_is_valid(item.get("quantity")) and "quantity" not in missing:
                missing.append("quantity")
    else:
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


def _decision_node_for_current_task(state: GraphState) -> GraphState:
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
        "SEARCH_SERVICES": "search_services",
        "CHECK_AVAILABILITY": "check_availability",
        "GET_AVAILABLE_PROFESSIONALS": "get_available_professionals",
        "CREATE_BOOKING": "create_booking",
        "GET_BOOKING": "get_booking",
        "CANCEL_BOOKING": "cancel_booking",
        "PROCESS_BOOKING_PAYMENT": "process_booking_payment",
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


# =========================================================
# Phase 13: Multi-Intent Orchestration Helpers
# =========================================================

def _active_intent_from_state(state: GraphState) -> str | None:
    """Resolve the coordinator-selected task without guessing an intent."""
    candidates = (
        state.get("active_intent"),
        state.get("current_intent"),
        (state.get("multi_intent") or {}).get("active_intent")
        if isinstance(state.get("multi_intent"), dict)
        else None,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _is_multi_intent_state(state: GraphState) -> bool:
    """Detect coordinator metadata; this does not classify user language."""
    if isinstance(state.get("multi_intent"), dict):
        return True
    detected_intents = state.get("detected_intents")
    if isinstance(detected_intents, (list, tuple)) and len(detected_intents) > 1:
        return True

    for key in ("pending_intents", "intent_statuses", "intent_entities"):
        value = state.get(key)
        if isinstance(value, (dict, list, tuple)) and len(value) > 0:
            return True
    return False


def _state_for_active_intent(state: GraphState, active_intent: str) -> GraphState:
    """Create a shallow state view scoped to the coordinator's active task."""
    scoped = dict(state)
    scoped["intent"] = active_intent

    intent_entities = state.get("intent_entities")
    if isinstance(intent_entities, dict):
        bucket = intent_entities.get(active_intent)
        if isinstance(bucket, dict):
            scoped["entities"] = dict(bucket)
        elif active_intent in intent_entities:
            # A malformed bucket must not fall back to another intent's entities.
            scoped["entities"] = {}
    return scoped


def _intent_statuses(state: GraphState) -> dict[str, Any]:
    statuses = state.get("intent_statuses")
    if not isinstance(statuses, dict):
        multi = state.get("multi_intent")
        statuses = multi.get("intent_statuses") if isinstance(multi, dict) else None
    return dict(statuses) if isinstance(statuses, dict) else {}


def _pending_intents(state: GraphState) -> list[str]:
    pending = state.get("pending_intents")
    if not isinstance(pending, list):
        multi = state.get("multi_intent")
        pending = multi.get("pending_intents") if isinstance(multi, dict) else None
    return [item for item in pending if isinstance(item, str) and item.strip()] if isinstance(pending, list) else []


def _orchestrator_directive(
    state: GraphState,
    result: GraphState,
    active_intent: str | None,
) -> dict[str, Any]:
    """
    Describe the next orchestration step without advancing the queue.

    A Decision node runs before tool execution, so only the runner/coordinator
    can mark a task complete and advance to a queued intent after observing the
    tool result.
    """
    decision = result.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    action = _normalize_action(decision.get("action"))
    route = decision.get("route")
    allowed = bool(decision.get("allowed"))
    reason = decision.get("reason")

    if action == "ASK_CLARIFICATION" or reason in {
        "missing_order_reference",
        "missing_product_reference",
        "missing_quantity",
        "checkout_incomplete",
        "new_address_incomplete",
    }:
        directive = "wait_for_input"
    elif route == ROUTE_TOOL and allowed:
        directive = "execute_active_intent"
    elif not allowed:
        policy = state.get("policy_result")
        retryable = isinstance(policy, dict) and bool(policy.get("retryable"))
        directive = "wait_for_input" if retryable else "stop_on_policy_rejection"
    elif action == "END_CONVERSATION":
        directive = "finish_conversation"
    else:
        directive = "continue_current_intent"

    statuses = _intent_statuses(state)
    pending = _pending_intents(state)
    result_meta: dict[str, Any] = {
        "orchestrator_action": directive,
        "active_intent": active_intent,
        "pending_intents": pending,
        "intent_statuses": statuses,
        # Queue advancement is deliberately delegated to the runner after
        # the current task's actual result is known.
        "advance_intent_queue": False,
    }

    if statuses:
        terminal_values = {"completed", "complete", "done", "failed", "skipped", "cancelled"}
        all_terminal = all(
            (isinstance(status, str) and status.strip().casefold() in terminal_values)
            or (isinstance(status, dict) and str(status.get("status", "")).strip().casefold() in terminal_values)
            for status in statuses.values()
        )
        if all_terminal and not pending and directive not in {"wait_for_input", "execute_active_intent"}:
            result_meta["orchestrator_action"] = "finish_multi_intent"
        elif active_intent and pending:
            active_status = statuses.get(active_intent)
            if isinstance(active_status, dict):
                active_status = active_status.get("status")
            if isinstance(active_status, str) and active_status.strip().casefold() in {"completed", "complete", "done"}:
                # This is a signal for the coordinator, not permission to execute
                # the next intent from inside Decision.
                result_meta["orchestrator_action"] = "resume_next_intent"
                result_meta["advance_intent_queue"] = False

    return result_meta


def decision_node(state: GraphState) -> GraphState:
    """
    Phase 13 wrapper around the existing decision logic.

    Multi-intent tasks must have a coordinator-selected active intent and an
    existing policy result. This node never promotes a queued intent directly
    to execution and never advances the queue before the active task's result.
    """
    multi_intent = _is_multi_intent_state(state)
    active_intent = _active_intent_from_state(state)

    if multi_intent and not active_intent:
        result = _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=None,
            tool=None,
            reason="missing_active_intent",
            orchestrator_action="wait_for_coordinator",
            active_intent=None,
            advance_intent_queue=False,
        )
        return result

    scoped_state = _state_for_active_intent(state, active_intent) if active_intent else dict(state)

    policy = scoped_state.get("policy_result")
    if not isinstance(policy, dict):
        policy = scoped_state.get("policy")

    # Legacy direct routing is retained only for single-intent compatibility.
    # In a multi-intent turn, every active task must pass the normal policy gate.
    if multi_intent and not isinstance(policy, dict):
        result = _decision_result(
            route=ROUTE_RESPONSE,
            allowed=False,
            action=None,
            tool=None,
            reason="policy_result_required_for_multi_intent",
            orchestrator_action="stop_on_policy_rejection",
            active_intent=active_intent,
            advance_intent_queue=False,
        )
        return result

    result = _decision_node_for_current_task(scoped_state)

    if multi_intent:
        # Detect explicit provenance conflicts when upstream nodes provide it.
        policy_intent = None
        if isinstance(policy, dict):
            policy_intent = policy.get("active_intent") or policy.get("intent")
        planner_decision = scoped_state.get("planner_decision")
        if policy_intent is None and isinstance(planner_decision, dict):
            policy_intent = planner_decision.get("active_intent") or planner_decision.get("intent")

        if isinstance(policy_intent, str) and policy_intent.strip() and policy_intent.strip() != active_intent:
            result = _decision_result(
                route=ROUTE_RESPONSE,
                allowed=False,
                action=_normalize_action(policy.get("action")) if isinstance(policy, dict) else None,
                tool=None,
                reason="active_intent_policy_mismatch",
                active_intent=active_intent,
                policy_intent=policy_intent.strip(),
                orchestrator_action="stop_on_policy_rejection",
                advance_intent_queue=False,
            )
            return result

    result.update(_orchestrator_directive(scoped_state, result, active_intent))
    return result


__all__ = [
    "decision_node",
    "SUPPORTED_TOOLS",
    "INTENT_TO_TOOL",
    "ROUTE_TOOL",
    "ROUTE_RESPONSE",
]