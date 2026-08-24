"""Pydantic models for the AI Assistant — analysis plans, proposals, and results."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChartProposal(BaseModel):
    type: str
    title: str = ""
    endpoint: str
    payload: Dict[str, Any]


class TestProposal(BaseModel):
    id: str
    test: str
    test_name: str
    rationale: str
    endpoint: str
    payload: Dict[str, Any]
    charts: List[ChartProposal] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    fallback_test: Optional[str] = None
    user_confirmed: bool = False
    user_removed: bool = False


class DataTransform(BaseModel):
    type: str
    description: str
    endpoint: str
    payload: Dict[str, Any]


class AnalysisPlan(BaseModel):
    plan_name: str
    tests: List[TestProposal]
    notes: str = ""
    data_transforms: List[DataTransform] = Field(default_factory=list)


class TestResult(BaseModel):
    test_id: str
    test_name: str
    status: str
    endpoint: str
    payload: Dict[str, Any]
    response: Dict[str, Any] = Field(default_factory=dict)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    used_fallback: bool = False
    fallback_reason: str = ""


class SynthesizedAnswer(BaseModel):
    summary: str
    detailed_results: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: str = ""
    conclusion: str = ""
