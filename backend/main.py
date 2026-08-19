# =========================================================
# BuyQK Backend - FastAPI Application
# =========================================================
#
# Responsibilities:
#   - Create the FastAPI application
#   - Define application metadata
#   - Register application routers
#   - Configure CORS
#   - Provide the Uvicorn entry point
#
# Registered API areas:
#   - Health
#   - Chat / AI
#   - Addresses
#   - Cart
#
# Business logic remains inside the appropriate service
# and AI layers. This file is only the application boundary.
#
# =========================================================


from __future__ import annotations


# =========================================================
# Standard Library
# =========================================================

import sys
from pathlib import Path


# =========================================================
# Ensure Repository Root Is Importable
# =========================================================
#
# This allows:
#
#     uvicorn main:app
#
# when executed from the backend directory, while also
# supporting:
#
#     uvicorn backend.main:app
#
# from the repository root.
#
# =========================================================

repo_root = Path(__file__).resolve().parent.parent

if str(repo_root) not in sys.path:
    sys.path.insert(
        0,
        str(repo_root),
    )


# =========================================================
# FastAPI
# =========================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# =========================================================
# API Routers
# =========================================================

from backend.api.chat import (
    router as chat_router,
)

from backend.api.health import (
    router as health_router,
)

from backend.api.addresses import (
    router as addresses_router,
)

from backend.api.cart import (
    router as cart_router,
)


# =========================================================
# FastAPI Application
# =========================================================

app = FastAPI(
    title="BuyQK Backend",
    description=(
        "Backend API for the BuyQK AI shopping assistant."
    ),
    version="0.1.0",
)


# =========================================================
# CORS
# =========================================================
#
# Local frontend development:
#
#   Next.js / React:
#       localhost:3000
#       localhost:3001
#
#   Alternative loopback:
#       127.0.0.1:3000
#       127.0.0.1:3001
#
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Register Application Routers
# =========================================================

# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

app.include_router(
    health_router,
)


# ---------------------------------------------------------
# AI / Chat
# ---------------------------------------------------------

app.include_router(
    chat_router,
)


# ---------------------------------------------------------
# Addresses
# ---------------------------------------------------------

app.include_router(
    addresses_router,
)


# ---------------------------------------------------------
# Cart
# ---------------------------------------------------------
#
# Cart endpoints are now exposed through:
#
#     /cart
#
# The cart router delegates all authoritative cart operations
# to backend.services.cart_service.
#
# =========================================================

app.include_router(
    cart_router,
)


# =========================================================
# Root Endpoint
# =========================================================
#
# This is intentionally lightweight.
#
# It does not replace the /health endpoint.
#
# =========================================================

@app.get("/")
def root():
    """
    Basic API information endpoint.
    """

    return {
        "service": "BuyQK Backend",
        "status": "ok",
        "version": "0.1.0",
    }


# =========================================================
# Local Development Entry Point
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )