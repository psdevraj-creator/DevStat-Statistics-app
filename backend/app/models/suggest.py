"""
Pydantic models for the /api/analysis/suggest-test endpoint.

These define the request shape (what the wizard sends) and the response
shape (what the frontend receives to render the recommendation card).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ── Enums used across models ───────────────────────────────────────────

AnalysisGoal = Literal[
    "compare_groups",
    "test_association",
    "model_predict",
    "survival_analysis",
    "correlation",
]

VariableType = Literal[
    "continuous",
    "binary",
    "categorical",
    "ordinal",
    "survival_time",
    "event_indicator",
    "unknown",
]


# ── Request ────────────────────────────────────────────────────────────

class VariableInfo(BaseModel):
    """A column the user selected, with auto-inferred type and optional override."""
    column: str
    inferred_type: VariableType = "unknown"
    override_type: Optional[VariableType] = None

    @property
    def effective_type(self) -> VariableType:
        return self.override_type or self.inferred_type


class SuggestTestRequest(BaseModel):
    """Wizard payload sent by the frontend."""
    goal: AnalysisGoal
    outcome_variable: Optional[str] = None
    predictor_variables: List[str] = Field(default_factory=list)
    group_variable: Optional[str] = None
    time_variable: Optional[str] = None
    event_variable: Optional[str] = None
    event_code: int = 1
    paired: bool = False
    num_groups: Optional[int] = None
    variables: List[VariableInfo] = Field(default_factory=list)


# ── Response ───────────────────────────────────────────────────────────

class AssumptionInfo(BaseModel):
    """Summary of one assumption check."""
    name: str
    passed: Optional[bool] = None       # None = could not check
    detail: str = ""
    warning: Optional[str] = None


class TestRecommendation(BaseModel):
    """A single recommended test with rationale."""
    test_id: str
    test_name: str
    is_fallback: bool = False
    rationale: str = ""
    assumptions: List[AssumptionInfo] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Payload ready to POST to the analysis endpoint
    analysis_payload: Dict[str, Any] = Field(default_factory=dict)
    analysis_endpoint: str = ""


class SuggestTestResponse(BaseModel):
    """Full wizard recommendation response."""
    goal: AnalysisGoal
    outcome_type: VariableType = "unknown"
    predictor_type: VariableType = "unknown"
    paired: bool = False
    num_groups: Optional[int] = None
    primary: TestRecommendation
    fallback: Optional[TestRecommendation] = None
    warnings: List[str] = Field(default_factory=list)
