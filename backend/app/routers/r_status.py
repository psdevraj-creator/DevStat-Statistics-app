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


@router.get("/logs")
async def get_backend_logs() -> Dict[str, Any]:
    """Return the last 2000 lines of the backend log file."""
    from app.logging_config import LOG_FILE
    if not LOG_FILE.exists():
        return {"available": False, "logs": "No log file found."}
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        return {"available": True, "path": str(LOG_FILE), "lineCount": len(lines), "logs": "\n".join(lines[-2000:])}
    except Exception as e:
        return {"available": False, "logs": f"Error reading log: {e}"}
