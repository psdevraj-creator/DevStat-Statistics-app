"""
DevStat AI — FastAPI Router

Endpoints for the LLM-powered AI Assistant. Mounted at /api/ai.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.ai.models import AnalysisPlan, SynthesizedAnswer, TestProposal, TestResult
from app.ai.parser import parse_goal
from app.ai.router import execute_plan
from app.ai.scanner import scan_dataset, build_data_dictionary, format_data_dictionary
from app.ai.synthesizer import synthesize_results
import app.state as _state

router = APIRouter(prefix="", tags=["AI Assistant"])

HISTORY_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_FILE = HISTORY_DIR / "ai_history.json"


# ── Helpers ──────────────────────────────────────────────────────────────

def _load_history() -> List[Dict[str, Any]]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_to_history(entry: Dict[str, Any]) -> None:
    history = _load_history()
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/ai/scan")
async def api_scan():
    """Scan the current dataset and return a data dictionary."""
    from app.ai.scanner import scan_dataset
    scan = scan_dataset()
    if scan is None:
        raise HTTPException(status_code=400, detail="No dataset is currently loaded.")
    return scan


@router.post("/ai/parse")
async def api_parse(body: Dict[str, Any]):
    """Parse a user question into an analysis plan."""
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="'question' is required.")

    scan = scan_dataset()
    if scan is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload a file first.")

    max_tests = body.get("max_tests", 5)
    plan = await parse_goal(question, max_tests=max_tests)

    return {
        "question": question,
        "plan": plan.model_dump(),
        "dataset": {
            "name": scan["name"],
            "rows": scan["rows"],
            "cols": scan["cols"],
        },
    }


@router.post("/ai/execute")
async def api_execute(body: Dict[str, Any]):
    """Execute a confirmed analysis plan."""
    plan_data = body.get("plan")
    if not plan_data:
        raise HTTPException(status_code=400, detail="'plan' is required.")

    plan = AnalysisPlan(**plan_data)
    auto_fallback = body.get("auto_fallback", True)

    results = await execute_plan(plan, auto_fallback=auto_fallback)

    return {
        "results": [r.model_dump() for r in results],
        "total": len(results),
        "success_count": sum(1 for r in results if r.status == "success"),
        "error_count": sum(1 for r in results if r.status == "error"),
    }


@router.post("/ai/synthesize")
async def api_synthesize(body: Dict[str, Any]):
    """Synthesize test results into a natural language answer."""
    question = body.get("question", "")
    results_data = body.get("results", [])

    if not results_data:
        raise HTTPException(status_code=400, detail="'results' is required.")

    results = [TestResult(**r) for r in results_data]
    answer = await synthesize_results(results, question)

    return answer.model_dump()


@router.post("/ai/analyze")
async def api_analyze(body: Dict[str, Any]):
    """Full pipeline: parse + execute + synthesize in one call."""
    try:
        question = body.get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="'question' is required.")

        scan = scan_dataset()
        if scan is None:
            raise HTTPException(status_code=400, detail="No dataset loaded.")

        max_tests = body.get("max_tests", 5)
        auto_fallback = body.get("auto_fallback", True)

        plan = await parse_goal(question, max_tests=max_tests)

        for t in plan.tests:
            t.user_confirmed = True

        results = await execute_plan(plan, auto_fallback=auto_fallback)

        answer = await synthesize_results(results, question)

        session_id = str(uuid.uuid4())[:8]
        _save_to_history({
            "id": session_id,
            "question": question,
            "plan_name": plan.plan_name,
            "timestamp": datetime.now().isoformat(),
            "test_count": len(results),
            "success_count": sum(1 for r in results if r.status == "success"),
            "summary": answer.summary,
        })

        return {
            "session_id": session_id,
            "question": question,
            "plan": plan.model_dump(),
            "results": [r.model_dump() for r in results],
            "answer": answer.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"ANALYZE ERROR: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"Analyze failed: {type(e).__name__}: {e}")


@router.get("/ai/history")
async def api_history(limit: int = 20):
    """Return past analysis sessions."""
    history = _load_history()
    return history[-limit:]


@router.get("/ai/history/{session_id}")
async def api_get_history(session_id: str):
    """Return a specific analysis session."""
    history = _load_history()
    for entry in history:
        if entry.get("id") == session_id:
            return entry
    raise HTTPException(status_code=404, detail="Session not found.")
