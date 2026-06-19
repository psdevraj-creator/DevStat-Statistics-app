"""DevStat — Wizard Query Router

Deterministic help wizard that guides users to the correct statistical test.
Uses WizardEngine (no LLM).  State is passed round-trip with the client.

Mounted at ``/api/wizard`` in the main FastAPI application.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.wizard import WizardEngine

router = APIRouter()

# ── Request / Response models ─────────────────────────────────────────

class WizardQueryRequest(BaseModel):
    text: str
    state: Optional[Dict[str, Any]] = None


class WizardRecommendation(BaseModel):
    test_name: str
    alternative: str
    graphs: list[str]
    assumptions: list[str]
    module: str
    explanation: str
    prefill_params: Dict[str, Any]


class WizardQueryResponse(BaseModel):
    response: Dict[str, Any]
    state: Dict[str, Any]
    recommendation: Optional[WizardRecommendation] = None


# ── Singleton engine ─────────────────────────────────────────────────

_engine: Optional[WizardEngine] = None


def _get_engine() -> WizardEngine:
    """Lazy-initialised singleton WizardEngine."""
    global _engine
    if _engine is None:
        _engine = WizardEngine()
    return _engine


# ── Endpoint ─────────────────────────────────────────────────────────

@router.post("/query", response_model=WizardQueryResponse)
async def wizard_query(payload: WizardQueryRequest) -> Dict[str, Any]:
    """Process a wizard query and return the next step or recommendation.

    The client holds the *state* and passes it back on every call.
    On the first call (no state), the engine starts from the root question.

    Returns:
        - **response**: next question dict or final result dict.
        - **state**:    updated wizard state (send this back next time).
        - **recommendation**: full recommendation (only when a leaf is reached).
    """
    engine = _get_engine()

    # Default initial state
    state: Dict[str, Any] = (
        payload.state
        if payload.state is not None
        else {"current_node": "what_analysis", "answers": {}}
    )

    result = engine.process_input(payload.text, state)

    return {
        "response": result["response"],
        "state": result["state"],
        "recommendation": result.get("recommendation"),
    }


@router.get("/reset")
async def wizard_reset() -> Dict[str, Any]:
    """Reset the wizard engine (re-initialise singleton).

    Returns a fresh initial state.
    """
    global _engine
    _engine = WizardEngine()
    return {
        "state": {"current_node": "what_analysis", "answers": {}},
        "message": "Wizard reset successfully.",
    }
