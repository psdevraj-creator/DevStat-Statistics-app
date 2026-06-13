"""
DevStat — Eligibility Router

Lightweight endpoints called on every variable dropdown change.
No calculation — just eligibility rules + chart suggestions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.eligibility import (
    check_chart_eligibility,
    check_descriptive_eligibility,
    check_ttest_eligibility,
    check_anova_eligibility,
    check_mannwhitney_eligibility,
    check_wilcoxon_eligibility,
    check_kruskal_eligibility,
    check_chi_square_eligibility,
    check_mcnemar_eligibility,
    check_regression_eligibility,
    check_logistic_eligibility,
    check_survival_eligibility,
    check_correlation_eligibility,
    check_reliability_eligibility,
    check_factor_eligibility,
    CHART_RULES,
)

router = APIRouter(prefix="/api/eligibility", tags=["Eligibility"])


class EligibilityRequest(BaseModel):
    analysis: str
    var_types: Dict[str, str] = {}
    n_groups: int = 0
    n_items: int = 0
    n_vars: int = 0
    n_rows: int = 0
    n_x_categories: int = 0
    n_y_categories: int = 0
    has_time: bool = False
    has_event: bool = False
    is_paired: bool = False
    is_survival: bool = False
    is_time_to_event: bool = False


class ChartSuggestionRequest(BaseModel):
    var_types: List[Dict[str, Any]]


CHART_NAMES = {
    "bar": "Bar Chart", "histogram": "Histogram", "scatter": "Scatter Plot",
    "boxplot": "Box Plot", "line": "Line Chart", "pie": "Pie Chart",
    "stacked_bar": "Stacked Bar Chart", "km": "Kaplan-Meier Curve",
    "violin": "Violin Plot", "strip": "Strip/Beeswarm Plot",
    "ecdf": "ECDF Plot", "qq": "Q-Q Plot", "hexbin": "Hexbin Plot",
    "pareto": "Pareto Chart", "cleveland_dot": "Cleveland Dot Plot",
    "lollipop": "Lollipop Chart", "dumbbell": "Dumbbell Plot",
    "splom": "Scatter Matrix", "control_chart": "Control Chart",
    "run_chart": "Run Chart", "gantt": "Gantt Chart",
    "calendar_heatmap": "Calendar Heatmap",
    "parallel_coordinates": "Parallel Coordinates", "radar": "Radar/Spider Chart",
    "treemap": "Treemap", "sankey": "Sankey Diagram",
    "waterfall": "Waterfall Chart", "funnel": "Funnel Plot",
    "bland_altman": "Bland-Altman Plot", "forest": "Forest Plot",
    "correlation_heatmap": "Correlation Heatmap", "swimmer": "Swimmer Plot",
    "volcano": "Volcano Plot", "ridgeline": "Ridgeline Plot",
    "bubble": "Bubble Chart", "calibration": "Calibration Plot",
    "pca": "PCA Scatter", "correlation_network": "Correlation Network",
    "monthly_trend": "Monthly Trend Heatmap", "adverse_event_heatmap": "Adverse Event Heatmap",
}


@router.post("/check")
async def eligibility_check(req: EligibilityRequest) -> Dict[str, Any]:
    """Check if an analysis/chart is valid for given variable types."""
    vt = req.var_types

    if req.analysis.startswith("chart_"):
        chart_type = req.analysis.replace("chart_", "")
        return check_chart_eligibility(
            chart_type=chart_type,
            x_type=vt.get("x", "continuous"),
            y_type=vt.get("y", "continuous"),
            n_x_categories=req.n_x_categories,
            n_y_categories=req.n_y_categories,
            has_time=req.has_time,
            has_event=req.has_event,
            n_rows=req.n_rows,
            has_paired=req.is_paired,
        )

    checks = {
        "ttest": lambda: check_ttest_eligibility(req.n_groups, req.is_paired, vt.get("dependent", "continuous")),
        "ttest_paired": lambda: check_paired_ttest_eligibility(req.is_paired, vt.get("dependent", "continuous")),
        "anova": lambda: check_anova_eligibility(req.n_groups, vt.get("dependent", "continuous"), req.is_paired),
        "mannwhitney": lambda: check_mannwhitney_eligibility(req.n_groups, req.is_paired, vt.get("dependent", "continuous")),
        "wilcoxon": lambda: check_wilcoxon_eligibility(req.is_paired, vt.get("dependent", "continuous")),
        "kruskal": lambda: check_kruskal_eligibility(req.n_groups, req.is_paired),
        "chisquare": lambda: check_chi_square_eligibility(vt.get("dependent", "nominal")),
        "mcnemar": lambda: check_mcnemar_eligibility(req.is_paired, vt.get("dependent", "binary")),
        "linear_regression": lambda: check_regression_eligibility(vt.get("dependent", "continuous"), req.is_survival, req.is_time_to_event),
        "logistic_regression": lambda: check_logistic_eligibility(vt.get("dependent", "binary")),
        "survival": lambda: check_survival_eligibility(req.has_event, req.has_time),
        "correlation": lambda: check_correlation_eligibility([vt.get(k, "continuous") for k in vt]),
        "reliability": lambda: check_reliability_eligibility(req.n_items),
        "factor": lambda: check_factor_eligibility(req.n_vars),
    }

    check = checks.get(req.analysis)
    if not check:
        return {"eligible": True, "blocked": False}
    return check()


@router.post("/suggest-charts")
async def suggest_charts(req: ChartSuggestionRequest) -> List[Dict[str, Any]]:
    """Rank chart types by how well they fit the selected variables."""
    var_types = {v.get("role", "x"): v.get("type", "continuous") for v in req.var_types}
    x_type = var_types.get("x", "continuous")
    y_type = var_types.get("y", "continuous")
    n_vars = len(req.var_types)

    scored = []
    for chart_id, rule in CHART_RULES.items():
        score = 0
        allowed_x = rule.get("x_types", [])
        allowed_y = rule.get("y_types", [])
        min_cols = rule.get("min_columns", 0)

        if x_type in allowed_x:
            score += 2
        if not allowed_y or y_type in allowed_y:
            score += 2
        if n_vars >= min_cols:
            score += 1

        if score > 0:
            scored.append({
                "chart": chart_id,
                "name": CHART_NAMES.get(chart_id, chart_id),
                "score": score,
                "eligible": check_chart_eligibility(
                    chart_id, x_type=x_type, y_type=y_type,
                ).get("eligible", False),
            })

    scored.sort(key=lambda c: (c["eligible"], c["score"]), reverse=True)
    return scored
