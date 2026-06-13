"""
DevStat — Charts Router

Endpoints that return JSON-serialisable chart data structures for the
front-end charting library.  All endpoints operate on the dataset
currently held in memory (``app.main._state.current_data``).

Mounted at ``/api/charts`` in the main FastAPI application.
"""

from __future__ import annotations

import base64
import io
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi import APIRouter, HTTPException

import app.state as _state
from app.state import require_data
from app.services.charts import (
    bar_chart_data,
    boxplot_data,
    histogram_data,
    km_curve_data,
    roc_curve_data,
    scatter_data,
    violin_plot_data, strip_plot_data, ecdf_plot_data, qq_plot_data, hexbin_plot_data,
    pareto_chart_data, cleveland_dot_plot_data, lollipop_chart_data, dumbbell_plot_data, splom_plot_data,
    control_chart_data, run_chart_data, gantt_chart_data, calendar_heatmap_data,
    parallel_coordinates_data, radar_chart_data, treemap_data, sankey_diagram_data,
    waterfall_chart_data,     funnel_plot_data, bland_altman_plot_data, forest_plot_data,
    correlation_heatmap_data, swimmer_plot_data, volcano_plot_data,
    ridgeline_plot_data, bubble_chart_data, calibration_plot_data,
    pca_scatter_data, correlation_network_data, monthly_trend_heatmap_data,
    adverse_event_heatmap_data,
)
from app.services.diagnostic import roc_analysis
from app.services.survival import kaplan_meier
from app.models.dataset import ChartResponse

router = APIRouter(prefix="", tags=["Charts"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


_require_data = require_data


# ---------------------------------------------------------------------------
# Basic charts
# ---------------------------------------------------------------------------


@router.post("/histogram", response_model=ChartResponse)
async def histogram(
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare histogram chart data for a numeric column.

    Request body:
        - ``column`` (str, required)
        - ``bins`` (str or int, optional, default ``\"auto\"``)
        - ``group_col`` (str, optional)
    """
    _require_data()
    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")

    bins = body.get("bins", "auto")
    group_col: Optional[str] = body.get("group_col")

    return histogram_data(_state.current_data, column=column, bins=bins, group_col=group_col)


@router.post("/boxplot", response_model=ChartResponse)
async def boxplot(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare boxplot chart data for a numeric column.

    Request body:
        - ``column`` (str, required)
        - ``group_col`` (str, optional)
    """
    _require_data()
    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")

    group_col: Optional[str] = body.get("group_col")

    return boxplot_data(_state.current_data, column=column, group_col=group_col)


@router.post("/scatter", response_model=ChartResponse)
async def scatter(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare scatter plot chart data with regression line.

    Request body:
        - ``x_col`` (str, required)
        - ``y_col`` (str, required)
        - ``group_col`` (str, optional)
    """
    _require_data()
    x_col = body.get("x_col")
    y_col = body.get("y_col")
    if not x_col or not y_col:
        raise HTTPException(
            status_code=400, detail="Both 'x_col' and 'y_col' are required."
        )

    group_col: Optional[str] = body.get("group_col")

    return scatter_data(
        _state.current_data, x_col=x_col, y_col=y_col, group_col=group_col
    )


@router.post("/bar", response_model=ChartResponse)
async def bar(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare bar chart data.

    Request body:
        - ``category_col`` (str, required) — x-axis categories
        - ``value_col`` (str, optional) — numeric column to aggregate; if
          omitted, category counts are used.
        - ``error_bars`` (str, optional) — ``\"sd\"`` (default), ``\"se\"``,
          ``\"ci95\"``, or ``\"none\"``.
    """
    _require_data()
    category_col = body.get("category_col")
    if not category_col:
        raise HTTPException(
            status_code=400, detail="'category_col' is required."
        )

    value_col: Optional[str] = body.get("value_col")
    error_bars: str = body.get("error_bars", "sd")

    return bar_chart_data(
        _state.current_data,
        category_col=category_col,
        value_col=value_col,
        error_bars=error_bars,
    )


# ---------------------------------------------------------------------------
# Composite charts (run analysis internally)
# ---------------------------------------------------------------------------


@router.post("/km-curve")
async def km_curve(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare Kaplan-Meier curve chart data.

    Runs ``kaplan_meier()`` internally and transforms the result into
    plot-ready coordinates.

    Request body:
        - ``time_col`` (str, required)
        - ``status_col`` (str, required)
        - ``event_code`` (int, optional, default ``1``)
        - ``group_col`` (str, optional)
    """
    _require_data()
    time_col = body.get("time_col")
    status_col = body.get("status_col")
    if not time_col or not status_col:
        raise HTTPException(
            status_code=400,
            detail="Both 'time_col' and 'status_col' are required.",
        )

    event_code: int = body.get("event_code", 1)
    group_col: Optional[str] = body.get("group_col")

    km_result = kaplan_meier(
        _state.current_data,
        time_col=time_col,
        status_col=status_col,
        event_code=event_code,
        group_col=group_col,
    )

    return km_curve_data(km_result)


@router.post("/roc-curve")
async def roc_curve(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare ROC curve chart data.

    Runs ``roc_analysis()`` internally and transforms the result into
    plot-ready coordinates.

    Request body:
        - ``test_col`` (str, required)
        - ``gold_col`` (str, required)
        - ``positive_code`` (optional, default ``1``)
    """
    _require_data()
    test_col = body.get("test_col")
    gold_col = body.get("gold_col")
    if not test_col or not gold_col:
        raise HTTPException(
            status_code=400,
            detail="Both 'test_col' and 'gold_col' are required.",
        )

    positive_code = body.get("positive_code", 1)

    roc_result = roc_analysis(
        _state.current_data,
        test_col=test_col,
        gold_col=gold_col,
        positive_code=positive_code,
    )

    return roc_curve_data(roc_result)


# ═══════════════════════════════════════════════════════════════════════════
# Batch 1 — Distribution chart endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/violin")
async def violin_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    """Violin plot — distribution of a numeric variable across groups."""
    _require_data()
    column = body.get("column")
    group_col = body.get("group_col")
    if not column:
        raise HTTPException(400, detail="'column' is required.")
    if column not in _state.current_data.columns:
        raise HTTPException(400, detail=f"Column '{column}' not found.")
    return violin_plot_data(_state.current_data, column, group_col)


@router.post("/strip")
async def strip_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    """Strip/beeswarm plot — individual data points across groups."""
    _require_data()
    column = body.get("column")
    group_col = body.get("group_col")
    if not column:
        raise HTTPException(400, detail="'column' is required.")
    return strip_plot_data(_state.current_data, column, group_col)


@router.post("/ecdf")
async def ecdf_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    """ECDF — empirical cumulative distribution function."""
    _require_data()
    column = body.get("column")
    group_col = body.get("group_col")
    if not column:
        raise HTTPException(400, detail="'column' is required.")
    return ecdf_plot_data(_state.current_data, column, group_col)


@router.post("/qq")
async def qq_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    """Q-Q plot — compare distribution to a theoretical one."""
    _require_data()
    column = body.get("column")
    dist = body.get("dist", "norm")
    if not column:
        raise HTTPException(400, detail="'column' is required.")
    return qq_plot_data(_state.current_data, column, dist)


@router.post("/hexbin")
async def hexbin_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    """Hexbin plot — 2D density for large datasets."""
    _require_data()
    x_col = body.get("x_col") or body.get("x")
    y_col = body.get("y_col") or body.get("y")
    if not x_col or not y_col:
        raise HTTPException(400, detail="'x_col' and 'y_col' are required.")
    return hexbin_plot_data(_state.current_data, x_col, y_col)


# ═══════════════════════════════════════════════════════════════════════════
# Batch 2 — Comparison chart endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/pareto")
async def pareto_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    val = body.get("value_col") or body.get("value")
    if not cat or not val:
        raise HTTPException(400, detail="'category_col' and 'value_col' are required.")
    return pareto_chart_data(_state.current_data, cat, val)


@router.post("/cleveland-dot")
async def cleveland_dot_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    val = body.get("value_col") or body.get("value")
    if not cat or not val:
        raise HTTPException(400, detail="'category_col' and 'value_col' are required.")
    return cleveland_dot_plot_data(_state.current_data, cat, val)


@router.post("/lollipop")
async def lollipop_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    val = body.get("value_col") or body.get("value")
    if not cat or not val:
        raise HTTPException(400, detail="'category_col' and 'value_col' are required.")
    return lollipop_chart_data(_state.current_data, cat, val)


@router.post("/dumbbell")
async def dumbbell_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col")
    pre = body.get("pre_col") or body.get("pre")
    post = body.get("post_col") or body.get("post")
    if not cat or not pre or not post:
        raise HTTPException(400, detail="'category_col', 'pre_col', and 'post_col' are required.")
    return dumbbell_plot_data(_state.current_data, cat, pre, post)


@router.post("/splom")
async def splom_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cols = body.get("columns", [])
    group = body.get("group_col")
    if len(cols) < 3:
        raise HTTPException(400, detail="SPLOM requires at least 3 columns.")
    return splom_plot_data(_state.current_data, cols, group)


# ═══════════════════════════════════════════════════════════════════════════
# Batch 3 — Time / process chart endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/control-chart")
async def control_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    val = body.get("value_col") or body.get("value")
    time = body.get("time_col")
    if not val:
        raise HTTPException(400, detail="'value_col' is required.")
    return control_chart_data(_state.current_data, val, time)


@router.post("/run-chart")
async def run_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    val = body.get("value_col") or body.get("value")
    time = body.get("time_col")
    if not val:
        raise HTTPException(400, detail="'value_col' is required.")
    return run_chart_data(_state.current_data, val, time)


@router.post("/gantt")
async def gantt_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    task = body.get("task_col") or body.get("task")
    start = body.get("start_col") or body.get("start")
    end = body.get("end_col") or body.get("end")
    if not task or not start or not end:
        raise HTTPException(400, detail="'task_col', 'start_col', and 'end_col' are required.")
    return gantt_chart_data(_state.current_data, task, start, end)


@router.post("/calendar-heatmap")
async def calendar_heatmap(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    date = body.get("date_col") or body.get("date")
    val = body.get("value_col") or body.get("value")
    if not date or not val:
        raise HTTPException(400, detail="'date_col' and 'value_col' are required.")
    return calendar_heatmap_data(_state.current_data, date, val)


# ═══════════════════════════════════════════════════════════════════════════
# Batch 4 — Specialized chart endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/parallel-coordinates")
async def parallel_coordinates_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cols = body.get("columns", [])
    color = body.get("color_col")
    if len(cols) < 3:
        raise HTTPException(400, detail="Parallel coordinates requires at least 3 columns.")
    return parallel_coordinates_data(_state.current_data, cols, color)


@router.post("/radar")
async def radar_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    vals = body.get("value_cols", [])
    if not cat or len(vals) < 3:
        raise HTTPException(400, detail="'category_col' and at least 3 'value_cols' are required.")
    return radar_chart_data(_state.current_data, cat, vals)


@router.post("/treemap")
async def treemap_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    val = body.get("value_col") or body.get("value")
    parent = body.get("parent_col")
    if not cat or not val:
        raise HTTPException(400, detail="'category_col' and 'value_col' are required.")
    return treemap_data(_state.current_data, cat, val, parent)


@router.post("/sankey")
async def sankey_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    src = body.get("source_col") or body.get("source")
    tgt = body.get("target_col") or body.get("target")
    val = body.get("value_col") or body.get("value")
    if not src or not tgt:
        raise HTTPException(400, detail="'source_col' and 'target_col' are required.")
    return sankey_diagram_data(_state.current_data, src, tgt, val)


@router.post("/waterfall")
async def waterfall_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cat = body.get("category_col") or body.get("category")
    val = body.get("value_col") or body.get("value")
    if not cat or not val:
        raise HTTPException(400, detail="'category_col' and 'value_col' are required.")
    return waterfall_chart_data(_state.current_data, cat, val)


@router.post("/funnel")
async def funnel_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    effect = body.get("effect_col") or body.get("effect")
    precision = body.get("precision_col") or body.get("precision")
    if not effect or not precision:
        raise HTTPException(400, detail="'effect_col' and 'precision_col' are required.")
    return funnel_plot_data(_state.current_data, effect, precision)


@router.post("/bland-altman")
async def bland_altman_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    c1 = body.get("col1") or body.get("measurement1")
    c2 = body.get("col2") or body.get("measurement2")
    if not c1 or not c2:
        raise HTTPException(400, detail="'col1' and 'col2' are required.")
    return bland_altman_plot_data(_state.current_data, c1, c2)


@router.post("/forest")
async def forest_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    label = body.get("label_col") or body.get("label")
    est = body.get("estimate_col") or body.get("estimate")
    lo = body.get("ci_lower_col") or body.get("ci_lower")
    hi = body.get("ci_upper_col") or body.get("ci_upper")
    if not label or not est or not lo or not hi:
        raise HTTPException(400, detail="'label_col', 'estimate_col', 'ci_lower_col', 'ci_upper_col' are required.")
    return forest_plot_data(_state.current_data, label, est, lo, hi)


@router.post("/correlation-heatmap")
async def correlation_heatmap(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cols = body.get("columns", [])
    method = body.get("method", "pearson")
    if len(cols) < 2:
        raise HTTPException(400, detail="At least 2 columns required.")
    return correlation_heatmap_data(_state.current_data, cols, method)


@router.post("/swimmer")
async def swimmer_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    pat = body.get("patient_col") or body.get("patient")
    start = body.get("start_col") or body.get("start")
    end = body.get("end_col") or body.get("end")
    resp = body.get("response_col")
    if not pat or not start or not end:
        raise HTTPException(400, detail="'patient_col', 'start_col', 'end_col' required.")
    return swimmer_plot_data(_state.current_data, pat, start, end, resp)


@router.post("/volcano")
async def volcano_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    eff = body.get("effect_col") or body.get("effect")
    pv = body.get("pvalue_col") or body.get("pvalue")
    label = body.get("label_col")
    if not eff or not pv:
        raise HTTPException(400, detail="'effect_col' and 'pvalue_col' required.")
    return volcano_plot_data(_state.current_data, eff, pv, label)


@router.post("/ridgeline")
async def ridgeline_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    val = body.get("value_col") or body.get("value")
    grp = body.get("group_col") or body.get("group")
    if not val or not grp:
        raise HTTPException(400, detail="'value_col' and 'group_col' required.")
    return ridgeline_plot_data(_state.current_data, val, grp)


@router.post("/bubble")
async def bubble_chart(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    x = body.get("x_col") or body.get("x")
    y = body.get("y_col") or body.get("y")
    sz = body.get("size_col") or body.get("size")
    grp = body.get("group_col")
    if not x or not y or not sz:
        raise HTTPException(400, detail="'x_col', 'y_col', 'size_col' required.")
    return bubble_chart_data(_state.current_data, x, y, sz, grp)


@router.post("/calibration")
async def calibration_plot(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    pred = body.get("predicted_col") or body.get("predicted")
    act = body.get("actual_col") or body.get("actual")
    if not pred or not act:
        raise HTTPException(400, detail="'predicted_col' and 'actual_col' required.")
    return calibration_plot_data(_state.current_data, pred, act)


@router.post("/pca")
async def pca_scatter(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cols = body.get("columns", [])
    grp = body.get("group_col")
    if len(cols) < 2:
        raise HTTPException(400, detail="At least 2 columns required for PCA.")
    return pca_scatter_data(_state.current_data, cols, grp)


@router.post("/correlation-network")
async def correlation_network(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    cols = body.get("columns", [])
    thresh = body.get("threshold", 0.3)
    if len(cols) < 3:
        raise HTTPException(400, detail="At least 3 columns required for network.")
    return correlation_network_data(_state.current_data, cols, thresh)


@router.post("/monthly-trend")
async def monthly_trend_heatmap(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    date = body.get("date_col") or body.get("date")
    val = body.get("value_col") or body.get("value")
    if not date or not val:
        raise HTTPException(400, detail="'date_col' and 'value_col' required.")
    return monthly_trend_heatmap_data(_state.current_data, date, val)


@router.post("/ae-heatmap")
async def adverse_event_heatmap(body: Dict[str, Any]) -> Dict[str, Any]:
    _require_data()
    pat = body.get("patient_col") or body.get("patient")
    evt = body.get("event_col") or body.get("event")
    grade = body.get("grade_col")
    if not pat or not evt:
        raise HTTPException(400, detail="'patient_col' and 'event_col' required.")
    return adverse_event_heatmap_data(_state.current_data, pat, evt, grade)


@router.post("/export/matplotlib")
async def export_matplotlib(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a publication-quality chart via matplotlib/seaborn and return as base64 PNG."""
    _require_data()
    chart_type = body.get("chart_type", "histogram")
    column = body.get("column")
    group_col = body.get("group_col")

    sns.set_style("whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5))

    try:
        if chart_type == "histogram" and column:
            data = _state.current_data[column].dropna()
            sns.histplot(data, kde=True, ax=ax)
            ax.set_title(f"Histogram of {column}")
        elif chart_type == "boxplot" and column:
            if group_col:
                sns.boxplot(x=_state.current_data[group_col], y=_state.current_data[column], ax=ax)
            else:
                sns.boxplot(y=_state.current_data[column], ax=ax)
            ax.set_title(f"Boxplot of {column}")
        elif chart_type == "scatter":
            x_col = body.get("x_col") or body.get("x")
            y_col = body.get("y_col") or body.get("y")
            if x_col and y_col:
                sns.scatterplot(x=_state.current_data[x_col], y=_state.current_data[y_col], ax=ax)
                ax.set_title(f"{x_col} vs {y_col}")
        elif chart_type == "correlation_heatmap":
            cols = body.get("columns", [])
            if len(cols) >= 2:
                corr = _state.current_data[cols].corr()
                sns.heatmap(corr, annot=True, cmap="RdBu_r", center=0, ax=ax)
                ax.set_title("Correlation Heatmap")
        elif chart_type == "violin" and column:
            if group_col:
                sns.violinplot(x=_state.current_data[group_col], y=_state.current_data[column], ax=ax)
            else:
                sns.violinplot(y=_state.current_data[column], ax=ax)
            ax.set_title(f"Violin Plot of {column}")
        elif chart_type == "pairplot":
            cols = body.get("columns", [])
            if len(cols) >= 2:
                fig = sns.pairplot(_state.current_data[cols].dropna(), diag_kind="kde")
                fig.savefig(buf := io.BytesIO(), format="png", dpi=150, bbox_inches="tight")
                plt.close("all")
                return {"image": base64.b64encode(buf.getvalue()).decode(), "format": "png"}
        else:
            return {"error": f"Unsupported matplotlib chart type: {chart_type}"}

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close("all")
        return {"image": base64.b64encode(buf.getvalue()).decode(), "format": "png", "chart_type": chart_type}
    except Exception as e:
        plt.close("all")
        return {"error": f"Matplotlib export failed: {e}"}
