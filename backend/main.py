# Responsibilities:
# - Create the FastAPI application
# - Define application metadata
# - Provide a basic health-check endpoint
# - Serve as the entry point for Uvicorn


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure repo root is on sys.path so absolute imports work when running
# the module from the `backend/` directory (e.g. `uvicorn main:app`).
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Register routers (use absolute imports to work reliably)
from backend.api.chat import router as chat_router
from backend.api.health import router as health_router
from backend.api.addresses import router as addresses_router

# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title="BuyQK Backend",
    description="Backend API for the BuyQK AI shopping assistant.",
    version="0.1.0",
)

# Enable CORS for local frontend development
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


# Register application routers
app.include_router(
    health_router
)

app.include_router(
    chat_router
)

app.include_router(
    addresses_router
)


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health_check():
    """
    Basic health-check endpoint.

    Used to verify that the FastAPI application
    is running correctly.
    """

    return {
        "status": "ok",
        "service": "BuyQK Backend",
    }


# ---------------------------------------------------------
# Local Development Entry Point
# ---------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )