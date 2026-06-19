"""Suggest-Test router — mounted at /api/analysis."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

import app.state as _state
from app.state import require_data
from app.models.suggest import SuggestTestRequest, SuggestTestResponse
from app.services.suggest import recommend_test
from app.services.validate_test import validate_test_choice, TEST_CONTRACTS

router = APIRouter(prefix="", tags=["Suggest Test"])


_require_data = require_data


@router.post("/suggest-test", response_model=SuggestTestResponse)
async def suggest_test(req: SuggestTestRequest) -> Dict[str, Any]:
    """Recommend a statistical test based on the research goal and data."""
    _require_data()
    if not req.goal:
        raise HTTPException(status_code=400, detail="'goal' is required.")
    result = recommend_test(_state.current_data, req)
    return result.model_dump()


@router.post("/validate-test")
async def validate_test(body: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a user-chosen test against its input contract.

    Request body::

        {
          "test_id": "independent_ttest",
          "outcome_variable": "age",
          "group_variable": "group",
          "predictor_variables": [],
          "time_variable": null,
          "event_variable": null,
          "outcome_type": "continuous",
          "group_type": "categorical",
          "paired": false,
          "num_groups": 2,
          "override_reason": "I want a non-parametric test because the data is skewed"
        }

    Returns a 3-tier safety result:
      - compatible  → test can run normally
      - soft        → warning, allow continue
      - interrupt   → requires override_reason
      - hard        → fundamentally incompatible, must fix

    If the tier is ``interrupt`` and no ``override_reason`` is provided,
    returns HTTP 400 with a clear explanation.
    """
    test_id = body.get("test_id", "")
    if not test_id:
        raise HTTPException(status_code=400, detail="'test_id' is required.")

    result = validate_test_choice(
        test_id=test_id,
        outcome_variable=body.get("outcome_variable"),
        group_variable=body.get("group_variable"),
        predictor_variables=body.get("predictor_variables", []),
        time_variable=body.get("time_variable"),
        event_variable=body.get("event_variable"),
        outcome_type=body.get("outcome_type", "unknown"),
        group_type=body.get("group_type", "unknown"),
        paired=body.get("paired", False),
        num_groups=body.get("num_groups", 0),
    )

    # Require override reason for interrupt tier
    if result["tier"] == "interrupt":
        reason = (body.get("override_reason") or "").strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot proceed: {result['message']} "
                    "Please provide an 'override_reason' explaining why you are "
                    "choosing this test despite the compatibility warning."
                ),
            )
        result["override_reason"] = reason

    return result


@router.get("/available-tests")
async def available_tests() -> Dict[str, Any]:
    """Return all supported tests with their input contracts."""
    return {"tests": TEST_CONTRACTS}
