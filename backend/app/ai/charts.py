"""Chart Derivation — maps test types to DevStat chart endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from app.ai.models import ChartProposal


DEFAULT_CHARTS: Dict[str, List[ChartProposal]] = {
    "independent_ttest": [
        ChartProposal(type="boxplot", title="Boxplot by Group", endpoint="/api/charts/boxplot", payload={}),
        ChartProposal(type="histogram", title="Histogram by Group", endpoint="/api/charts/histogram", payload={}),
    ],
    "paired_ttest": [
        ChartProposal(type="boxplot", title="Paired Boxplot", endpoint="/api/charts/boxplot", payload={}),
    ],
    "oneway_anova": [
        ChartProposal(type="boxplot", title="Boxplot by Group", endpoint="/api/charts/boxplot", payload={}),
    ],
    "mannwhitney": [
        ChartProposal(type="boxplot", title="Boxplot by Group", endpoint="/api/charts/boxplot", payload={}),
    ],
    "chisquare": [
        ChartProposal(type="bar", title="Grouped Bar Chart", endpoint="/api/charts/bar", payload={}),
    ],
    "fisher_exact": [
        ChartProposal(type="bar", title="Grouped Bar Chart", endpoint="/api/charts/bar", payload={}),
    ],
    "pearson": [
        ChartProposal(type="scatter", title="Scatter Plot", endpoint="/api/charts/scatter", payload={}),
    ],
    "spearman": [
        ChartProposal(type="scatter", title="Scatter Plot", endpoint="/api/charts/scatter", payload={}),
    ],
    "linear_regression": [
        ChartProposal(type="scatter", title="Scatter with Regression", endpoint="/api/charts/scatter", payload={}),
    ],
    "logistic_regression": [
        ChartProposal(type="bar", title="Predicted Probabilities", endpoint="/api/charts/bar", payload={}),
    ],
    "kaplan_meier": [
        ChartProposal(type="km_curve", title="Kaplan-Meier Curve", endpoint="/api/charts/km-curve", payload={}),
    ],
    "cox_regression": [
        ChartProposal(type="km_curve", title="Kaplan-Meier Curve", endpoint="/api/charts/km-curve", payload={}),
    ],
    "diagnostic_test": [
        ChartProposal(type="roc_curve", title="ROC Curve", endpoint="/api/charts/roc-curve", payload={}),
    ],
    "descriptive": [
        ChartProposal(type="histogram", title="Histogram", endpoint="/api/charts/histogram", payload={}),
    ],
    "frequencies": [
        ChartProposal(type="bar", title="Frequency Bar Chart", endpoint="/api/charts/bar", payload={}),
    ],
}


def get_default_charts(test_type: str) -> List[ChartProposal]:
    return DEFAULT_CHARTS.get(test_type, [])


def suggest_charts(test_type: str, payload: Dict[str, Any]) -> List[ChartProposal]:
    """Return chart proposals with payload filled in based on test payload."""
    charts = get_default_charts(test_type)
    filled = []
    for chart in charts:
        p = _build_payload(chart.type, payload)
        filled.append(ChartProposal(type=chart.type, title=chart.title, endpoint=chart.endpoint, payload=p))
    return filled


def _build_payload(chart_type: str, test_payload: Dict[str, Any]) -> Dict[str, Any]:
    if chart_type == "boxplot":
        for key in ("dependent_0", "dependent", "column", "outcome"):
            col = _get_val(test_payload, key)
            if col:
                return {"column": col, "group_col": test_payload.get("group") or test_payload.get("group_var")}
        return {}

    if chart_type == "histogram":
        for key in ("dependent_0", "dependent", "column", "outcome"):
            col = _get_val(test_payload, key)
            if col:
                return {"column": col, "group_col": test_payload.get("group")}
        return {}

    if chart_type == "scatter":
        x = test_payload.get("x_col") or _get_val(test_payload, "columns_0")
        y = test_payload.get("y_col") or _get_val(test_payload, "columns_1") or test_payload.get("dependent") or _get_val(test_payload, "dv")
        if x and y:
            return {"x_col": x, "y_col": y}
        return {}

    if chart_type == "bar":
        cat = test_payload.get("category_col") or test_payload.get("row") or test_payload.get("column")
        val = test_payload.get("value_col") or test_payload.get("col")
        p: Dict[str, Any] = {"category_col": cat}
        if val:
            p["value_col"] = val
        return p

    if chart_type == "km_curve":
        return {
            "time_col": test_payload.get("time_col", ""),
            "status_col": test_payload.get("status_col", ""),
            "group_col": test_payload.get("group_col") or (test_payload.get("factors", [None])[0] if test_payload.get("factors") else None),
        }

    if chart_type == "roc_curve":
        return {
            "test_col": test_payload.get("test_col", ""),
            "gold_col": test_payload.get("gold_col", ""),
        }

    return {}


def _get_val(payload: Dict[str, Any], key: str):
    if key in payload:
        return payload[key]
    parts = key.split("_")
    if len(parts) == 2 and parts[1].isdigit():
        arr = payload.get(parts[0])
        if isinstance(arr, list) and len(arr) > int(parts[1]):
            return arr[int(parts[1])]
    return None
