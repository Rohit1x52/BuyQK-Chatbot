"""
BuyQK AI Engine
Response Contracts

Defines the standardized result contract produced by the
Response Node.

Responsibilities:
- Represent successful response generation.
- Represent failed response generation.
- Preserve the relationship between the response and the
  authoritative ToolResult.
- Carry user-facing text.
- Carry optional frontend metadata.
- Keep presentation-layer infrastructure independent from
  business logic.

Architecture:

    ToolResult
         +
    GraphState / conversation context
         ↓
    Response Node
         ↓
    ResponseResult

Important:
    ToolResult remains authoritative for backend facts.

    ResponseResult contains presentation output only.

Business logic belongs in:
    backend/services/

Tool execution belongs in:
    ai_engine/tools/

Graph orchestration belongs in:
    ai_engine/graph/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Mapping, TypeVar

from ai_engine.tools.results import ToolResult


# =========================================================
# Type Variables
# =========================================================

T = TypeVar("T")


# =========================================================
# Response Result
# =========================================================

@dataclass(frozen=True, slots=True)
class ResponseResult(Generic[T]):
    """
    Standard result produced by the BuyQK Response Node.

    A ResponseResult represents the presentation outcome of
    the response-generation step.

    Successful response:

        success=True
        message="Three packets of Tata Tea have been added."
        metadata={...}
        tool_result=<authoritative ToolResult>

    Failed response generation:

        success=False
        message=None
        metadata=None
        tool_result=<authoritative ToolResult or None>
        error="Response generation failed."

    The Response Node must never use ResponseResult to
    override backend-authoritative values.
    """

    success: bool

    # Final customer-facing natural-language response.
    message: str | None = None

    # Optional frontend metadata.
    #
    # Examples:
    #   {
    #       "type": "product_search",
    #   }
    #
    #   {
    #       "type": "cart_updated",
    #   }
    #
    #   {
    #       "type": "payment_selection",
    #       "methods": [...]
    #   }
    metadata: Mapping[str, Any] | None = None

    # The authoritative backend result used to generate
    # this response.
    #
    # This is optional because some responses, such as a
    # greeting, may not have a ToolResult.
    tool_result: ToolResult[Any] | None = None

    # Internal response-generation error.
    #
    # This is NOT intended to expose raw exceptions to the
    # customer.
    error: str | None = None

    def __post_init__(self) -> None:
        """
        Validate the response contract.
        """

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        if not isinstance(
            self.success,
            bool,
        ):
            raise TypeError(
                "ResponseResult.success must be a boolean."
            )

        # -------------------------------------------------
        # Message
        # -------------------------------------------------

        if self.message is not None:
            if not isinstance(
                self.message,
                str,
            ):
                raise TypeError(
                    "ResponseResult.message must be a string or None."
                )

            if not self.message.strip():
                raise ValueError(
                    "ResponseResult.message cannot be empty when provided."
                )

        # -------------------------------------------------
        # Metadata
        # -------------------------------------------------

        if (
            self.metadata is not None
            and not isinstance(
                self.metadata,
                Mapping,
            )
        ):
            raise TypeError(
                "ResponseResult.metadata must be a mapping or None."
            )

        # -------------------------------------------------
        # ToolResult
        # -------------------------------------------------

        if (
            self.tool_result is not None
            and not isinstance(
                self.tool_result,
                ToolResult,
            )
        ):
            raise TypeError(
                "ResponseResult.tool_result must be a ToolResult or None."
            )

        # -------------------------------------------------
        # Error
        # -------------------------------------------------

        if self.error is not None:
            if not isinstance(
                self.error,
                str,
            ):
                raise TypeError(
                    "ResponseResult.error must be a string or None."
                )

            if not self.error.strip():
                raise ValueError(
                    "ResponseResult.error cannot be empty when provided."
                )

        # -------------------------------------------------
        # Success invariants
        # -------------------------------------------------

        if self.success:

            if self.error is not None:
                raise ValueError(
                    "A successful ResponseResult cannot contain an error."
                )

            if self.message is None:
                raise ValueError(
                    "A successful ResponseResult must contain a message."
                )

        # -------------------------------------------------
        # Failure invariants
        # -------------------------------------------------

        else:

            if self.error is None:
                raise ValueError(
                    "A failed ResponseResult must contain an error."
                )

    # =====================================================
    # Constructors
    # =====================================================

    @classmethod
    def ok(
        cls,
        message: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        tool_result: ToolResult[Any] | None = None,
    ) -> "ResponseResult[T]":
        """
        Create a successful response result.

        Example:

            return ResponseResult.ok(
                message="Three packets of Tata Tea have been added.",
                tool_result=tool_result,
            )
        """

        return cls(
            success=True,
            message=message,
            metadata=metadata,
            tool_result=tool_result,
            error=None,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        *,
        message: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        tool_result: ToolResult[Any] | None = None,
    ) -> "ResponseResult[None]":
        """
        Create a failed response-generation result.

        ``error`` is an internal response-generation error.

        ``message`` may optionally contain a safe fallback
        customer-facing message.
        """

        return cls(
            success=False,
            message=message,
            metadata=metadata,
            tool_result=tool_result,
            error=error,
        )

    # =====================================================
    # Convenience Helpers
    # =====================================================

    def is_success(self) -> bool:
        """
        Return True when response generation succeeded.
        """

        return self.success

    def is_failure(self) -> bool:
        """
        Return True when response generation failed.
        """

        return not self.success

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the response result into a JSON-compatible
        presentation structure.

        The authoritative ToolResult is serialized through
        ToolResult.to_dict().
        """

        return {
            "success": self.success,
            "message": self.message,
            "metadata": (
                dict(self.metadata)
                if self.metadata is not None
                else None
            ),
            "tool_result": (
                self.tool_result.to_dict()
                if self.tool_result is not None
                else None
            ),
            "error": self.error,
        }


# =========================================================
# Convenience Functions
# =========================================================

def success_response(
    message: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    tool_result: ToolResult[Any] | None = None,
) -> ResponseResult[Any]:
    """
    Convenience wrapper for ResponseResult.ok().
    """

    return ResponseResult.ok(
        message=message,
        metadata=metadata,
        tool_result=tool_result,
    )


def failure_response(
    error: str,
    *,
    message: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    tool_result: ToolResult[Any] | None = None,
) -> ResponseResult[None]:
    """
    Convenience wrapper for ResponseResult.fail().
    """

    return ResponseResult.fail(
        error=error,
        message=message,
        metadata=metadata,
        tool_result=tool_result,
    )


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ResponseResult",
    "success_response",
    "failure_response",
]