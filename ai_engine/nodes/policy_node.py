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
#   Tool
#      ↓
#   Backend Service
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
#
# Those responsibilities belong to backend services.
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
    # Product
    # -----------------------------------------------------
    "search_products",

    # -----------------------------------------------------
    # Cart
    # -----------------------------------------------------
    "add_to_cart",
    "remove_from_cart",
    "update_cart_item",
    "clear_cart",
    "show_cart",
    "checkout_cart",

    # -----------------------------------------------------
    # Order
    # -----------------------------------------------------
    "create_order",
    "track_order",
    "cancel_order",

    # -----------------------------------------------------
    # Support
    # -----------------------------------------------------
    "create_support_ticket",

    # -----------------------------------------------------
    # Address
    # -----------------------------------------------------
    "list_saved_addresses",
}


# =========================================================
# Actions That Do Not Require Backend Tools
# =========================================================

NON_TOOL_ACTIONS = {
    "ANSWER",
    "ASK_CLARIFICATION",
    "CONFIRM",
    "END_CONVERSATION",
    "START_CHECKOUT",
    "MODIFY_CHECKOUT",
}


# =========================================================
# Cart Actions
# =========================================================

CART_ACTIONS = {
    "ADD_CART_ITEM",
    "REMOVE_CART_ITEM",
    "UPDATE_CART_ITEM",
    "CLEAR_CART",
    "SHOW_CART",
    "CHECKOUT_CART",
}


# =========================================================
# Cart Tool Mapping
# =========================================================

CART_TOOL_MAPPING = {
    "ADD_CART_ITEM": "add_to_cart",
    "REMOVE_CART_ITEM": "remove_from_cart",
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

    Numeric zero remains a valid value for generic state
    checks, although quantity validation separately rejects
    zero.
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
) -> GraphState:
    """
    Build a consistent Policy rejection result.
    """

    result = {
        "allowed": False,
        "action": action,
        "tool": tool,
        "reason": reason,
        "retryable": retryable,
    }

    return {
        "policy_result": result,
        "policy_error": result,
        "policy_decision": "deny",
        "policy_allowed": False,
        "policy_reason": reason,
        "tool_name": None,
        "planner_action": action,
        "planner_tool": tool,
        "planner_status": "rejected",
    }


def _success(
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Build a consistent Policy approval result.
    """

    result = {
        "allowed": True,
        "action": action,
        "tool": tool,
    }

    return {
        "policy_result": result,
        "policy_error": None,
        "policy_decision": "allow",
        "policy_allowed": True,
        "policy_reason": None,
        "tool_name": tool,
        "planner_action": action,
        "planner_tool": tool,
        "planner_status": "approved",
    }


# =========================================================
# Planned Arguments
# =========================================================

def _get_planned_arguments(
    state: GraphState,
) -> dict[str, Any]:
    """
    Safely retrieve Planner arguments.

    The current planner_node stores arguments in:

        planner_args

    The canonical GraphState compatibility field is:

        planned_arguments

    The legacy flat field is:

        arguments
    """

    planned_arguments = state.get(
        "planned_arguments"
    )

    if isinstance(
        planned_arguments,
        dict,
    ):
        return planned_arguments

    planner_args = state.get(
        "planner_args"
    )

    if isinstance(
        planner_args,
        dict,
    ):
        return planner_args

    arguments = state.get(
        "arguments"
    )

    if isinstance(
        arguments,
        dict,
    ):
        return arguments

    return {}


# =========================================================
# Argument Value Resolver
# =========================================================

def _get_argument(
    state: GraphState,
    *keys: str,
) -> Any:
    """
    Retrieve a value from Planner arguments first and then
    from GraphState.

    This allows the Policy node to work with both:

        planned_arguments
        state fields

    without allowing the LLM to bypass the state contract.
    """

    arguments = _get_planned_arguments(
        state
    )

    for key in keys:
        if key in arguments:
            value = arguments.get(key)

            if _has_value(value):
                return value

    for key in keys:
        value = state.get(key)

        if _has_value(value):
            return value

    return None


# =========================================================
# Product Reference Validation
# =========================================================

def _get_product_reference(
    state: GraphState,
) -> Any:
    """
    Retrieve the product reference supplied by the Planner.

    Preferred representation:

        product_name

    A product_id may already exist in authoritative GraphState
    after backend resolution, so it is accepted as a fallback.

    The Policy node does NOT resolve product names and does NOT
    verify that the product exists.
    """

    return _get_argument(
        state,
        "product_name",
        "product",
        "product_reference",
        "product_id",
    )


def _validate_product_reference(
    state: GraphState,
    action: str,
    tool: str,
) -> GraphState | None:
    """
    Validate that a Cart operation targeting a specific product
    has a product reference.

    Returns:
        None when valid.
        GraphState rejection when invalid.
    """

    product_reference = _get_product_reference(
        state
    )

    if not _has_value(
        product_reference
    ):
        return _failure(
            "missing_product_reference",
            action=action,
            tool=tool,
            retryable=True,
        )

    return None


# =========================================================
# Quantity Validation
# =========================================================

def _get_quantity(
    state: GraphState,
) -> Any:
    """
    Retrieve the requested quantity from Planner arguments
    or GraphState.
    """

    return _get_argument(
        state,
        "quantity",
    )


def _validate_positive_quantity(
    state: GraphState,
    action: str,
    tool: str,
) -> GraphState | None:
    """
    Validate that a Cart quantity is a positive integer.

    Business constraints such as maximum stock remain the
    responsibility of Cart Service/backend.
    """

    quantity = _get_quantity(
        state
    )

    if quantity is None:
        return _failure(
            "missing_quantity",
            action=action,
            tool=tool,
            retryable=True,
        )

    # bool is technically an int in Python.
    # It must not be accepted as a quantity.
    if isinstance(
        quantity,
        bool,
    ):
        return _failure(
            "invalid_quantity",
            action=action,
            tool=tool,
            retryable=True,
        )

    if not isinstance(
        quantity,
        int,
    ):
        return _failure(
            "invalid_quantity",
            action=action,
            tool=tool,
            retryable=True,
        )

    if quantity <= 0:
        return _failure(
            "invalid_quantity",
            action=action,
            tool=tool,
            retryable=True,
        )

    return None


# =========================================================
# Cart State Helpers
# =========================================================

def _get_cart_items(
    state: GraphState,
) -> list[Any]:
    """
    Safely retrieve the current cart items from GraphState.

    An unavailable cart snapshot is represented as an empty
    list for Policy purposes.

    The Policy node does not query the database itself.
    """

    cart_items = state.get(
        "cart_items",
        [],
    )

    if isinstance(
        cart_items,
        list,
    ):
        return cart_items

    return []


def _cart_has_items(
    state: GraphState,
) -> bool:
    """
    Determine whether the current state contains at least one
    cart item.

    This is a state-level readiness check only.

    The backend remains authoritative.
    """

    cart_items = _get_cart_items(
        state
    )

    return len(cart_items) > 0


# =========================================================
# Completed Transaction Guard
# =========================================================

def _transaction_already_completed(
    state: GraphState,
) -> bool:
    """
    Determine whether this checkout already resulted in a
    successfully created order.

    This protects against duplicate order creation.
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

    # -----------------------------------------------------
    # Authoritative order_created flag
    # -----------------------------------------------------

    if order_created:
        return True

    # -----------------------------------------------------
    # Persisted order ID
    # -----------------------------------------------------

    if _has_value(
        order_id
    ):
        return True

    # -----------------------------------------------------
    # Terminal checkout status
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Explicit checkout completion
    # -----------------------------------------------------

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
    transaction fields required before CREATE_ORDER.

    This does NOT validate business facts such as:

        product exists
        stock is sufficient
        address belongs to user
        payment is currently available

    Those are backend responsibilities.
    """

    missing: list[str] = []

    if not (
        _has_value(
            state.get("product_id")
        )
        or _has_value(
            state.get("product_name")
        )
    ):
        missing.append(
            "product_name"
        )

    if not _has_value(
        state.get("quantity")
    ):
        missing.append(
            "quantity"
        )

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

    tool = tool.strip()

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
# Validate Cart Action
# =========================================================

def _validate_cart_action(
    state: GraphState,
    action: str,
    tool: str | None,
) -> GraphState:
    """
    Validate a Cart action proposed by the Planner.

    This function validates ONLY what can safely be checked
    at the Policy layer.

    It does NOT:
        - query Product
        - query stock
        - calculate price
        - calculate totals
        - modify Cart
        - create an order

    Those operations belong to Cart Service/backend.
    """

    # -----------------------------------------------------
    # Action → canonical tool mapping
    # -----------------------------------------------------

    expected_tool = CART_TOOL_MAPPING.get(
        action
    )

    if expected_tool is None:
        return _failure(
            "invalid_cart_action",
            action=action,
            tool=tool,
            retryable=False,
        )

    if tool != expected_tool:
        return _failure(
            "cart_action_tool_mismatch",
            action=action,
            tool=tool,
            retryable=False,
        )

    # -----------------------------------------------------
    # ADD_CART_ITEM
    # -----------------------------------------------------

    if action == "ADD_CART_ITEM":

        product_error = _validate_product_reference(
            state,
            action,
            tool,
        )

        if product_error is not None:
            return product_error

        quantity_error = _validate_positive_quantity(
            state,
            action,
            tool,
        )

        if quantity_error is not None:
            return quantity_error

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # REMOVE_CART_ITEM
    # -----------------------------------------------------

    if action == "REMOVE_CART_ITEM":

        product_error = _validate_product_reference(
            state,
            action,
            tool,
        )

        if product_error is not None:
            return product_error

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # UPDATE_CART_ITEM
    # -----------------------------------------------------

    if action == "UPDATE_CART_ITEM":

        product_error = _validate_product_reference(
            state,
            action,
            tool,
        )

        if product_error is not None:
            return product_error

        quantity_error = _validate_positive_quantity(
            state,
            action,
            tool,
        )

        if quantity_error is not None:
            return quantity_error

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # CLEAR_CART
    # -----------------------------------------------------

    if action == "CLEAR_CART":

        # Clearing an already empty cart is safe.
        #
        # We intentionally do NOT reject it because DELETE /
        # clear operations should be idempotent.
        #
        # Backend Cart Service remains responsible for the
        # actual operation.

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # SHOW_CART
    # -----------------------------------------------------

    if action == "SHOW_CART":

        # Viewing an empty cart is valid.
        #
        # Therefore no cart_items requirement exists here.

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # CHECKOUT_CART
    # -----------------------------------------------------

    if action == "CHECKOUT_CART":

        # Checkout cannot meaningfully proceed with an empty
        # cart.

        if not _cart_has_items(
            state
        ):
            return _failure(
                "empty_cart",
                action=action,
                tool=tool,
                retryable=True,
            )

        # If an order has already been created, do not allow
        # checkout to execute again.

        if _transaction_already_completed(
            state
        ):
            return _failure(
                "checkout_already_completed",
                action=action,
                tool=tool,
                retryable=False,
            )

        return _success(
            action,
            tool,
        )

    # -----------------------------------------------------
    # Defensive fallback
    # -----------------------------------------------------

    return _failure(
        "unsupported_cart_action",
        action=action,
        tool=tool,
        retryable=False,
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
        result = {
            "allowed": False,
            "action": action,
            "tool": tool,
            "reason": "checkout_incomplete",
            "missing_fields": missing,
            "retryable": True,
        }

        return {
            "policy_result": result,
            "policy_error": result,
            "policy_decision": "deny",
            "policy_allowed": False,
            "policy_reason": "checkout_incomplete",
            "tool_name": None,
            "missing_fields": missing,
            "planner_action": action,
            "planner_tool": tool,
            "planner_status": "rejected",
        }

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

    planned_order_id = None

    if isinstance(
        planned_arguments,
        dict,
    ):
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

    planned_order_id = None

    if isinstance(
        planned_arguments,
        dict,
    ):
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

    # =====================================================
    # Resolve Planner Decision
    # =====================================================

    planner_decision = state.get(
        "planner_decision"
    )

    # -----------------------------------------------------
    # Compatibility: planner object
    # -----------------------------------------------------

    if not isinstance(
        planner_decision,
        dict,
    ):

        planner = state.get(
            "planner"
        )

        if isinstance(
            planner,
            dict,
        ):
            planner_decision = {
                "action": planner.get(
                    "action"
                ),
                "tool": (
                    planner.get("tool")
                    or planner.get("tool_name")
                ),
                "arguments": planner.get(
                    "arguments",
                    {},
                ),
            }

        # -------------------------------------------------
        # Compatibility: planner_* fields
        # -------------------------------------------------

        elif _has_value(
            state.get(
                "planner_action"
            )
        ):
            planner_decision = {
                "action": state.get(
                    "planner_action"
                ),
                "tool": state.get(
                    "planner_tool"
                ),
                "arguments": state.get(
                    "planner_args",
                    {},
                ),
            }

        # -------------------------------------------------
        # Compatibility: flat planner output
        # -------------------------------------------------

        elif _has_value(
            state.get(
                "action"
            )
        ):
            planner_decision = {
                "action": state.get(
                    "action"
                ),
                "tool": (
                    state.get("tool")
                    or state.get("tool_name")
                ),
                "arguments": state.get(
                    "arguments",
                    {},
                ),
            }

        else:
            planner_decision = {
                "action": None,
                "tool": None,
                "arguments": {},
            }

    # =====================================================
    # Validate Planner Decision
    # =====================================================

    if not isinstance(
        planner_decision,
        dict,
    ):
        return _failure(
            "missing_planner_decision"
        )

    action = planner_decision.get(
        "action"
    )

    if not isinstance(
        action,
        str,
    ) or not action.strip():
        return _failure(
            "invalid_planner_action"
        )

    action = action.strip().upper()

    # =====================================================
    # Resolve Tool
    # =====================================================

    tool = planner_decision.get(
        "tool"
    )

    if isinstance(
        tool,
        str,
    ):
        tool = tool.strip()

    # -----------------------------------------------------
    # Canonical tool mapping
    #
    # This protects against a planner returning:
    #
    # ADD_CART_ITEM + "cart_manager"
    #
    # We require:
    #
    # ADD_CART_ITEM + "add_to_cart"
    # -----------------------------------------------------

    if action in CART_TOOL_MAPPING:

        expected_tool = CART_TOOL_MAPPING[
            action
        ]

        if tool is None:
            tool = expected_tool

        elif tool != expected_tool:
            return _failure(
                "cart_action_tool_mismatch",
                action=action,
                tool=tool,
                retryable=False,
            )

    elif not tool and action in {
        "CREATE_ORDER",
        "TRACK_ORDER",
        "CANCEL_ORDER",
    }:
        tool = {
            "CREATE_ORDER": "create_order",
            "TRACK_ORDER": "track_order",
            "CANCEL_ORDER": "cancel_order",
        }.get(
            action
        )

    # =====================================================
    # Planner Arguments
    # =====================================================

    planned_arguments = planner_decision.get(
        "arguments"
    )

    if not isinstance(
        planned_arguments,
        dict,
    ):
        planned_arguments = {}

    # -----------------------------------------------------
    # Compatibility mirror
    # -----------------------------------------------------

    state = dict(
        state
    )

    state["planned_arguments"] = (
        planned_arguments
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
        # These actions intentionally do not execute tools.
        # -------------------------------------------------

        return _success(
            action,
            None,
        )

    # =====================================================
    # CART ACTIONS
    # =====================================================

    if action in CART_ACTIONS:

        return _validate_cart_action(
            state,
            action,
            tool,
        )

    # =====================================================
    # CREATE_ORDER
    # =====================================================

    if action == "CREATE_ORDER":

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