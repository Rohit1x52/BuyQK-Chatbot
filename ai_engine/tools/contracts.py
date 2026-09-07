"""
BuyQK AI Engine
Tool Contracts

Defines the common contract used by all backend tools.

Responsibilities:
- Define tool metadata.
- Define the callable tool interface.
- Keep tool infrastructure independent from business logic.

Business logic belongs in:
    backend/services/

Tool execution belongs in:
    ai_engine/tools/
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


# =========================================================
# Type Aliases
# =========================================================

ToolHandler = Callable[..., Any]


# =========================================================
# Tool Contract
# =========================================================

@dataclass(frozen=True, slots=True)
class ToolContract:
    """
    Describes a single BuyQK backend capability.

    A ToolContract contains metadata and the callable handler
    required to execute the capability.

    The contract itself does not execute business logic.

    Example:

        ToolContract(
            name="search_products",
            description="Search available products.",
            category="product",
            handler=search_products,
        )
    """

    name: str
    description: str
    category: str
    handler: ToolHandler

    # Whether the operation only reads backend state.
    read_only: bool = True

    # Optional input schema/metadata.
    #
    # This remains generic at the infrastructure layer.
    # Individual tools can later provide their own schema.
    input_schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """
        Validate the structural integrity of the contract.
        """

        if not isinstance(self.name, str):
            raise TypeError(
                "Tool name must be a string."
            )

        normalized_name = self.name.strip()

        if not normalized_name:
            raise ValueError(
                "Tool name cannot be empty."
            )

        if normalized_name != self.name:
            raise ValueError(
                "Tool name cannot contain leading or trailing whitespace."
            )

        if not isinstance(
            self.description,
            str,
        ):
            raise TypeError(
                "Tool description must be a string."
            )

        if not self.description.strip():
            raise ValueError(
                "Tool description cannot be empty."
            )

        if not isinstance(
            self.category,
            str,
        ):
            raise TypeError(
                "Tool category must be a string."
            )

        if not self.category.strip():
            raise ValueError(
                "Tool category cannot be empty."
            )

        if not callable(self.handler):
            raise TypeError(
                "Tool handler must be callable."
            )

        if not isinstance(
            self.read_only,
            bool,
        ):
            raise TypeError(
                "read_only must be a boolean."
            )

        if (
            self.input_schema is not None
            and not isinstance(
                self.input_schema,
                Mapping,
            )
        ):
            raise TypeError(
                "input_schema must be a mapping or None."
            )


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ToolContract",
    "ToolHandler",
]