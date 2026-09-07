"""
BuyQK AI Engine
Tool Results

Defines the standardized result contract returned by BuyQK tools.

Responsibilities:
- Represent successful tool execution.
- Represent failed tool execution.
- Normalize ToolError exceptions.
- Preserve structured error information.
- Provide a predictable interface for the Tool Node and
  Response Node.

Business logic belongs in:
    backend/services/

Tool registration belongs in:
    ai_engine/tools/registry.py

Tool exceptions belong in:
    ai_engine/tools/errors.py
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Mapping, TypeVar

from ai_engine.tools.errors import ToolError


# =========================================================
# Type Variables
# =========================================================

T = TypeVar("T")


# =========================================================
# Normalized Tool Error
# =========================================================

@dataclass(frozen=True, slots=True)
class ToolErrorResult:
    """
    Machine-readable representation of a tool failure.

    Attributes:
        code:
            Stable machine-readable error code.

        message:
            Human-readable error message.

        details:
            Optional structured diagnostic information.
    """

    code: str
    message: str
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.code,
            str,
        ):
            raise TypeError(
                "Tool error code must be a string."
            )

        if not self.code.strip():
            raise ValueError(
                "Tool error code cannot be empty."
            )

        if not isinstance(
            self.message,
            str,
        ):
            raise TypeError(
                "Tool error message must be a string."
            )

        if not self.message.strip():
            raise ValueError(
                "Tool error message cannot be empty."
            )

        if (
            self.details is not None
            and not isinstance(
                self.details,
                Mapping,
            )
        ):
            raise TypeError(
                "Tool error details must be a mapping or None."
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the normalized error into a JSON-compatible
        dictionary.
        """

        return {
            "code": self.code,
            "message": self.message,
            "details": (
                dict(self.details)
                if self.details is not None
                else None
            ),
        }


# =========================================================
# Tool Result
# =========================================================

@dataclass(frozen=True, slots=True)
class ToolResult(Generic[T]):
    """
    Standard result returned by a BuyQK tool.

    A ToolResult is either:

        success=True
        data=<backend result>
        error=None

    or:

        success=False
        data=None
        error=<ToolErrorResult>

    The contract deliberately keeps business data generic.
    Product, cart, order, checkout, and service tools can
    provide their own data structures.
    """

    success: bool
    tool: str
    data: T | None = None
    error: ToolErrorResult | None = None

    def __post_init__(self) -> None:
        """
        Validate the result contract.
        """

        if not isinstance(
            self.success,
            bool,
        ):
            raise TypeError(
                "ToolResult.success must be a boolean."
            )

        if not isinstance(
            self.tool,
            str,
        ):
            raise TypeError(
                "ToolResult.tool must be a string."
            )

        if not self.tool.strip():
            raise ValueError(
                "ToolResult.tool cannot be empty."
            )

        # -------------------------------------------------
        # Success invariant
        # -------------------------------------------------

        if self.success:

            if self.error is not None:
                raise ValueError(
                    "A successful ToolResult cannot contain an error."
                )

        # -------------------------------------------------
        # Failure invariant
        # -------------------------------------------------

        else:

            if self.error is None:
                raise ValueError(
                    "A failed ToolResult must contain an error."
                )

            if self.data is not None:
                raise ValueError(
                    "A failed ToolResult cannot contain data."
                )

    # =====================================================
    # Constructors
    # =====================================================

    @classmethod
    def ok(
        cls,
        tool: str,
        data: T | None = None,
    ) -> "ToolResult[T]":
        """
        Create a successful tool result.

        Example:

            return ToolResult.ok(
                tool="search_products",
                data=products,
            )
        """

        return cls(
            success=True,
            tool=tool,
            data=data,
            error=None,
        )

    @classmethod
    def fail(
        cls,
        tool: str,
        error: ToolErrorResult,
    ) -> "ToolResult[None]":
        """
        Create a failed tool result from a normalized error.
        """

        if not isinstance(
            error,
            ToolErrorResult,
        ):
            raise TypeError(
                "error must be a ToolErrorResult."
            )

        return cls(
            success=False,
            tool=tool,
            data=None,
            error=error,
        )

    @classmethod
    def from_error(
        cls,
        tool: str,
        error: ToolError,
    ) -> "ToolResult[None]":
        """
        Convert a BuyQK ToolError into a normalized failure.
        """

        if not isinstance(
            error,
            ToolError,
        ):
            raise TypeError(
                "error must be a ToolError."
            )

        return cls.fail(
            tool=tool,
            error=ToolErrorResult(
                code=error.code,
                message=error.message,
                details=error.details,
            ),
        )

    @classmethod
    def from_exception(
        cls,
        tool: str,
        error: Exception,
    ) -> "ToolResult[None]":
        """
        Normalize an arbitrary exception.

        ToolError instances preserve their structured error
        information.

        Unknown exceptions are converted into a generic
        backend/tool execution error without exposing the
        raw exception to the customer-facing response layer.
        """

        if isinstance(
            error,
            ToolError,
        ):
            return cls.from_error(
                tool=tool,
                error=error,
            )

        return cls.fail(
            tool=tool,
            error=ToolErrorResult(
                code="tool_execution_error",
                message="Tool execution failed.",
                details=None,
            ),
        )

    # =====================================================
    # State / API Conversion
    # =====================================================

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the result into a JSON-compatible dictionary.

        Example success:

            {
                "success": True,
                "tool": "search_products",
                "data": {...},
                "error": None,
            }

        Example failure:

            {
                "success": False,
                "tool": "search_products",
                "data": None,
                "error": {
                    "code": "not_found",
                    "message": "Product was not found.",
                    "details": None,
                },
            }
        """

        return {
            "success": self.success,
            "tool": self.tool,
            "data": self.data,
            "error": (
                self.error.to_dict()
                if self.error is not None
                else None
            ),
        }

    # =====================================================
    # Backward-Compatible Mapping Interface
    # =====================================================

    def _legacy_payload(self) -> dict[str, Any]:
        """
        Return the flat presentation payload historically exposed by
        the Tool Node.

        Canonical storage remains:
            success / tool / data / error

        The graph and older tests/callers may still access:
            result["success"]
            result.get("success")
            result["cart_id"]
            result.get("order_id")
            result["products"]

        For a successful result, fields inside ``data`` are exposed
        at the top level for compatibility. Canonical ToolResult fields
        always take precedence.
        """

        payload: dict[str, Any] = {
            "success": self.success,
            "tool": self.tool,
            "data": self.data,
            "error": (
                self.error.to_dict()
                if self.error is not None
                else None
            ),
        }

        if isinstance(self.data, Mapping):
            for key, value in self.data.items():
                payload.setdefault(
                    key,
                    value,
                )

        return payload

    def __getitem__(self, key: str) -> Any:
        """
        Backward-compatible dictionary-style access.

        This does NOT change the canonical ToolResult contract; it only
        prevents existing graph/tests from breaking during migration.
        """

        return self._legacy_payload()[key]

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Backward-compatible dict.get() access.
        """

        return self._legacy_payload().get(
            key,
            default,
        )

    def __contains__(self, key: object) -> bool:
        """
        Support ``key in result`` for legacy callers.
        """

        return key in self._legacy_payload()

    def keys(self):
        """
        Return legacy-compatible payload keys.
        """

        return self._legacy_payload().keys()

    def items(self):
        """
        Return legacy-compatible payload items.
        """

        return self._legacy_payload().items()

    def values(self):
        """
        Return legacy-compatible payload values.
        """

        return self._legacy_payload().values()

    def is_success(self) -> bool:
        """
        Return True when the tool failed.
        """

        return self.success

    def is_failure(self) -> bool:
        """
        Return True when the tool execution failed.
        """
        return not self.success


# =========================================================
# Convenience Functions
# =========================================================

def success_result(
    tool: str,
    data: T | None = None,
) -> ToolResult[T]:
    """
    Convenience wrapper for ToolResult.ok().
    """

    return ToolResult.ok(
        tool=tool,
        data=data,
    )


def failure_result(
    tool: str,
    error: ToolError,
) -> ToolResult[None]:
    """
    Convenience wrapper for ToolResult.from_error().
    """

    return ToolResult.from_error(
        tool=tool,
        error=error,
    )


def normalize_exception(
    tool: str,
    error: Exception,
) -> ToolResult[None]:
    """
    Convert any exception into a normalized ToolResult.
    """

    return ToolResult.from_exception(
        tool=tool,
        error=error,
    )


def result_to_dict(
    result: Any,
) -> dict[str, Any]:
    """Convert a ToolResult or legacy dictionary for presentation/serialization."""
    if isinstance(result, ToolResult):
        payload = result.to_dict()
        if isinstance(result.data, dict):
            payload.update(result.data)
        return payload

    if isinstance(result, dict):
        return dict(result)

    return {}


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ToolErrorResult",
    "ToolResult",
    "success_result",
    "failure_result",
    "normalize_exception",
    "result_to_dict",
]