"""
BuyQK AI Engine
Tool Errors

Defines the standardized exception hierarchy used by the
BuyQK tool infrastructure.

Responsibilities:
- Provide a common base exception for tool failures.
- Represent predictable categories of tool failures.
- Preserve machine-readable error codes.
- Preserve human-readable error messages.
- Keep backend implementation details away from the graph.

Business logic belongs in:
    backend/services/

Result normalization belongs in:
    ai_engine/tools/results.py
"""


from __future__ import annotations

from typing import Any


# =========================================================
# Base Tool Error
# =========================================================

class ToolError(Exception):
    """
    Base exception for all expected BuyQK tool failures.

    Attributes:
        message:
            Human-readable description of the failure.

        code:
            Stable machine-readable error identifier.

        details:
            Optional structured information useful for logging,
            debugging, or downstream result normalization.

    Example:

        raise ToolError(
            message="Product ID is required.",
            code="missing_product_id",
        )
    """

    default_code = "tool_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:

        if not isinstance(
            message,
            str,
        ):
            raise TypeError(
                "Tool error message must be a string."
            )

        message = message.strip()

        if not message:
            raise ValueError(
                "Tool error message cannot be empty."
            )

        resolved_code = (
            code
            if code is not None
            else self.default_code
        )

        if not isinstance(
            resolved_code,
            str,
        ):
            raise TypeError(
                "Tool error code must be a string."
            )

        resolved_code = resolved_code.strip()

        if not resolved_code:
            raise ValueError(
                "Tool error code cannot be empty."
            )

        if details is not None and not isinstance(
            details,
            dict,
        ):
            raise TypeError(
                "Tool error details must be a dictionary or None."
            )

        self.message = message
        self.code = resolved_code
        self.details = details

        super().__init__(message)

    def __str__(self) -> str:
        return self.message


# =========================================================
# Validation Error
# =========================================================

class ToolValidationError(ToolError):
    """
    Raised when tool input is invalid or incomplete.

    Examples:
        Missing required argument.
        Invalid quantity.
        Invalid product ID.
        Invalid date/time.
    """

    default_code = "validation_error"


# =========================================================
# Not Found Error
# =========================================================

class ToolNotFoundError(ToolError):
    """
    Raised when a requested backend resource does not exist.

    Examples:
        Product not found.
        Order not found.
        Address not found.
    """

    default_code = "not_found"


# =========================================================
# Availability Error
# =========================================================

class ToolAvailabilityError(ToolError):
    """
    Raised when a requested resource or capability is
    currently unavailable.

    Examples:
        Product out of stock.
        Requested quantity unavailable.
        Service slot unavailable.
    """

    default_code = "availability_error"


# =========================================================
# Authorization Error
# =========================================================

class ToolAuthorizationError(ToolError):
    """
    Raised when the current user is not authorized to perform
    the requested operation or access the requested resource.
    """

    default_code = "authorization_error"


# =========================================================
# Conflict Error
# =========================================================

class ToolConflictError(ToolError):
    """
    Raised when the requested operation conflicts with the
    current backend state.

    Examples:
        Attempting to cancel an already cancelled order.
        Attempting to modify a completed order.
        Conflicting checkout state.
    """

    default_code = "conflict_error"


# =========================================================
# Backend Error
# =========================================================

class ToolBackendError(ToolError):
    """
    Raised when an underlying backend dependency fails.

    This represents infrastructure/service failures rather
    than user-input validation failures.

    Examples:
        Database failure.
        Backend service unavailable.
        External API failure.
    """

    default_code = "backend_error"


# =========================================================
# Tool Execution Error
# =========================================================

class ToolExecutionError(ToolError):
    """
    Raised when a registered tool cannot complete execution
    even though its input passed validation.

    This is useful for failures that occur inside the tool
    execution layer itself.
    """

    default_code = "execution_error"


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "ToolError",
    "ToolValidationError",
    "ToolNotFoundError",
    "ToolAvailabilityError",
    "ToolAuthorizationError",
    "ToolConflictError",
    "ToolBackendError",
    "ToolExecutionError",
]