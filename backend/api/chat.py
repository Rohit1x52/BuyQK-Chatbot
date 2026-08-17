# Purpose:
# Exposes the BuyQK AI chat workflow through FastAPI.
#
# Flow:
#
# Client / Frontend
#       ↓
# POST /chat
#       ↓
# FastAPI
#       ↓
# Pydantic validation
#       ↓
# SQLAlchemy DB session
#       ↓
# run_chat()
#       ↓
# LangGraph
#       ↓
# Backend services
#       ↓
# SQLite
#       ↓
# AI response
#       ↓
# FastAPI response


from __future__ import annotations

import inspect
import sys
from pathlib import Path

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
# We currently run FastAPI from:
#
#     buyqk-ai/backend/
#
# But ai_engine/ is located beside backend/.
#
# Adding the project root allows Python to import:
#
#     ai_engine.graph.runner
#
# Later, when the project is packaged properly, this
# path handling can be removed.
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# =========================================================
# Local Backend Imports
# =========================================================

from backend.database.dependencies import get_db

from backend.schemas.chat_schema import (
    ChatRequest,
    ChatResponse,
)


# =========================================================
# AI Engine Import
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
    Process a user message through the BuyQK AI engine.

    Pipeline:

        Request
            ↓
        FastAPI
            ↓
        Pydantic validation
            ↓
        run_chat()
            ↓
        Conversation Memory
            ↓
        LangGraph
            ↓
        Backend services
            ↓
        SQLite
            ↓
        Response
    """

    try:

        # =================================================
        # Frontend Checkout Selections
        # =================================================
        #
        # These are authoritative selections made by the
        # user through the frontend.
        #
        # selected_address_id:
        #     Existing saved address selected by user.
        #
        # payment_method:
        #     Payment method selected by user.
        #
        # The LLM must NOT override these values.
        # =================================================

        selected_address_id = getattr(
            request,
            "selected_address_id",
            None,
        )

        payment_method = getattr(
            request,
            "payment_method",
            None,
        )


        # =================================================
        # Execute AI Workflow
        # =================================================

        run_chat_params = inspect.signature(
            run_chat
        ).parameters

        run_chat_kwargs = {
            "message": request.message,
            "session_id": request.session_id,
            "user_id": request.user_id,
            "db": db,
            "selected_address_id": (
                selected_address_id
            ),
        }

        if "payment_method" in run_chat_params:
            run_chat_kwargs["payment_method"] = (
                payment_method
            )

        result = run_chat(
            **run_chat_kwargs
        )


        # =================================================
        # Validate Graph Result
        # =================================================

        if not isinstance(
            result,
            dict,
        ):

            raise HTTPException(
                status_code=500,
                detail=(
                    "AI engine returned "
                    "an invalid response."
                ),
            )


        # =================================================
        # Extract Response
        # =================================================

        response_text = result.get(
            "response",
            "",
        )


        # =================================================
        # Extract Metadata
        # =================================================

        metadata = result.get(
            "metadata",
            {},
        )


        if metadata is None:

            metadata = {}


        # =================================================
        # Safety Check
        # =================================================

        if not response_text:

            raise HTTPException(
                status_code=500,
                detail=(
                    "AI engine returned "
                    "an empty response."
                ),
            )


        # =================================================
        # API Response
        # =================================================
        #
        # metadata may contain:
        #
        # Product search:
        #     products
        #
        # Address selection:
        #     type
        #     addresses
        #     allow_new
        #
        # Payment selection:
        #     type
        #     methods
        #
        # Order success:
        #     order_id
        #     total_amount
        #     status
        #     payment_method
        #     can_track
        #
        # Tracking:
        #     order_id
        #     status
        #
        # The frontend uses this metadata to decide which
        # UI component to render.
        # =================================================

        return {
            "response": response_text,

            "metadata": metadata,
        }


    # =====================================================
    # Known Validation / Business Errors
    # =====================================================

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


    # =====================================================
    # Preserve FastAPI HTTP Errors
    # =====================================================

    except HTTPException:

        raise


    # =====================================================
    # Unexpected Errors
    # =====================================================

    except Exception as exc:

        # -------------------------------------------------
        # Log server-side error
        # -------------------------------------------------
        #
        # Do NOT expose internal Python/SQL/database
        # details to the frontend.
        # -------------------------------------------------

        print(
            f"[CHAT ERROR] "
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