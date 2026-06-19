"""
DevStat — Syntax Execution Router

Syntax execution is not available in the Python-only engine.
Previously used for running R code against the dataset.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SyntaxRunRequest(BaseModel):
    code: str


@router.post("/run")
async def syntax_run(req: SyntaxRunRequest) -> Dict[str, Any]:
    """Syntax execution is not available in Python-only mode."""
    raise HTTPException(
        status_code=503,
        detail="Syntax execution is not available in the Python-only engine.",
    )
