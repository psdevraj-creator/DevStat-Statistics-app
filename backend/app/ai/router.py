"""Action Router — executes a confirmed AnalysisPlan using DevStat's internal services."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import app.state as _state
from app.ai.models import AnalysisPlan, TestResult
from app.routers import analysis as analysis_router
from app.services.compare import (
    mannwhitney as py_mannwhitney,
    ttest as py_ttest,
)
from app.services.descriptive import descriptive_stats, frequencies as py_frequencies
from app.services.charts import (
    bar_chart_data,
    boxplot_data,
    histogram_data,
    scatter_data,
)

TEST_CHART_MAP: Dict[str, List[Dict[str, Any]]] = {
    "independent_ttest": [
        {"type": "boxplot", "chart_fn": boxplot_data, "key_map": {"column": "dependent_0", "group_col": "group"}},
        {"type": "histogram", "chart_fn": histogram_data, "key_map": {"column": "dependent_0", "group_col": "group"}},
    ],
    "paired_ttest": [
        {"type": "boxplot", "chart_fn": boxplot_data, "key_map": {"column": "dependent_0"}},
    ],
    "oneway_anova": [
        {"type": "boxplot", "chart_fn": boxplot_data, "key_map": {"column": "dependent_0", "group_col": "group"}},
    ],
    "mannwhitney": [
        {"type": "boxplot", "chart_fn": boxplot_data, "key_map": {"column": "dependent", "group_col": "group"}},
    ],
    "chisquare": [
        {"type": "bar", "chart_fn": bar_chart_data, "key_map": {"category_col": "row"}},
    ],
    "fisher_exact": [
        {"type": "bar", "chart_fn": bar_chart_data, "key_map": {"category_col": "row"}},
    ],
    "pearson": [
        {"type": "scatter", "chart_fn": scatter_data, "key_map": {"x_col": "columns_0", "y_col": "columns_1"}},
    ],
    "spearman": [
        {"type": "scatter", "chart_fn": scatter_data, "key_map": {"x_col": "columns_0", "y_col": "columns_1"}},
    ],
    "linear_regression": [
        {"type": "scatter", "chart_fn": scatter_data, "key_map": {"x_col": "independents_0", "y_col": "dependent"}},
    ],
    "descriptive": [
        {"type": "histogram", "chart_fn": histogram_data, "key_map": {"column": "columns_0"}},
    ],
    "frequencies": [
        {"type": "bar", "chart_fn": bar_chart_data, "key_map": {"category_col": "column"}},
    ],
}

FALLBACK_ENDPOINT_MAP = {
    "mannwhitney": "mannwhitney",
    "wilcoxon": "wilcoxon",
    "kruskalwallis": "kruskalwallis",
    "fisher_exact": "fisher_exact",
    "spearman": "spearman",
}

FALLBACK_NAME_MAP = {
    "mannwhitney": "Mann-Whitney U test",
    "wilcoxon": "Wilcoxon signed-rank test",
    "kruskalwallis": "Kruskal-Wallis test",
    "fisher_exact": "Fisher's exact test",
    "spearman": "Spearman rank correlation",
}


async def execute_plan(plan: AnalysisPlan, auto_fallback: bool = True) -> List[TestResult]:
    """Run all confirmed tests using DevStat's internal services."""
    results = []

    for test in plan.tests:
        if not test.user_confirmed:
            continue

        result = TestResult(
            test_id=test.id,
            test_name=test.test_name,
            status="success",
            endpoint=test.endpoint,
            payload=test.payload,
        )

        try:
            response = await _run_single_test(test)
            if "error" in response and test.fallback_test and auto_fallback:
                result.used_fallback = True
                result.fallback_reason = f"Primary failed: {response.get('error')}. Using fallback: {test.fallback_test}"
                response = await _run_fallback(test)
                if response:
                    result.endpoint = f"/api/analysis/np-{test.fallback_test}"
                    result.test_name = FALLBACK_NAME_MAP.get(test.fallback_test, test.fallback_test)

            if "error" in response:
                result.status = "error"
                result.error = response["error"]
            else:
                result.response = response

            result.charts = await _fetch_charts(test.test, test.payload)

        except Exception as e:
            result.status = "error"
            result.error = str(e)

        results.append(result)

    return results


async def _run_single_test(test) -> Dict[str, Any]:
    """Run a single test by dispatching to the correct service."""
    df = _state.current_data
    if df is None:
        return {"error": "No dataset loaded"}

    t = test.test

    if t == "independent_ttest":
        dep = _get_payload_val(test.payload, "dependent_0")
        grp = test.payload.get("group")
        if dep and grp:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, py_ttest, df, dep, grp, False)
        return {"error": "Missing dependent or group variable"}

    if t == "mannwhitney":
        dep = test.payload.get("dependent")
        grp = test.payload.get("group")
        if dep and grp:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, py_mannwhitney, df, dep, grp)
        return {"error": "Missing dependent or group variable"}

    if t == "descriptive":
        cols = test.payload.get("columns") or [test.payload.get("column")]
        if cols:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, descriptive_stats, df, cols)
        return {"error": "Missing column"}

    if t == "frequencies":
        col = test.payload.get("column")
        if col:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, py_frequencies, df, col)
        return {"error": "Missing column"}

    return {"error": f"Test '{t}' execution not yet implemented in AI router. Use the standard DevStat page for this test."}


async def _run_fallback(test) -> Optional[Dict[str, Any]]:
    """Run fallback test."""
    ft = test.fallback_test
    if not ft:
        return None

    df = _state.current_data
    if df is None:
        return None

    loop = asyncio.get_event_loop()

    if ft == "mannwhitney":
        dep = test.payload.get("dependent") or _get_payload_val(test.payload, "dependent_0")
        grp = test.payload.get("group")
        if dep and grp:
            return await loop.run_in_executor(None, py_mannwhitney, df, dep, grp)

    if ft == "wilcoxon":
        from app.services.compare import wilcoxon
        v1 = test.payload.get("variable1") or _get_payload_val(test.payload, "dependent_0")
        v2 = test.payload.get("variable2") or _get_payload_val(test.payload, "dependent_1")
        if v1 and v2:
            return await loop.run_in_executor(None, wilcoxon, df, v1, v2)

    return None


async def _fetch_charts(test_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch chart data based on test type."""
    chart_defs = TEST_CHART_MAP.get(test_type, [])
    charts = []
    df = _state.current_data
    if df is None:
        return charts

    for cd in chart_defs:
        chart_payload = _build_chart_payload(cd["key_map"], payload)
        if not chart_payload.get("column") and not chart_payload.get("x_col") and not chart_payload.get("category_col"):
            continue
        try:
            loop = asyncio.get_event_loop()
            fn = cd["chart_fn"]
            fn_kwargs = {k: v for k, v in chart_payload.items() if v is not None}
            data = await loop.run_in_executor(None, lambda: fn(df, **fn_kwargs))
            charts.append({"type": cd["type"], "title": f"{test_type} — {cd['type']}", "data": data})
        except Exception as e:
            charts.append({"type": cd["type"], "title": f"{test_type} — {cd['type']}", "data": {"error": str(e)}})

    return charts


def _build_chart_payload(key_map: Dict[str, str], test_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = {}
    for chart_key, test_key in key_map.items():
        parts = test_key.split("_")
        if len(parts) == 2 and parts[1].isdigit():
            arr = test_payload.get(parts[0])
            if isinstance(arr, list) and len(arr) > int(parts[1]):
                payload[chart_key] = arr[int(parts[1])]
            else:
                payload[chart_key] = None
        else:
            payload[chart_key] = test_payload.get(test_key)
    return payload


def _get_payload_val(payload: Dict[str, Any], key: str):
    if key in payload:
        return payload[key]
    parts = key.split("_")
    if len(parts) == 2 and parts[1].isdigit():
        arr = payload.get(parts[0])
        if isinstance(arr, list) and len(arr) > int(parts[1]):
            return arr[int(parts[1])]
    return None
