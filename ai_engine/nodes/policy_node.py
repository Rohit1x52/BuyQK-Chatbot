# =========================================================
# BuyQK AI - Policy / Validator Node
# =========================================================
#
# Purpose:
# Validate the AI Planner's proposed action before allowing
# the Tool Node to execute anything.
#
# Architecture:
#
#   Context
#      ↓
#   Understander
#      ↓
#   Planner
#      ↓
#   Policy / Validator
#      ↓
#   Decision
#      ↓
#   Tool
#      ↓
#   Backend
#
# IMPORTANT:
#
# The Policy Node is NOT another AI decision maker.
#
# The AI Planner proposes:
#
#   action
#   tool
#   arguments
#
# This node verifies whether that proposal is compatible
# with the authoritative application state.
#
# It does NOT:
#
#   - calculate prices
#   - calculate bills
#   - check product stock by itself
#   - create orders
#   - generate order IDs
#   - generate checkout IDs
#   - invent payment methods
#   - invent addresses
#   - mutate carts
#
# Those responsibilities belong to backend services.
#
# =========================================================
# Phase 3 Cart Boundary
# =========================================================
#
# New cart capabilities:
#
#   add_to_cart
#   remove_from_cart
#   update_cart_item
#   clear_cart
#   show_cart
#   checkout_cart
#
# Policy validates:
#
#   Planner proposal
#       ↓
#   capability/tool compatibility
#       ↓
#   required argument presence
#       ↓
#   transaction-state safety
#       ↓
#   ALLOW / DENY
#
# Policy does NOT:
#
#   - verify stock
#   - calculate price
#   - calculate totals
#   - resolve authoritative product IDs
#   - mutate the cart
#   - create an order
#
# Backend remains authoritative.
#
# =========================================================


from __future__ import annotations

from typing import Any

from ai_engine.graph.state import GraphState


# =========================================================
# Supported Tools
# =========================================================

SUPPORTED_TOOLS = {
    # -----------------------------------------------------
    # Phase 2
    # -----------------------------------------------------
    "search_products",
    "create_order",
    "track_order",
    "cancel_order",
    "create_support_ticket",
    "list_saved_addresses",

    # -----------------------------------------------------
    # Phase 3 - Cart
    # -----------------------------------------------------
    "add_to_cart",
    "remove_from_cart",
    "update_cart_item",
    "clear_cart",
    "show_cart",
    "checkout_cart",
}


# =========================================================
# Actions That Do Not Require Backend Tools
# =========================================================

NON_TOOL_ACTIONS = {
    "ANSWER",
    "ASK_CLARIFICATION",
    "CONFIRM",
    "END_CONVERSATION",
}


# =========================================================
# Cart Actions
# =========================================================
#
# The planner may use action names directly as capabilities.
#
# These bindings make sure the planner cannot request:
#
#     action = ADD_TO_CART
#     tool   = clear_cart
#
# and accidentally execute the wrong capability.
#
# =========================================================

CART_ACTION_TO_TOOL = {
    "ADD_TO_CART": "add_to_cart",
    "REMOVE_FROM_CART": "remove_from_cart",
    "UPDATE_CART_ITEM": "update_cart_item",
    "CLEAR_CART": "clear_cart",
    "SHOW_CART": "show_cart",
    "CHECKOUT_CART": "checkout_cart",
}


# =========================================================
# Utility
# =========================================================

def _has_value(
    value: Any,
) -> bool:
    """
    Determine whether a value is meaningfully present.

    Empty strings and None are considered absent.

    Numeric zero remains a present value here.

    Individual validators are responsible for deciding
    whether zero is semantically valid.
    """

    if value is None:
        return False

    if isinstance(
        value,
        str,
    ):
        return bool(
            value.strip()
        )

    return True


def _failure(
    reason: str,
    *,
    action: str | None = None,
    tool: str | None = None,
    retryable: bool = False,
    **extra: Any,
) -> GraphState:
    """
    Build a standardized policy rejection.

    A rejection does not execute a tool.
    """

    result = {
        "allowed": False,
        "action": action,
        "tool": tool,
        "reason": reason,
        "retryable": retryable,
        **extra,
    }

    return {
        "policy_result": result,
        "policy_error": result,
        "tool_name": None,
    }


def _success(
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Build a standardized policy approval.
    """

    result = {
        "allowed": True,
        "action": action,
        "tool": tool,
    }

    return {
        "policy_result": result,
        "policy_error": None,
        "tool_name": tool,
    }


# =========================================================
# Planner Arguments
# =========================================================

def _get_planned_arguments(
    state: GraphState,
) -> dict[str, Any]:
    """
    Return the planner's proposed arguments.

    Supports the canonical planner field:

        planner_decision["arguments"]

    and compatibility aliases:

        planner_decision["tool_arguments"]
        state["planned_arguments"]

    The Policy Node only validates these arguments.

    It does NOT resolve authoritative backend values.
    """

    planner_decision = state.get(
        "planner_decision",
        {},
    )

    if isinstance(
        planner_decision,
        dict,
    ):
        arguments = planner_decision.get(
            "arguments"
        )

        if isinstance(
            arguments,
            dict,
        ):
            return dict(
                arguments
            )

        arguments = planner_decision.get(
            "tool_arguments"
        )

        if isinstance(
            arguments,
            dict,
        ):
            return dict(
                arguments
            )

    planned_arguments = state.get(
        "planned_arguments",
        {},
    )

    if isinstance(
        planned_arguments,
        dict,
    ):
        return dict(
            planned_arguments
        )

    return {}


# =========================================================
# State / Argument Helpers
# =========================================================

def _get_entities(
    state: GraphState,
) -> dict[str, Any]:
    """
    Safely return GraphState entities.
    """

    entities = state.get(
        "entities",
        {},
    )

    if isinstance(
        entities,
        dict,
    ):
        return entities

    return {}


def _get_argument(
    state: GraphState,
    arguments: dict[str, Any],
    key: str,
) -> Any:
    """
    Resolve an argument without inventing it.

    Precedence:

        planner arguments
            ↓
        entity state
            ↓
        GraphState
    """

    if key in arguments:
        return arguments.get(
            key
        )

    entities = _get_entities(
        state
    )

    if key in entities:
        return entities.get(
            key
        )

    return state.get(
        key
    )


def _positive_integer(
    value: Any,
) -> bool:
    """
    Determine whether a value is a positive integer.

    bool is deliberately rejected because:

        bool is int

    in Python.
    """

    if isinstance(
        value,
        bool,
    ):
        return False

    if isinstance(
        value,
        int,
    ):
        return value > 0

    if isinstance(
        value,
        str,
    ):
        try:
            parsed = int(
                value.strip()
            )
        except (
            TypeError,
            ValueError,
        ):
            return False

        return parsed > 0

    return False


# =========================================================
# Completed Transaction Guard
# =========================================================

def _transaction_already_completed(
    state: GraphState,
) -> bool:
    """
    Determine whether this checkout already resulted in a
    successfully created order.

    This is the critical duplicate-order protection.

    Example:

        Order created
            ↓
        user: "Thank you"
            ↓
        planner proposes ANSWER
            ↓
        allowed

    Even if the planner incorrectly proposes CREATE_ORDER,
    the policy layer prevents another transaction.
    """

    order_created = bool(
        state.get(
            "order_created",
            False,
        )
    )

    checkout_completed = bool(
        state.get(
            "checkout_completed",
            False,
        )
    )

    checkout_status = state.get(
        "checkout_status"
    )

    order_id = state.get(
        "order_id"
    )

    # The authoritative order_created flag is sufficient.
    if order_created:
        return True

    # A persisted order ID means an order already exists.
    if _has_value(
        order_id
    ):
        return True

    # A terminal completed checkout should not be recreated.
    if (
        isinstance(
            checkout_status,
            str,
        )
        and checkout_status.strip().lower()
        in {
            "completed",
            "complete",
            "success",
            "successful",
        }
    ):
        return True

    if checkout_completed:
        return True

    return False


# =========================================================
# Checkout Readiness
# =========================================================

def _checkout_has_required_state(
    state: GraphState,
) -> tuple[bool, list[str]]:
    """
    Validate that the current GraphState contains the
    transaction fields required before CREATE_ORDER or
    CHECKOUT_CART.

    This does NOT validate business facts such as:

        product exists
        stock is sufficient
        address belongs to user
        payment is currently available

    Those are backend responsibilities.
    """

    missing: list[str] = []

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    if not _has_value(
        state.get(
            "product_id"
        )
    ):
        missing.append(
            "product_id"
        )

    # -----------------------------------------------------
    # Quantity
    # -----------------------------------------------------

    quantity = state.get(
        "quantity"
    )

    if not _positive_integer(
        quantity
    ):
        missing.append(
            "quantity"
        )

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------

    address_id = state.get(
        "address_id"
    )

    selected_address_id = state.get(
        "selected_address_id"
    )

    if not (
        _has_value(
            address_id
        )
        or _has_value(
            selected_address_id
        )
    ):
        missing.append(
            "address_id"
        )

    # -----------------------------------------------------
    # Payment
    # -----------------------------------------------------

    payment_method = state.get(
        "selected_payment_method"
    )

    if not _has_value(
        payment_method
    ):
        payment_method = state.get(
            "payment_method"
        )

    if not _has_value(
        payment_method
    ):
        payment_method = state.get(
            "selected_payment_method_normalized"
        )

    if not _has_value(
        payment_method
    ):
        missing.append(
            "payment_method"
        )

    return (
        len(missing) == 0,
        missing,
    )


# =========================================================
# Validate Tool
# =========================================================

def _validate_tool(
    tool: Any,
) -> tuple[bool, str | None]:
    """
    Validate that the planner requested a tool supported by
    the application.

    The planner cannot invent arbitrary tool names.
    """

    if tool is None:
        return (
            True,
            None,
        )

    if not isinstance(
        tool,
        str,
    ):
        return (
            False,
            "invalid_tool",
        )

    tool = tool.strip().casefold()

    if not tool:
        return (
            True,
            None,
        )

    if tool not in SUPPORTED_TOOLS:
        return (
            False,
            "unsupported_tool",
        )

    return (
        True,
        tool,
    )


# =========================================================
# Validate CREATE_ORDER
# =========================================================

def _validate_create_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate an AI proposal to create an order.

    Only transaction-state readiness is checked here.

    Product availability, stock, price, payment validity,
    authorization and final billing remain backend
    responsibilities.
    """

    # -----------------------------------------------------
    # Duplicate transaction guard
    # -----------------------------------------------------

    if _transaction_already_completed(
        state
    ):
        return _failure(
            "checkout_already_completed",
            action=action,
            tool=tool,
            retryable=False,
        )

    # -----------------------------------------------------
    # Checkout ID
    # -----------------------------------------------------

    checkout_id = state.get(
        "checkout_id"
    )

    if not _has_value(
        checkout_id
    ):
        return _failure(
            "missing_checkout_id",
            action=action,
            tool=tool,
            retryable=True,
        )

    # -----------------------------------------------------
    # Required checkout state
    # -----------------------------------------------------

    ready, missing = (
        _checkout_has_required_state(
            state
        )
    )

    if not ready:
        return _failure(
            "checkout_incomplete",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=missing,
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate TRACK_ORDER
# =========================================================

def _validate_track_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate tracking capability.

    The actual order ownership/status lookup remains a backend
    responsibility.
    """

    order_id = state.get(
        "order_id"
    )

    planned_arguments = _get_planned_arguments(
        state
    )

    planned_order_id = (
        planned_arguments.get(
            "order_id"
        )
    )

    if not (
        _has_value(
            order_id
        )
        or _has_value(
            planned_order_id
        )
    ):
        return _failure(
            "missing_order_reference",
            action=action,
            tool=tool,
            retryable=True,
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate CANCEL_ORDER
# =========================================================

def _validate_cancel_order(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate that a cancellation request contains an order
    reference.

    Whether cancellation is actually allowed is determined
    by the backend/order service.
    """

    order_id = state.get(
        "order_id"
    )

    planned_arguments = _get_planned_arguments(
        state
    )

    planned_order_id = (
        planned_arguments.get(
            "order_id"
        )
    )

    if not (
        _has_value(
            order_id
        )
        or _has_value(
            planned_order_id
        )
    ):
        return _failure(
            "missing_order_reference",
            action=action,
            tool=tool,
            retryable=True,
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Cart Reference Helpers
# =========================================================

def _cart_reference(
    state: GraphState,
    arguments: dict[str, Any],
) -> tuple[str | None, Any]:
    """
    Return the strongest available cart-item reference.

    Supported references:

        cart_item_id
        item_id
        product_id
        product_name

    Policy does not decide which product ID is authoritative.

    If product_name is supplied, the backend may resolve it.
    """

    # -----------------------------------------------------
    # Explicit cart item ID
    # -----------------------------------------------------

    for key in (
        "cart_item_id",
        "item_id",
    ):
        value = _get_argument(
            state,
            arguments,
            key,
        )

        if _has_value(
            value
        ):
            return (
                key,
                value,
            )

    # -----------------------------------------------------
    # Product ID
    # -----------------------------------------------------

    product_id = _get_argument(
        state,
        arguments,
        "product_id",
    )

    if _has_value(
        product_id
    ):
        return (
            "product_id",
            product_id,
        )

    # -----------------------------------------------------
    # Product name
    # -----------------------------------------------------

    product_name = _get_argument(
        state,
        arguments,
        "product_name",
    )

    if _has_value(
        product_name
    ):
        return (
            "product_name",
            product_name,
        )

    return (
        None,
        None,
    )


# =========================================================
# Validate ADD_TO_CART
# =========================================================

def _validate_add_to_cart(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate an add-to-cart proposal.

    Policy checks only that the request contains enough
    information to identify the requested item and quantity.

    Backend remains responsible for:

        - resolving product identity
        - verifying product existence
        - verifying stock
        - calculating price
        - calculating cart totals
        - mutating the cart
    """

    arguments = _get_planned_arguments(
        state
    )

    reference_type, reference = (
        _cart_reference(
            state,
            arguments,
        )
    )

    if reference_type is None:
        return _failure(
            "missing_cart_product_reference",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=[
                "product_id_or_product_name"
            ],
        )

    quantity = _get_argument(
        state,
        arguments,
        "quantity",
    )

    if not _positive_integer(
        quantity
    ):
        return _failure(
            "invalid_cart_quantity",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=[
                "quantity"
            ],
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate REMOVE_FROM_CART
# =========================================================

def _validate_remove_from_cart(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a remove-from-cart proposal.

    At least one item/product reference must be supplied.

    Backend determines whether the item actually exists in
    the user's cart and whether the user is authorized to
    mutate that cart.
    """

    arguments = _get_planned_arguments(
        state
    )

    reference_type, reference = (
        _cart_reference(
            state,
            arguments,
        )
    )

    if reference_type is None:
        return _failure(
            "missing_cart_item_reference",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=[
                "cart_item_id_or_product_id_or_product_name"
            ],
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate UPDATE_CART_ITEM
# =========================================================

def _validate_update_cart_item(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a cart quantity update.

    A cart item/product reference and a positive quantity are
    required.

    Backend determines whether the cart item exists and
    whether the requested quantity is actually available.
    """

    arguments = _get_planned_arguments(
        state
    )

    reference_type, reference = (
        _cart_reference(
            state,
            arguments,
        )
    )

    if reference_type is None:
        return _failure(
            "missing_cart_item_reference",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=[
                "cart_item_id_or_product_id_or_product_name"
            ],
        )

    quantity = _get_argument(
        state,
        arguments,
        "quantity",
    )

    if not _positive_integer(
        quantity
    ):
        return _failure(
            "invalid_cart_quantity",
            action=action,
            tool=tool,
            retryable=True,
            missing_fields=[
                "quantity"
            ],
        )

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate CLEAR_CART
# =========================================================

def _validate_clear_cart(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a clear-cart proposal.

    No product or quantity is required.

    Backend remains responsible for:

        - identifying the user's cart
        - verifying ownership
        - clearing the cart
    """

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate SHOW_CART
# =========================================================

def _validate_show_cart(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a show-cart proposal.

    No product or quantity is required.

    Backend remains responsible for retrieving the
    authoritative cart state.
    """

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate CHECKOUT_CART
# =========================================================

def _validate_checkout_cart(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate the transition from cart to checkout.

    This policy check does NOT create an order.

    It only ensures that:
        - an already-completed transaction is not reused
        - a checkout/cart transaction has the required state

    Backend remains responsible for actual cart validation,
    stock, pricing, billing, payment, and order creation.
    """

    # -----------------------------------------------------
    # Duplicate transaction protection
    # -----------------------------------------------------

    if _transaction_already_completed(
        state
    ):
        return _failure(
            "checkout_already_completed",
            action=action,
            tool=tool,
            retryable=False,
        )

    # -----------------------------------------------------
    # Checkout ID
    # -----------------------------------------------------
    #
    # checkout_cart should not create a checkout ID inside
    # Policy. If the application architecture requires a
    # durable checkout ID before this boundary, it must already
    # exist in GraphState.
    #
    # -----------------------------------------------------

    checkout_id = state.get(
        "checkout_id"
    )

    if not _has_value(
        checkout_id
    ):
        return _failure(
            "missing_checkout_id",
            action=action,
            tool=tool,
            retryable=True,
        )

    # -----------------------------------------------------
    # Do not require all CREATE_ORDER fields here.
    # -----------------------------------------------------
    #
    # CHECKOUT_CART is a cart → checkout transition.
    #
    # The checkout workflow may still need:
    #
    #     product
    #     quantity
    #     address
    #     payment
    #
    # before CREATE_ORDER.
    #
    # Therefore Policy must not prematurely treat
    # CHECKOUT_CART as CREATE_ORDER.
    #
    # -----------------------------------------------------

    return _success(
        action,
        tool,
    )


# =========================================================
# Validate Cart Action
# =========================================================

def _validate_cart_action(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a Phase-3 cart capability.

    The action/tool pair is checked first.

    Then the appropriate deterministic validator is used.
    """

    expected_tool = CART_ACTION_TO_TOOL.get(
        action
    )

    if expected_tool is None:
        return _failure(
            "unsupported_cart_action",
            action=action,
            tool=tool,
            retryable=False,
        )

    # -----------------------------------------------------
    # Explicit action/tool binding
    # -----------------------------------------------------

    if tool != expected_tool:
        return _failure(
            "cart_action_tool_mismatch",
            action=action,
            tool=tool,
            retryable=False,
            expected_tool=expected_tool,
        )

    # -----------------------------------------------------
    # Individual cart validators
    # -----------------------------------------------------

    if action == "ADD_TO_CART":
        return _validate_add_to_cart(
            state,
            action,
            tool,
        )

    if action == "REMOVE_FROM_CART":
        return _validate_remove_from_cart(
            state,
            action,
            tool,
        )

    if action == "UPDATE_CART_ITEM":
        return _validate_update_cart_item(
            state,
            action,
            tool,
        )

    if action == "CLEAR_CART":
        return _validate_clear_cart(
            state,
            action,
            tool,
        )

    if action == "SHOW_CART":
        return _validate_show_cart(
            state,
            action,
            tool,
        )

    if action == "CHECKOUT_CART":
        return _validate_checkout_cart(
            state,
            action,
            tool,
        )

    return _failure(
        "unsupported_cart_action",
        action=action,
        tool=tool,
        retryable=False,
    )


# =========================================================
# Validate Generic Tool
# =========================================================

def _validate_generic_tool(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a normal backend capability.

    The actual business validation happens in the backend.
    """

    return _success(
        action,
        tool,
    )


# =========================================================
# Policy Node
# =========================================================

def policy_node(
    state: GraphState,
) -> GraphState:
    """
    Validate the AI Planner's proposed action.

    The policy node is deliberately deterministic.

    AI decides:
        What does the user want?

    Policy verifies:
        Is this proposed action permitted by the current
        application/transaction state?

    Backend decides:
        Is the actual operation valid?
    """

    planner_decision = state.get(
        "planner_decision",
        {},
    )

    if not isinstance(
        planner_decision,
        dict,
    ):
        return _failure(
            "missing_planner_decision"
        )

    # =====================================================
    # Planner Action
    # =====================================================

    action = planner_decision.get(
        "action"
    )

    if not isinstance(
        action,
        str,
    ):
        return _failure(
            "invalid_planner_action"
        )

    action = (
        action
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    # =====================================================
    # Planner Tool
    # =====================================================

    tool = planner_decision.get(
        "tool"
    )

    # =====================================================
    # Tool Validation
    # =====================================================

    valid_tool, normalized_tool = (
        _validate_tool(
            tool
        )
    )

    if not valid_tool:
        return _failure(
            "unsupported_tool",
            action=action,
            tool=(
                tool
                if isinstance(
                    tool,
                    str,
                )
                else None
            ),
            retryable=False,
        )

    tool = normalized_tool

    # =====================================================
    # Non-tool conversational action
    # =====================================================

    if action in NON_TOOL_ACTIONS:

        # -------------------------------------------------
        # Critical completed-order protection
        # -------------------------------------------------
        #
        # A conversational message after a completed order
        # is allowed to remain conversational.
        #
        # It must never be converted into create_order merely
        # because checkout information remains in state.
        #
        # -------------------------------------------------

        return _success(
            action,
            None,
        )

    # =====================================================
    # Phase 3 - CART ACTIONS
    # =====================================================
    #
    # Handle these BEFORE the generic-tool fallback.
    #
    # This is important because cart capabilities have
    # capability-specific validation requirements.
    #
    # =====================================================

    if action in CART_ACTION_TO_TOOL:

        return _validate_cart_action(
            state,
            action,
            tool,
        )

    # =====================================================
    # CREATE_ORDER
    # =====================================================

    if action == "CREATE_ORDER":

        # The planner must explicitly request the order tool.
        if tool != "create_order":
            return _failure(
                "create_order_requires_create_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_create_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # TRACK_ORDER
    # =====================================================

    if action == "TRACK_ORDER":

        if tool != "track_order":
            return _failure(
                "track_order_requires_track_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_track_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # CANCEL_ORDER
    # =====================================================

    if action == "CANCEL_ORDER":

        if tool != "cancel_order":
            return _failure(
                "cancel_order_requires_cancel_order_tool",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _validate_cancel_order(
            state,
            action,
            tool,
        )

    # =====================================================
    # All Other Tool Actions
    # =====================================================

    if tool is None:
        return _failure(
            "tool_required_for_action",
            action=action,
            tool=None,
            retryable=False,
        )

    return _validate_generic_tool(
        state,
        action,
        tool,
    )