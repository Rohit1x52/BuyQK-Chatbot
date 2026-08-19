# =========================================================
# BuyQK AI - Chat API
# =========================================================
#
# Purpose:
# Expose the BuyQK AI conversation workflow through FastAPI.
#
# Flow:
#
# Client / Frontend
#       ↓
# POST /chat
#       ↓
# Pydantic validation
#       ↓
# SQLAlchemy DB session
#       ↓
# run_chat()
#       ↓
# LangGraph
#       ↓
# AI understanding
#       ↓
# Decision
#       ↓
# Backend tools/services
#       ↓
# SQLite
#       ↓
# Authoritative transaction result
#       ↓
# AI response
#       ↓
# FastAPI response
#
#
# IMPORTANT:
#
# This API layer is NOT responsible for:
#
# - intent detection
# - entity extraction
# - product resolution
# - quantity interpretation
# - checkout decisions
# - order creation
# - billing calculation
# - price calculation
# - stock calculation
# - duplicate-order prevention
#
# Those responsibilities belong to the AI graph and backend
# services respectively.
#
# The API only:
#
# - validates the request
# - provides the DB session
# - passes authoritative frontend selections
# - executes the graph
# - returns the graph result
#
# =========================================================


from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any


from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session


# =========================================================
# Project Root
# =========================================================
#
# Project:
#
#     buyqk-ai/
#     ├── backend/
#     └── ai_engine/
#
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# =========================================================
# Backend Imports
# =========================================================

from backend.database.dependencies import (
    get_db,
)

from backend.schemas.chat_schema import (
    ChatRequest,
    ChatResponse,
)


# =========================================================
# AI Engine
# =========================================================

from ai_engine.graph.runner import (
    run_chat,
)


# =========================================================
# Router
# =========================================================

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


# =========================================================
# Helper - Optional Request Field
# =========================================================

def _request_value(
    request: ChatRequest,
    field_name: str,
    default: Any = None,
) -> Any:
    """
    Safely read an optional field from ChatRequest.

    This keeps the API compatible with older request schemas
    while allowing newer transaction fields such as:

        checkout_id
        selected_address_id
        payment_method

    to be passed through when available.

    The API does NOT interpret these values.
    """

    return getattr(
        request,
        field_name,
        default,
    )


# =========================================================
# Helper - Build run_chat Arguments
# =========================================================

def _build_run_chat_kwargs(
    request: ChatRequest,
    db: Session,
) -> dict[str, Any]:
    """
    Build the arguments passed to the AI graph runner.

    The API passes user/frontend information through.

    It does NOT make checkout or transaction decisions.
    """

    kwargs: dict[str, Any] = {
        "message": request.message,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "db": db,
    }

    # =====================================================
    # Frontend-authoritative address selection
    # =====================================================

    selected_address_id = _request_value(
        request,
        "selected_address_id",
    )

    if selected_address_id is not None:
        kwargs[
            "selected_address_id"
        ] = selected_address_id

    # =====================================================
    # Frontend-authoritative payment selection
    # =====================================================

    payment_method = _request_value(
        request,
        "payment_method",
    )

    if payment_method is not None:
        kwargs[
            "payment_method"
        ] = payment_method

    # =====================================================
    # New transaction checkout ID
    # =====================================================
    #
    # If the frontend/request already knows the checkout ID,
    # pass it through.
    #
    # The API does NOT generate an order ID.
    #
    # The backend transaction layer remains authoritative.
    #
    # =====================================================

    checkout_id = _request_value(
        request,
        "checkout_id",
    )

    if checkout_id is not None:
        kwargs[
            "checkout_id"
        ] = checkout_id

    return kwargs


# =========================================================
# Helper - Call Graph Runner
# =========================================================

def _run_graph(
    kwargs: dict[str, Any],
) -> Any:
    """
    Execute run_chat while remaining compatible with older
    runner signatures.

    Newer runners can consume:

        checkout_id
        selected_address_id
        payment_method

    Older runners simply receive the arguments they support.

    No business logic is performed here.
    """

    try:
        parameters = inspect.signature(
            run_chat
        ).parameters
    except (
        TypeError,
        ValueError,
    ):
        # If the callable signature cannot be inspected,
        # execute using the complete argument set.
        return run_chat(
            **kwargs
        )

    supported_kwargs = {
        name: value
        for name, value in kwargs.items()
        if name in parameters
    }

    return run_chat(
        **supported_kwargs
    )


# =========================================================
# Helper - Validate Graph Result
# =========================================================

def _validate_graph_result(
    result: Any,
) -> dict[str, Any]:
    """
    Validate the result returned by the LangGraph runner.
    """

    if not isinstance(
        result,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "AI engine returned "
                "an invalid response."
            ),
        )

    return result


# =========================================================
# Helper - Extract Response
# =========================================================

def _extract_response(
    result: dict[str, Any],
) -> str:
    """
    Extract the final AI response.

    The AI response must already have been generated by
    response_node.

    This API does not generate fallback transaction text.
    """

    response = result.get(
        "response"
    )

    if response is None:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "AI engine returned "
                "no response."
            ),
        )

    if not isinstance(
        response,
        str,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "AI engine returned "
                "an invalid response."
            ),
        )

    response = response.strip()

    if not response:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "AI engine returned "
                "an empty response."
            ),
        )

    return response


# =========================================================
# Helper - Extract Metadata
# =========================================================

def _extract_metadata(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract frontend metadata from GraphState.

    Metadata may contain:

        product search
        address selection
        payment selection
        order result
        bill
        tracking
        errors
        transaction state

    The API does not calculate or modify these values.
    """

    metadata = result.get(
        "metadata",
        {},
    )

    if metadata is None:
        return {}

    if not isinstance(
        metadata,
        dict,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "AI engine returned "
                "invalid metadata."
            ),
        )

    return metadata


# =========================================================
# Chat Endpoint
# =========================================================

@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Process a user message through BuyQK AI.

    The endpoint is intentionally thin.

    Request
        ↓
    AI graph
        ↓
    authoritative backend result
        ↓
    response
    """

    try:

        # =================================================
        # Build Graph Input
        # =================================================
        #
        # Frontend selections are passed through as
        # authoritative selections.
        #
        # The AI/entity node may understand the surrounding
        # conversation, but it must not overwrite a frontend
        # selection with a hallucinated value.
        #
        # =================================================

        run_chat_kwargs = (
            _build_run_chat_kwargs(
                request=request,
                db=db,
            )
        )

        # =================================================
        # Execute LangGraph
        # =================================================

        result = _run_graph(
            run_chat_kwargs
        )

        # =================================================
        # Validate Graph Result
        # =================================================

        result = _validate_graph_result(
            result
        )

        # =================================================
        # Final AI Response
        # =================================================

        response_text = _extract_response(
            result
        )

        # =================================================
        # Frontend Metadata
        # =================================================

        metadata = _extract_metadata(
            result
        )

        # =================================================
        # Return
        # =================================================
        #
        # IMPORTANT:
        #
        # Billing values are returned exactly as produced by
        # the authoritative backend/order service.
        #
        # Example:
        #
        # metadata = {
        #     "type": "order_success",
        #     "order_id": 10,
        #     "checkout_id": "...",
        #     "order_created": True,
        #     "bill": {
        #         "items": [...],
        #         "subtotal": ...,
        #         "delivery_charge": ...,
        #         "tax": ...,
        #         "discount": ...,
        #         "total": ...,
        #         "currency": ...
        #     }
        # }
        #
        # The API does not calculate any of these values.
        #
        # =================================================

        return {
            "response": response_text,
            "metadata": metadata,
        }

    # =====================================================
    # Business / Validation Error
    # =====================================================

    except ValueError as exc:

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    # =====================================================
    # Preserve Existing HTTP Errors
    # =====================================================

    except HTTPException:
        raise

    # =====================================================
    # Unexpected Error
    # =====================================================

    except Exception as exc:

        # -------------------------------------------------
        # Server-side logging
        # -------------------------------------------------
        #
        # Do not expose database/SQL/Python internals to
        # the frontend.
        #
        # -------------------------------------------------

        print(
            "[CHAT ERROR] "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Unable to process "
                "the chat request."
            ),
        ) from exc