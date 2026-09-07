"""
BuyQK AI Engine
Tool Registry

Responsibilities:
- Register backend tool capabilities.
- Prevent duplicate tool registrations.
- Retrieve registered tools.
- Check whether a tool exists.
- Execute registered tools through a common boundary.
- Normalize tool execution results.
- Convert unexpected exceptions into ToolResult failures.

The registry contains no business logic.

Business logic belongs in:
    backend/services/

Tool metadata belongs in:
    ai_engine/tools/contracts.py

Tool errors belong in:
    ai_engine/tools/errors.py

Tool results belong in:
    ai_engine/tools/results.py
"""


from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ai_engine.tools.contracts import (
    ToolContract,
)
from ai_engine.tools.errors import (
    ToolError,
)
from ai_engine.tools.results import (
    ToolErrorResult,
    ToolResult,
)


# =========================================================
# Tool Registry
# =========================================================

class ToolRegistry:
    """
    Central registry for BuyQK backend tools.

    The registry maps a canonical tool name to a ToolContract.

    Example:

        registry = ToolRegistry()

        registry.register(
            ToolContract(
                name="search_products",
                description="Search available products.",
                category="product",
                handler=search_products,
            )
        )

        result = registry.execute(
            "search_products",
            db=db,
            query="Amul milk",
        )
    """

    def __init__(
        self,
        tools: Iterable[ToolContract] | None = None,
    ) -> None:
        """
        Create an empty registry and optionally register an
        initial collection of tools.
        """

        self._tools: dict[str, ToolContract] = {}

        if tools is not None:
            for tool in tools:
                self.register(tool)

    # =====================================================
    # Registration
    # =====================================================

    def register(
        self,
        tool: ToolContract,
    ) -> ToolContract:
        """
        Register a ToolContract.

        Duplicate tool names are rejected.

        Returns:
            The registered ToolContract.

        Raises:
            TypeError:
                If the supplied object is not a ToolContract.

            ValueError:
                If another tool already uses the same name.
        """

        if not isinstance(
            tool,
            ToolContract,
        ):
            raise TypeError(
                "Only ToolContract instances can be registered."
            )

        name = tool.name

        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered."
            )

        self._tools[name] = tool

        return tool

    # =====================================================
    # Unregistration
    # =====================================================

    def unregister(
        self,
        name: str,
    ) -> ToolContract:
        """
        Remove and return a registered tool.

        Raises:
            ValueError:
                If the tool name is empty.

            KeyError:
                If the tool is not registered.
        """

        normalized_name = self._normalize_name(
            name
        )

        try:
            return self._tools.pop(
                normalized_name
            )
        except KeyError as exc:
            raise KeyError(
                f"Tool '{normalized_name}' is not registered."
            ) from exc

    # =====================================================
    # Lookup
    # =====================================================

    def get(
        self,
        name: str,
    ) -> ToolContract:
        """
        Retrieve a registered ToolContract.

        Raises:
            KeyError:
                If the tool does not exist.
        """

        normalized_name = self._normalize_name(
            name
        )

        try:
            return self._tools[
                normalized_name
            ]
        except KeyError as exc:
            raise KeyError(
                f"Tool '{normalized_name}' is not registered."
            ) from exc

    def has(
        self,
        name: str,
    ) -> bool:
        """
        Return True when a tool is registered.
        """

        normalized_name = self._normalize_name(
            name
        )

        return normalized_name in self._tools

    # =====================================================
    # Listing
    # =====================================================

    def list_tools(self) -> tuple[ToolContract, ...]:
        """
        Return all registered tools.

        The returned tuple prevents callers from modifying
        the registry's internal collection.
        """

        return tuple(
            self._tools.values()
        )

    def list_names(self) -> tuple[str, ...]:
        """
        Return all registered tool names.
        """

        return tuple(
            self._tools.keys()
        )

    # =====================================================
    # Execution
    # =====================================================

    def execute(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult[Any]:
        """
        Execute a registered tool.

        Execution always crosses the ToolResult boundary.

        Expected ToolError instances are converted into
        structured failures.

        Unexpected exceptions are also normalized so that
        raw backend exceptions do not escape into the graph.

        Example:

            result = registry.execute(
                "search_products",
                db=db,
                query="milk",
            )
        """

        normalized_name = self._normalize_name(
            name
        )

        if not self.has(
            normalized_name
        ):
            return ToolResult.fail(
                tool=normalized_name,
                error=self._unknown_tool_error(
                    normalized_name
                ),
            )

        tool = self._tools[
            normalized_name
        ]

        try:
            raw_result = tool.handler(
                *args,
                **kwargs,
            )

        except ToolError as exc:
            return ToolResult.from_error(
                tool=tool.name,
                error=exc,
            )

        except Exception as exc:
            return ToolResult.from_exception(
                tool=tool.name,
                error=exc,
            )

        return self._normalize_handler_result(
            tool=tool,
            result=raw_result,
        )

    # =====================================================
    # Handler Result Normalization
    # =====================================================

    @staticmethod
    def _normalize_handler_result(
        tool: ToolContract,
        result: Any,
    ) -> ToolResult[Any]:
        """
        Normalize a handler's return value.

        Supported handler return types:

        1. ToolResult
            Returned unchanged.

        2. None
            Converted to a successful ToolResult with no data.

        3. Any other value
            Wrapped as successful tool data.

        This allows backend service functions to remain simple:

            return products

        while the registry provides the standardized
        ToolResult boundary.
        """

        if isinstance(
            result,
            ToolResult,
        ):
            return result

        return ToolResult.ok(
            tool=tool.name,
            data=result,
        )

    # =====================================================
    # Name Normalization
    # =====================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Normalize a tool name for registry lookup.

        Only whitespace and casing are normalized.

        Business-specific aliases are intentionally NOT
        handled here.

        Example:

            " search_products "
                ↓
            "search_products"

        The registry must not decide that:

            "tracking"
                means
            "track_order"

        Such semantic/capability mapping belongs in the
        planner/policy/decision layer.
        """

        if not isinstance(
            name,
            str,
        ):
            raise TypeError(
                "Tool name must be a string."
            )

        normalized_name = name.strip().lower()

        if not normalized_name:
            raise ValueError(
                "Tool name cannot be empty."
            )

        return normalized_name

    # =====================================================
    # Unknown Tool Error
    # =====================================================

    @staticmethod
    def _unknown_tool_error(
        name: str,
    ) -> ToolErrorResult:
        """
        Create a normalized error for an unknown tool.

        The registry does not guess an alternative tool.
        """

        return ToolErrorResult(
            code="tool_not_registered",
            message=(
                f"Tool '{name}' is not registered."
            ),  
            details={
                "tool": name,
            },
        )


# =========================================================
# Default Registry
# =========================================================

default_registry = ToolRegistry()


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ToolRegistry",
    "default_registry",
]