"""
Engine Status Router — reports Python engine health.
Mounted at ``/api`` in the main FastAPI application.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/r-status")
async def engine_status() -> Dict[str, Any]:
    """Return Python engine status."""
    return {
        "status": "ok",
        "engine": "py",
        "message": "Python engine active.",
    }



