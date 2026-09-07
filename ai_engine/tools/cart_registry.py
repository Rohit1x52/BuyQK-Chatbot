"""
BuyQK AI Engine
Cart Tool Registry

Registers the canonical Cart tools with ToolRegistry.

Business logic:
    backend/services/cart_service.py

Tool wrappers:
    ai_engine/tools/cart_tools.py

Registry:
    ai_engine/tools/cart_registry.py
"""

from __future__ import annotations

from ai_engine.tools.contracts import ToolContract
from ai_engine.tools.registry import ToolRegistry

from ai_engine.tools.cart_tools import (
    add_to_cart_tool,
    remove_from_cart_tool,
    update_cart_item_tool,
    clear_cart_tool,
    get_cart_tool,
)


# =========================================================
# Input Schemas
# =========================================================

ADD_TO_CART_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "integer",
            "minimum": 1,
        },
        "product_id": {
            "type": "integer",
            "minimum": 1,
        },
        "quantity": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": [
        "user_id",
        "product_id",
        "quantity",
    ],
}


REMOVE_FROM_CART_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "integer",
            "minimum": 1,
        },
        "product_id": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": [
        "user_id",
        "product_id",
    ],
}


UPDATE_CART_ITEM_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "integer",
            "minimum": 1,
        },
        "product_id": {
            "type": "integer",
            "minimum": 1,
        },
        "quantity": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": [
        "user_id",
        "product_id",
        "quantity",
    ],
}


CLEAR_CART_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": [
        "user_id",
    ],
}


GET_CART_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": [
        "user_id",
    ],
}


# =========================================================
# Canonical Contracts
# =========================================================

ADD_TO_CART_CONTRACT = ToolContract(
    name="add_to_cart",
    description="Add a product to the user's shopping cart.",
    category="cart",
    handler=add_to_cart_tool,
    read_only=False,
    input_schema=ADD_TO_CART_INPUT_SCHEMA,
)


REMOVE_FROM_CART_CONTRACT = ToolContract(
    name="remove_from_cart",
    description="Remove a product from the user's shopping cart.",
    category="cart",
    handler=remove_from_cart_tool,
    read_only=False,
    input_schema=REMOVE_FROM_CART_INPUT_SCHEMA,
)


UPDATE_CART_ITEM_CONTRACT = ToolContract(
    name="update_cart_item",
    description="Update the quantity of a product in the user's shopping cart.",
    category="cart",
    handler=update_cart_item_tool,
    read_only=False,
    input_schema=UPDATE_CART_ITEM_INPUT_SCHEMA,
)


CLEAR_CART_CONTRACT = ToolContract(
    name="clear_cart",
    description="Remove all products from the user's shopping cart.",
    category="cart",
    handler=clear_cart_tool,
    read_only=False,
    input_schema=CLEAR_CART_INPUT_SCHEMA,
)


GET_CART_CONTRACT = ToolContract(
    name="get_cart",
    description="Retrieve the user's current shopping cart.",
    category="cart",
    handler=get_cart_tool,
    read_only=True,
    input_schema=GET_CART_INPUT_SCHEMA,
)


# =========================================================
# Cart Contracts
# =========================================================

CART_TOOL_CONTRACTS = (
    ADD_TO_CART_CONTRACT,
    REMOVE_FROM_CART_CONTRACT,
    UPDATE_CART_ITEM_CONTRACT,
    CLEAR_CART_CONTRACT,
    GET_CART_CONTRACT,
)


# =========================================================
# Registry Factory
# =========================================================

def create_cart_registry() -> ToolRegistry:
    """
    Create an independent registry containing the canonical
    Cart tools.
    """

    return ToolRegistry(
        tools=CART_TOOL_CONTRACTS,
    )


# =========================================================
# Default Registry
# =========================================================

cart_registry = create_cart_registry()


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ADD_TO_CART_INPUT_SCHEMA",
    "REMOVE_FROM_CART_INPUT_SCHEMA",
    "UPDATE_CART_ITEM_INPUT_SCHEMA",
    "CLEAR_CART_INPUT_SCHEMA",
    "GET_CART_INPUT_SCHEMA",
    "ADD_TO_CART_CONTRACT",
    "REMOVE_FROM_CART_CONTRACT",
    "UPDATE_CART_ITEM_CONTRACT",
    "CLEAR_CART_CONTRACT",
    "GET_CART_CONTRACT",
    "CART_TOOL_CONTRACTS",
    "create_cart_registry",
    "cart_registry",
]