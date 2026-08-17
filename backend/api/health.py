# Purpose:
# Provides health-check endpoints for the BuyQK backend.


from fastapi import APIRouter


# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


# ---------------------------------------------------------
# Basic health check
# ---------------------------------------------------------

@router.get("")
def health_check():
    """
    Verify that the BuyQK backend is running.
    """

    return {
        "status": "ok",
        "service": "BuyQK Backend",
    }