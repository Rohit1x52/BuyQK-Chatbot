"""
BuyQK AI Engine
Product Tool Registry

Defines the canonical product-tool registry.

Responsibilities:
- Define product tool contracts.
- Register product tools under canonical names.
- Provide an isolated product registry factory.
- Expose the default product registry.

Business logic remains in:
    backend/services/product_service.py

Tool execution remains in:
    ai_engine/tools/product_tools.py
"""

from __future__ import annotations

from ai_engine.tools.contracts import ToolContract
from ai_engine.tools.product_tools import (
    check_product_availability_tool,
    get_product_tool,
    search_products_tool,
)
from ai_engine.tools.registry import ToolRegistry


# =========================================================
# Input Schemas
# =========================================================

SEARCH_PRODUCTS_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Product search query.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of products to return.",
            "minimum": 1,
        },
    },
    "required": [
        "query",
    ],
}


GET_PRODUCT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_id": {
            "type": "integer",
            "description": "Product database ID.",
            "minimum": 1,
        },
    },
    "required": [
        "product_id",
    ],
}


CHECK_PRODUCT_AVAILABILITY_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_id": {
            "type": "integer",
            "description": "Product database ID.",
            "minimum": 1,
        },
        "quantity": {
            "type": "integer",
            "description": "Quantity requested.",
            "minimum": 1,
        },
    },
    "required": [
        "product_id",
    ],
}


# =========================================================
# Product Tool Contracts
# =========================================================

SEARCH_PRODUCTS_CONTRACT = ToolContract(
    name="search_products",
    description="Search available products.",
    category="product",
    handler=search_products_tool,
    read_only=True,
    input_schema=SEARCH_PRODUCTS_INPUT_SCHEMA,
)


GET_PRODUCT_CONTRACT = ToolContract(
    name="get_product",
    description="Retrieve a product by ID.",
    category="product",
    handler=get_product_tool,
    read_only=True,
    input_schema=GET_PRODUCT_INPUT_SCHEMA,
)


CHECK_PRODUCT_AVAILABILITY_CONTRACT = ToolContract(
    name="check_product_availability",
    description="Check whether a product is available in the requested quantity.",
    category="product",
    handler=check_product_availability_tool,
    read_only=True,
    input_schema=CHECK_PRODUCT_AVAILABILITY_INPUT_SCHEMA,
)


# =========================================================
# Canonical Product Contracts
# =========================================================

PRODUCT_TOOL_CONTRACTS = (
    SEARCH_PRODUCTS_CONTRACT,
    GET_PRODUCT_CONTRACT,
    CHECK_PRODUCT_AVAILABILITY_CONTRACT,
)


# =========================================================
# Product Registry Factory
# =========================================================

def create_product_registry() -> ToolRegistry:
    """
    Create a fresh ToolRegistry containing all canonical
    product tools.

    Every invocation returns an independent registry instance.
    """

    return ToolRegistry(
        tools=PRODUCT_TOOL_CONTRACTS,
    )


# =========================================================
# Default Product Registry
# =========================================================

product_registry = create_product_registry()


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "SEARCH_PRODUCTS_INPUT_SCHEMA",
    "GET_PRODUCT_INPUT_SCHEMA",
    "CHECK_PRODUCT_AVAILABILITY_INPUT_SCHEMA",
    "SEARCH_PRODUCTS_CONTRACT",
    "GET_PRODUCT_CONTRACT",
    "CHECK_PRODUCT_AVAILABILITY_CONTRACT",
    "PRODUCT_TOOL_CONTRACTS",
    "create_product_registry",
    "product_registry",
]