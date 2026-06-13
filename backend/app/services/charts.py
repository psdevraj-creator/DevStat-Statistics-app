"""
Charts service for DevStat.

Provides functions that return JSON-serialisable chart data structures
for use by the front-end charting library. Each function returns a dict
that can be directly rendered by a chart component.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.services import error


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _round(value: float, decimals: int = 4) -> float:
    """Round a float to *decimals* places, preserving None."""
    if value is None:
        return None
    return round(float(value), decimals)


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------


def histogram_data(
    df: pd.DataFrame,
    column: str,
    bins: str | int = "auto",
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare histogram chart data.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    column : str
        Numeric column to histogram.
    bins : str or int, optional
        Number of bins or method (``'auto'``, ``'fd'``, ``'sturges'``, etc.).
        Passed directly to :func:`numpy.histogram_bin_edges`.
    group_col : str, optional
        If provided, histograms are computed per group.

    Returns
    -------
    dict
        With keys ``bins`` (edges), ``counts``, ``normal_curve_coords``,
        and ``group`` info when grouped.
    """
    if column not in df.columns:
        return error(f"Column '{column}' not found in DataFrame.")

    df_clean = df[[column] + ([group_col] if group_col else [])].dropna()
    # Coerce to numeric — silently drop non-numeric values
    df_clean[column] = pd.to_numeric(df_clean[column], errors="coerce")
    df_clean = df_clean.dropna(subset=[column])

    if group_col is not None and group_col in df.columns:
        groups = df_clean[group_col].unique()
        groups = sorted([g for g in groups if pd.notna(g)], key=str)
        series_list = []
        for g in groups:
            series_list.append(
                (str(g), df_clean[df_clean[group_col] == g][column])
            )
    else:
        series_list = [("all", df_clean[column])]

    result: Dict[str, Any] = {
        "chart_type": "histogram",
        "column": column,
        "group_col": group_col,
        "series": [],
    }

    for label, series in series_list:
        vals = series.dropna().values
        if len(vals) == 0:
            continue

        # Compute bins.
        if isinstance(bins, str) and bins == "auto":
            bin_edges = np.histogram_bin_edges(vals, bins="auto")
        elif isinstance(bins, int):
            bin_edges = np.histogram_bin_edges(vals, bins=bins)
        else:
            bin_edges = np.histogram_bin_edges(vals, bins="auto")

        counts, _ = np.histogram(vals, bins=bin_edges)

        # Normal curve coordinates.
        mu = float(np.mean(vals))
        sigma = float(np.std(vals, ddof=1))
        x_normal = np.linspace(vals.min(), vals.max(), 100)
        y_normal = sp_stats.norm.pdf(x_normal, loc=mu, scale=sigma)
        # Scale to match histogram area.
        bin_width = bin_edges[1] - bin_edges[0]
        area_hist = len(vals) * bin_width
        y_normal_scaled = y_normal * area_hist

        series_data = {
            "group": label,
            "bins": [_round(float(b)) for b in bin_edges],
            "counts": [int(c) for c in counts],
            "normal_curve_coords": {
                "x": [_round(float(x)) for x in x_normal.tolist()],
                "y": [_round(float(y)) for y in y_normal_scaled.tolist()],
            },
            "mean": _round(mu),
            "std": _round(sigma),
            "n": int(len(vals)),
        }
        result["series"].append(series_data)

    return result


# ---------------------------------------------------------------------------
# Boxplot
# ---------------------------------------------------------------------------


def boxplot_data(
    df: pd.DataFrame,
    column: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare boxplot chart data.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    column : str
        Numeric column for the boxplot.
    group_col : str, optional
        If provided, one box per group.

    Returns
    -------
    dict
        With keys ``groups`` (list of dicts with min, q1, median, q3, max,
        outliers, n).
    """
    if column not in df.columns:
        return error(f"Column '{column}' not found in DataFrame.")

    df_clean = df[[column] + ([group_col] if group_col else [])].dropna()
    # Coerce to numeric — silently drop non-numeric values
    df_clean[column] = pd.to_numeric(df_clean[column], errors="coerce")
    df_clean = df_clean.dropna(subset=[column])

    if group_col is not None and group_col in df.columns:
        groups = df_clean[group_col].unique()
        groups = sorted([g for g in groups if pd.notna(g)], key=str)
        series_list = {}
        for g in groups:
            series_list[str(g)] = df_clean[df_clean[group_col] == g][column]
    else:
        series_list = {"all": df_clean[column]}

    result: Dict[str, Any] = {
        "chart_type": "boxplot",
        "column": column,
        "group_col": group_col,
        "groups": [],
    }

    for label, series in series_list.items():
        vals = series.dropna().values
        if len(vals) == 0:
            continue

        q1 = float(np.percentile(vals, 25))
        median = float(np.percentile(vals, 50))
        q3 = float(np.percentile(vals, 75))
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr

        inside = vals[(vals >= lower_fence) & (vals <= upper_fence)]
        outliers = vals[(vals < lower_fence) | (vals > upper_fence)]

        _min = float(inside.min()) if len(inside) > 0 else float(vals.min())
        _max = float(inside.max()) if len(inside) > 0 else float(vals.max())

        outlier_list = []
        for o in outliers:
            outlier_list.append({"value": _round(float(o))})

        group_data = {
            "group": label,
            "min": _round(_min),
            "q1": _round(q1),
            "median": _round(median),
            "q3": _round(q3),
            "max": _round(_max),
            "outliers": outlier_list,
            "n": int(len(vals)),
        }
        result["groups"].append(group_data)

    return result


# ---------------------------------------------------------------------------
# Scatter Plot
# ---------------------------------------------------------------------------


def scatter_data(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare scatter plot chart data with regression line.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    x_col : str
        Column for x-axis.
    y_col : str
        Column for y-axis.
    group_col : str, optional
        If provided, points are coloured by group.

    Returns
    -------
    dict
        With keys ``points``, ``regression_line``, ``r_squared``,
        and ``group_col`` info when grouped.
    """
    for col in [x_col, y_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    cols = [x_col, y_col]
    if group_col:
        cols.append(group_col)

    df_clean = df[cols].dropna()
    # Coerce both axes to numeric — silently drop non-numeric values
    for ax in [x_col, y_col]:
        df_clean[ax] = pd.to_numeric(df_clean[ax], errors="coerce")
    df_clean = df_clean.dropna(subset=[x_col, y_col])

    if group_col and group_col in df.columns:
        groups = df_clean[group_col].unique()
        groups = sorted([g for g in groups if pd.notna(g)], key=str)
        points_by_group = {}
        for g in groups:
            subset = df_clean[df_clean[group_col] == g]
            points_by_group[str(g)] = {
                "x": [_round(float(v)) for v in subset[x_col].values],
                "y": [_round(float(v)) for v in subset[y_col].values],
            }

        # Overall regression.
        x_vals = df_clean[x_col].values
        y_vals = df_clean[y_col].values
    else:
        x_vals = df_clean[x_col].values
        y_vals = df_clean[y_col].values
        points_by_group = {
            "all": {
                "x": [_round(float(v)) for v in x_vals],
                "y": [_round(float(v)) for v in y_vals],
            }
        }

    # Regression line.
    if len(x_vals) > 2:
        slope, intercept, r_val, p_val, se = sp_stats.linregress(x_vals, y_vals)
        x_line = np.linspace(float(x_vals.min()), float(x_vals.max()), 100)
        y_line = intercept + slope * x_line
        r_sq = r_val ** 2
        regression_line = {
            "slope": _round(float(slope)),
            "intercept": _round(float(intercept)),
            "x": [_round(float(x)) for x in x_line.tolist()],
            "y": [_round(float(y)) for y in y_line.tolist()],
        }
    else:
        r_sq = 0.0
        regression_line = None

    result: Dict[str, Any] = {
        "chart_type": "scatter",
        "x_col": x_col,
        "y_col": y_col,
        "group_col": group_col,
        "points": points_by_group,
        "regression_line": regression_line,
        "r_squared": _round(r_sq),
        "n": int(len(df_clean)),
    }

    return result


# ---------------------------------------------------------------------------
# Bar Chart
# ---------------------------------------------------------------------------


def bar_chart_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: Optional[str] = None,
    error_bars: str = "sd",
) -> Dict[str, Any]:
    """Prepare bar chart data.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    category_col : str
        Column containing category labels (x-axis).
    value_col : str, optional
        Column containing numeric values. If None, counts of categories
        are used.
    error_bars : str, optional
        Type of error bars: ``'sd'`` (default, standard deviation),
        ``'se'`` (standard error), ``'ci95'`` (95% CI), or ``'none'``.

    Returns
    -------
    dict
        With keys ``categories``, ``values``, ``errors``, ``n``.
    """
    if category_col not in df.columns:
        return error(f"Column '{category_col}' not found in DataFrame.")

    df_clean = df[[category_col] + ([value_col] if value_col else [])].dropna()

    result: Dict[str, Any] = {
        "chart_type": "bar",
        "category_col": category_col,
        "value_col": value_col,
        "series": [],
    }

    if value_col is not None and value_col in df.columns:
        # Aggregate by category.
        grouped = df_clean.groupby(category_col, dropna=True)[value_col]
        categories = []
        values = []
        errors = []
        for cat, group in grouped:
            vals = group.dropna().values
            if len(vals) == 0:
                continue
            mean_val = float(np.mean(vals))
            std_val = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            n_vals = len(vals)

            if error_bars == "sd":
                err = std_val
            elif error_bars == "se":
                err = std_val / np.sqrt(n_vals) if n_vals > 1 else 0.0
            elif error_bars == "ci95":
                err = (std_val / np.sqrt(n_vals)) * sp_stats.t.ppf(0.975, n_vals - 1) if n_vals > 1 else 0.0
            else:
                err = 0.0

            categories.append(str(cat))
            values.append(_round(mean_val))
            errors.append(_round(err))

        result["series"].append({
            "label": value_col,
            "categories": categories,
            "values": values,
            "errors": errors,
            "error_type": error_bars,
        })
    else:
        # Frequency counts.
        counts = df_clean[category_col].value_counts()
        categories = [str(c) for c in counts.index.tolist()]
        values = [int(v) for v in counts.values.tolist()]
        result["series"].append({
            "label": "count",
            "categories": categories,
            "values": values,
            "errors": [0] * len(values),
            "error_type": "none",
        })

    return result


# ---------------------------------------------------------------------------
# KM Curve Data (transform kaplan_meier result)
# ---------------------------------------------------------------------------


def km_curve_data(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a :func:`kaplan_meier` result into plot-ready coordinates.

    Parameters
    ----------
    result_dict : dict
        The dict returned by :func:`survival.kaplan_meier`.

    Returns
    -------
    dict
        With keys ``series`` (list of {group, x, y, ci_lower, ci_upper}),
        ``n_total``, ``n_events``, and ``n_censored``.
    """
    if "error" in result_dict:
        return result_dict

    km_raw = result_dict.get("km_curve", [])
    lr = result_dict.get("log_rank_test")
    return {
        "chart_type": "km_curve",
        "series": km_raw,
        "n_total": result_dict.get("n_total"),
        "n_events": result_dict.get("n_events"),
        "n_censored": result_dict.get("n_censored"),
        "median_survival": result_dict.get("median_survival"),
        "interpretation": result_dict.get("interpretation"),
        "log_rank_test": lr,
        "chisq": lr["statistic"] if lr and lr.get("statistic") is not None else None,
        "p_value": lr["p"] if lr and lr.get("p") is not None else None,
    }


# ---------------------------------------------------------------------------
# ROC Curve Data (transform roc_analysis result)
# ---------------------------------------------------------------------------


def roc_curve_data(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a :func:`roc_analysis` result into plot-ready coordinates.

    Parameters
    ----------
    result_dict : dict
        The dict returned by :func:`diagnostic.roc_analysis`.

    Returns
    -------
    dict
        With keys ``coordinates`` (list of {fpr, tpr}), ``auc``,
        ``optimal_cutoff``.
    """
    if "error" in result_dict:
        return result_dict

    coords = result_dict.get("roc_coordinates", [])
    clean_coords = [{"fpr": c["fpr"], "tpr": c["tpr"]} for c in coords]

    return {
        "chart_type": "roc_curve",
        "coordinates": clean_coords,
        "auc": result_dict.get("auc"),
        "optimal_cutoff": result_dict.get("optimal_cutoff"),
    }


# ---------------------------------------------------------------------------
# Forest Plot Data
# ---------------------------------------------------------------------------


def forest_plot_data(coefficients_table: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare forest plot data from a coefficients table.

    Designed to work with the coefficients tables from logistic regression
    (OR with CI) or Cox regression (HR with CI).

    Parameters
    ----------
    coefficients_table : list of dict
        Each dict must contain at minimum ``name``, plus either
        ``or``/``or_ci_lower``/``or_ci_upper`` or
        ``hr``/``hr_ci_lower``/``hr_ci_upper``.

    Returns
    -------
    dict
        With keys ``variables`` (list of {name, estimate, ci_lower,
        ci_upper, p}), ``effect_type`` (``'OR'`` or ``'HR'``).
    """
    if not coefficients_table:
        return error("Empty coefficients table.")

    # Detect effect type.
    first = coefficients_table[0]
    if "or" in first:
        effect_type = "OR"
    elif "hr" in first:
        effect_type = "HR"
    else:
        return error("Coefficients table must contain 'or' or 'hr' keys.")

    variables = []
    for row in coefficients_table:
        if row.get("name") == "const":
            continue
        estimate_key = "or" if effect_type == "OR" else "hr"
        ci_lower_key = f"{estimate_key}_ci_lower"
        ci_upper_key = f"{estimate_key}_ci_upper"

        variables.append({
            "name": row.get("name"),
            "estimate": row.get(estimate_key),
            "ci_lower": row.get(ci_lower_key),
            "ci_upper": row.get(ci_upper_key),
            "p": row.get("p"),
            "p_label": row.get("p_label"),
        })

    return {
        "chart_type": "forest_plot",
        "variables": variables,
        "effect_type": effect_type,
    }


# ---------------------------------------------------------------------------
# Downsampling helper for large datasets
# ---------------------------------------------------------------------------

MAX_CHART_POINTS = 5_000


# ═══════════════════════════════════════════════════════════════════════════
# Batch 1 — Distribution plots
# ═══════════════════════════════════════════════════════════════════════════


def violin_plot_data(
    df: pd.DataFrame,
    column: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Violin plot — distribution of a numeric variable across groups."""
    if column not in df.columns:
        return error(f"Column '{column}' not found.")
    data = df[[column] + ([group_col] if group_col else [])].dropna()
    if group_col:
        traces = []
        for g in sorted(data[group_col].unique()):
            vals = data.loc[data[group_col] == g, column]
            traces.append({
                "type": "violin", "y": vals.tolist(), "name": str(g),
                "box": {"visible": True}, "meanline": {"visible": True},
            })
    else:
        traces = [{"type": "violin", "y": data[column].tolist(), "name": column}]
    return {"chart_type": "violin", "traces": traces,
            "layout": {"title": f"Violin Plot: {column}", "yaxis": {"title": column}}}


def strip_plot_data(
    df: pd.DataFrame,
    column: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Strip/beeswarm plot — individual data points across groups."""
    if column not in df.columns:
        return error(f"Column '{column}' not found.")
    data = df[[column] + ([group_col] if group_col else [])].dropna()
    if group_col:
        traces = []
        for g in sorted(data[group_col].unique()):
            vals = data.loc[data[group_col] == g, column]
            traces.append({
                "type": "strip", "y": vals.tolist(), "name": str(g),
                "box": {"visible": True},
            })
    else:
        traces = [{"type": "strip", "y": data[column].tolist(), "name": column}]
    return {"chart_type": "strip", "traces": traces,
            "layout": {"title": f"Strip Plot: {column}", "yaxis": {"title": column}}}


def ecdf_plot_data(
    df: pd.DataFrame,
    column: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """ECDF — empirical cumulative distribution function."""
    if column not in df.columns:
        return error(f"Column '{column}' not found.")
    data = df[[column] + ([group_col] if group_col else [])].dropna()
    traces = []
    groups = [None] if not group_col else sorted(data[group_col].unique())
    for g in groups:
        vals = data[column] if g is None else data.loc[data[group_col] == g, column]
        sorted_vals = np.sort(vals.values)
        ecdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
        traces.append({
            "type": "scatter", "mode": "lines",
            "x": sorted_vals.tolist(), "y": ecdf.tolist(),
            "name": str(g) if g else column,
        })
    return {"chart_type": "ecdf", "traces": traces,
            "layout": {"title": f"ECDF: {column}", "xaxis": {"title": column}, "yaxis": {"title": "Cumulative Probability"}}}


def qq_plot_data(
    df: pd.DataFrame,
    column: str,
    dist: str = "norm",
) -> Dict[str, Any]:
    """Q-Q plot — compare distribution to a theoretical one."""
    if column not in df.columns:
        return error(f"Column '{column}' not found.")
    vals = df[column].dropna().values
    if len(vals) < 4:
        return error("Need at least 4 data points for Q-Q plot.")
    from scipy import stats as sp_stats
    if dist == "norm":
        theoretical = sp_stats.probplot(vals, dist="norm")
        qq_x = theoretical[0][0]
        qq_y = theoretical[0][1]
    else:
        return error(f"Unknown distribution: '{dist}'")
    min_val = min(min(qq_x), min(qq_y))
    max_val = max(max(qq_x), max(qq_y))
    traces = [
        {"type": "scatter", "mode": "markers", "x": qq_x.tolist(), "y": qq_y.tolist(), "name": column},
        {"type": "scatter", "mode": "lines", "x": [min_val, max_val], "y": [min_val, max_val],
         "name": "y=x", "line": {"dash": "dash", "color": "#888"}},
    ]
    return {"chart_type": "qq", "traces": traces,
            "layout": {"title": f"Q-Q Plot: {column}", "xaxis": {"title": "Theoretical Quantiles"},
                       "yaxis": {"title": "Sample Quantiles"}}}


def hexbin_plot_data(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
) -> Dict[str, Any]:
    """Hexbin plot — 2D density for large datasets."""
    for col in [x_col, y_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[x_col, y_col]].dropna()
    n = len(data)
    if n < 1000:
        return error(f"Hexbin requires 1000+ points; dataset has {n}. Use scatter plot instead.")
    # Downsample to max 10000 for performance
    if n > 10000:
        data = data.sample(n=10000, random_state=42)
    traces = [{
        "type": "histogram2dcontour" if n > 5000 else "histogram2d",
        "x": data[x_col].tolist(), "y": data[y_col].tolist(),
        "colorscale": "Viridis", "name": "density",
    }]
    return {"chart_type": "hexbin", "traces": traces,
            "layout": {"title": f"Hexbin: {x_col} vs {y_col}",
                       "xaxis": {"title": x_col}, "yaxis": {"title": y_col}}}


# ═══════════════════════════════════════════════════════════════════════════
# Batch 2 — Comparison charts
# ═══════════════════════════════════════════════════════════════════════════


def pareto_chart_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Pareto chart — sorted bar + cumulative line."""
    for col in [category_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, value_col]].dropna().groupby(category_col)[value_col].sum().sort_values(ascending=False)
    categories = data.index.tolist()
    values = data.values.tolist()
    cumulative = np.cumsum(values) / sum(values) * 100
    traces = [
        {"type": "bar", "x": categories, "y": values, "name": "Values"},
        {"type": "scatter", "mode": "lines+markers", "x": categories, "y": cumulative.tolist(),
         "yaxis": "y2", "name": "Cumulative %", "line": {"color": "#e53e3e"}},
    ]
    return {"chart_type": "pareto", "traces": traces,
            "layout": {"title": "Pareto Chart", "xaxis": {"title": category_col},
                       "yaxis": {"title": "Value"}, "yaxis2": {"title": "Cumulative %", "overlaying": "y", "side": "right"}}}


def cleveland_dot_plot_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Cleveland dot plot — sorted dots with lines."""
    for col in [category_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, value_col]].dropna().groupby(category_col)[value_col].mean().sort_values()
    categories = [str(c) for c in data.index]
    values = data.values.tolist()
    traces = [{
        "type": "scatter", "mode": "markers", "x": values, "y": categories,
        "marker": {"size": 10, "color": "#005eb8"},
    }]
    return {"chart_type": "cleveland_dot", "traces": traces,
            "layout": {"title": "Cleveland Dot Plot", "xaxis": {"title": value_col}, "yaxis": {"title": category_col, "autorange": "reversed"}}}


def lollipop_chart_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Lollipop chart — dots with stems."""
    for col in [category_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, value_col]].dropna().groupby(category_col)[value_col].mean().sort_values()
    categories = [str(c) for c in data.index]
    values = data.values.tolist()
    traces = [
        {"type": "scatter", "mode": "lines", "x": values, "y": categories,
         "line": {"color": "#a0aec0"}, "showlegend": False},
        {"type": "scatter", "mode": "markers", "x": values, "y": categories,
         "marker": {"size": 12, "color": "#005eb8"}, "name": value_col},
    ]
    return {"chart_type": "lollipop", "traces": traces,
            "layout": {"title": "Lollipop Chart", "xaxis": {"title": value_col}, "yaxis": {"title": category_col, "autorange": "reversed"}}}


def dumbbell_plot_data(
    df: pd.DataFrame,
    category_col: str,
    pre_col: str,
    post_col: str,
) -> Dict[str, Any]:
    """Dumbbell plot — change between two time points."""
    for col in [category_col, pre_col, post_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, pre_col, post_col]].dropna().groupby(category_col)[[pre_col, post_col]].mean()
    categories = [str(c) for c in data.index]
    pre_vals = data[pre_col].tolist()
    post_vals = data[post_col].tolist()
    traces = [
        {"type": "scatter", "mode": "lines", "x": list(zip(pre_vals, post_vals)), "y": list(zip(categories, categories)),
         "line": {"color": "#a0aec0"}, "showlegend": False},
        {"type": "scatter", "mode": "markers", "x": pre_vals, "y": categories,
         "marker": {"size": 10, "color": "#3182ce"}, "name": "Pre"},
        {"type": "scatter", "mode": "markers", "x": post_vals, "y": categories,
         "marker": {"size": 10, "color": "#e53e3e"}, "name": "Post"},
    ]
    return {"chart_type": "dumbbell", "traces": traces,
            "layout": {"title": "Dumbbell Plot — Pre vs Post", "xaxis": {"title": "Value"}, "yaxis": {"title": category_col, "autorange": "reversed"}}}


def splom_plot_data(
    df: pd.DataFrame,
    columns: list,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Scatter matrix — pairwise plots for multiple variables."""
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    if len(columns) < 3:
        return error("SPLOM requires at least 3 variables.")
    data = df[columns + ([group_col] if group_col else [])].dropna()
    dimensions = [{"label": c, "values": data[c].tolist()} for c in columns]
    trace = {"type": "splom", "dimensions": dimensions, "name": "Scatter Matrix"}
    if group_col:
        trace["marker"] = {"color": data[group_col].astype("category").cat.codes.tolist(), "showscale": True}
    return {"chart_type": "splom", "traces": [trace],
            "layout": {"title": "Scatter Matrix", "width": 700, "height": 700}}


# ═══════════════════════════════════════════════════════════════════════════
# Batch 3 — Time / process charts
# ═══════════════════════════════════════════════════════════════════════════


def control_chart_data(
    df: pd.DataFrame,
    value_col: str,
    time_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Control chart (Shewhart) — time-ordered values with ±3σ limits."""
    if value_col not in df.columns:
        return error(f"Column '{value_col}' not found.")
    data = df[[value_col] + ([time_col] if time_col else [])].dropna()
    vals = data[value_col].values
    n = len(vals)
    if n < 10:
        return error(f"Control chart needs at least 10 points; got {n}.")
    mean = float(np.mean(vals))
    std = float(np.std(vals, ddof=1))
    x = data[time_col].tolist() if time_col else list(range(n))
    traces = [
        {"type": "scatter", "mode": "lines", "x": x, "y": vals.tolist(), "name": value_col},
        {"type": "scatter", "mode": "lines", "x": x, "y": [mean] * n, "name": "Mean", "line": {"dash": "dash", "color": "#38a169"}},
        {"type": "scatter", "mode": "lines", "x": x, "y": [mean + 3 * std] * n, "name": "UCL (+3σ)", "line": {"dash": "dot", "color": "#e53e3e"}},
        {"type": "scatter", "mode": "lines", "x": x, "y": [mean - 3 * std] * n, "name": "LCL (-3σ)", "line": {"dash": "dot", "color": "#e53e3e"}},
    ]
    return {"chart_type": "control_chart", "traces": traces,
            "layout": {"title": "Control Chart", "xaxis": {"title": time_col or "Index"}, "yaxis": {"title": value_col}}}


def run_chart_data(
    df: pd.DataFrame,
    value_col: str,
    time_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Run chart — data over time with median line."""
    if value_col not in df.columns:
        return error(f"Column '{value_col}' not found.")
    data = df[[value_col] + ([time_col] if time_col else [])].dropna()
    vals = data[value_col].values
    n = len(vals)
    if n < 5:
        return error(f"Run chart needs at least 5 points; got {n}.")
    median = float(np.median(vals))
    x = data[time_col].tolist() if time_col else list(range(n))
    traces = [
        {"type": "scatter", "mode": "lines+markers", "x": x, "y": vals.tolist(), "name": value_col},
        {"type": "scatter", "mode": "lines", "x": x, "y": [median] * n, "name": "Median", "line": {"dash": "dash", "color": "#e53e3e"}},
    ]
    return {"chart_type": "run_chart", "traces": traces,
            "layout": {"title": "Run Chart", "xaxis": {"title": time_col or "Index"}, "yaxis": {"title": value_col}}}


def gantt_chart_data(
    df: pd.DataFrame,
    task_col: str,
    start_col: str,
    end_col: str,
) -> Dict[str, Any]:
    """Gantt chart — task timeline."""
    for col in [task_col, start_col, end_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[task_col, start_col, end_col]].dropna()
    # Convert dates to numeric if needed
    for c in [start_col, end_col]:
        if not pd.api.types.is_numeric_dtype(data[c]):
            data[c] = pd.to_numeric(pd.to_datetime(data[c]).astype(np.int64), errors="coerce")
    data = data.dropna()
    if len(data) == 0:
        return error("No valid data after date conversion.")
    tasks = data[task_col].tolist()
    traces = []
    for i, (_, row) in enumerate(data.iterrows()):
        traces.append({
            "type": "bar", "orientation": "h",
            "y": [str(row[task_col])], "x": [float(row[end_col] - row[start_col])],
            "base": float(row[start_col]), "name": str(row[task_col]),
            "showlegend": False, "width": 0.6,
        })
    return {"chart_type": "gantt", "traces": traces,
            "layout": {"title": "Gantt Chart", "xaxis": {"title": "Time"}, "yaxis": {"title": task_col, "autorange": "reversed"},
                       "barmode": "stack" if len(traces) > 1 else "relative"}}


def calendar_heatmap_data(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Calendar heatmap — aggregate values by date."""
    for col in [date_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[date_col, value_col]].dropna()
    try:
        dates = pd.to_datetime(data[date_col])
        data["month"] = dates.dt.month
        data["day"] = dates.dt.day
    except Exception:
        return error("Date column could not be parsed.")
    pivoted = data.pivot_table(index="day", columns="month", values=value_col, aggfunc="mean")
    z = pivoted.fillna(0).values.tolist()
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    traces = [{
        "type": "heatmap", "z": z,
        "x": [months[i] for i in range(len(pivoted.columns))],
        "y": list(range(1, 32)),
        "colorscale": "Viridis", "name": value_col,
    }]
    return {"chart_type": "calendar_heatmap", "traces": traces,
            "layout": {"title": "Calendar Heatmap", "xaxis": {"title": "Month"}, "yaxis": {"title": "Day of Month", "autorange": "reversed"}}}


# ═══════════════════════════════════════════════════════════════════════════
# Batch 4 — Specialized charts
# ═══════════════════════════════════════════════════════════════════════════


def parallel_coordinates_data(
    df: pd.DataFrame,
    columns: list,
    color_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Parallel coordinates — multi-dimensional data."""
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[columns + ([color_col] if color_col else [])].dropna()
    dimensions = []
    for c in columns:
        dim = {"label": c, "values": data[c].tolist()}
        if pd.api.types.is_numeric_dtype(data[c]):
            dim["range"] = [float(data[c].min()), float(data[c].max())]
        dimensions.append(dim)
    trace = {"type": "parcoords", "dimensions": dimensions, "name": "Parallel Coordinates"}
    if color_col and pd.api.types.is_numeric_dtype(data[color_col]):
        trace["line"] = {"color": data[color_col].tolist(), "colorscale": "Viridis", "showscale": True}
    return {"chart_type": "parallel_coordinates", "traces": [trace],
            "layout": {"title": "Parallel Coordinates", "height": 500}}


def radar_chart_data(
    df: pd.DataFrame,
    category_col: str,
    value_cols: list,
) -> Dict[str, Any]:
    """Radar/spider chart — multi-attribute profiles."""
    for col in [category_col] + value_cols:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col] + value_cols].dropna()
    traces = []
    for _, row in data.iterrows():
        r = [float(row[c]) for c in value_cols]
        traces.append({
            "type": "scatterpolar",
            "r": r + [r[0]],
            "theta": value_cols + [value_cols[0]],
            "fill": "toself",
            "name": str(row[category_col]),
        })
    return {"chart_type": "radar", "traces": traces,
            "layout": {"title": "Radar Chart", "polar": {"radialaxis": {"visible": True}}}}


def treemap_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    parent_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Treemap — hierarchical proportions."""
    for col in [category_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, value_col] + ([parent_col] if parent_col else [])].dropna()
    grouped = data.groupby(category_col)[value_col].sum().reset_index()
    labels = grouped[category_col].tolist()
    parents = [""] * len(labels)
    values = grouped[value_col].tolist()
    if parent_col:
        parent_map = data[[category_col, parent_col]].drop_duplicates(subset=[category_col]).set_index(category_col)[parent_col].to_dict()
        parents = [str(parent_map.get(l, "")) for l in labels]
    traces = [{"type": "treemap", "labels": labels, "parents": parents, "values": values, "textinfo": "label+value"}]
    return {"chart_type": "treemap", "traces": traces,
            "layout": {"title": "Treemap"}}


def sankey_diagram_data(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    value_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Sankey diagram — flow between categories."""
    for col in [source_col, target_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[source_col, target_col] + ([value_col] if value_col else [])].dropna()
    if not value_col:
        flow = data.groupby([source_col, target_col]).size().reset_index(name="count")
        value_col = "count"
    else:
        flow = data.groupby([source_col, target_col])[value_col].sum().reset_index()
    sources = pd.concat([flow[source_col], flow[target_col]]).unique()
    source_map = {s: i for i, s in enumerate(sources)}
    trace = {
        "type": "sankey",
        "node": {"label": [str(s) for s in sources]},
        "link": {
            "source": [source_map[s] for s in flow[source_col]],
            "target": [source_map[t] for t in flow[target_col]],
            "value": flow[value_col].tolist(),
        },
    }
    return {"chart_type": "sankey", "traces": [trace],
            "layout": {"title": "Sankey Diagram", "height": 500}}


def waterfall_chart_data(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Waterfall chart — sequential contribution to a total."""
    for col in [category_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[category_col, value_col]].dropna().groupby(category_col)[value_col].sum()
    categories = [str(c) for c in data.index]
    values = data.values.tolist()
    running = np.cumsum(values)
    traces = [
        {"type": "waterfall", "x": categories, "y": values,
         "connector": {"line": {"color": "#a0aec0"}},
         "increasing": {"marker": {"color": "#38a169"}},
         "decreasing": {"marker": {"color": "#e53e3e"}},
         "totals": {"marker": {"color": "#005eb8"}},
         "name": value_col},
    ]
    return {"chart_type": "waterfall", "traces": traces,
            "layout": {"title": "Waterfall Chart", "xaxis": {"title": category_col}, "yaxis": {"title": value_col}}}


def funnel_plot_data(
    df: pd.DataFrame,
    effect_col: str,
    precision_col: str,
) -> Dict[str, Any]:
    """Funnel plot — effect size vs precision with pseudo-confidence bands."""
    for col in [effect_col, precision_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[effect_col, precision_col]].dropna()
    n = len(data)
    if n < 5:
        return error(f"Funnel plot needs at least 5 points; got {n}.")
    effects = data[effect_col].values
    precisions = data[precision_col].values
    mean_effect = float(np.mean(effects))
    se_range = np.linspace(min(precisions), max(precisions), 100)
    traces = [
        {"type": "scatter", "mode": "markers", "x": effects.tolist(), "y": precisions.tolist(),
         "name": "Studies", "marker": {"color": "#005eb8"}},
        {"type": "scatter", "mode": "lines", "x": [mean_effect] * len(se_range), "y": se_range.tolist(),
         "name": "Mean effect", "line": {"dash": "dash", "color": "#e53e3e"}},
        {"type": "scatter", "mode": "lines", "x": (mean_effect + 1.96 * se_range).tolist(), "y": se_range.tolist(),
         "name": "95% CI", "line": {"dash": "dot", "color": "#a0aec0"}},
        {"type": "scatter", "mode": "lines", "x": (mean_effect - 1.96 * se_range).tolist(), "y": se_range.tolist(),
         "name": "", "line": {"dash": "dot", "color": "#a0aec0"}, "showlegend": False},
    ]
    return {"chart_type": "funnel", "traces": traces,
            "layout": {"title": "Funnel Plot", "xaxis": {"title": "Effect Size"}, "yaxis": {"title": "Precision (1/SE)"}}}


def bland_altman_plot_data(
    df: pd.DataFrame,
    col1: str,
    col2: str,
) -> Dict[str, Any]:
    """Bland-Altman plot — difference vs mean with limits of agreement."""
    for col in [col1, col2]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[col1, col2]].dropna()
    means = ((data[col1] + data[col2]) / 2).values
    diffs = (data[col1] - data[col2]).values
    n = len(means)
    if n < 3:
        return error("Need at least 3 paired measurements.")
    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1))
    loa_upper = mean_diff + 1.96 * std_diff
    loa_lower = mean_diff - 1.96 * std_diff
    x_range = [float(np.min(means)), float(np.max(means))]
    traces = [
        {"type": "scatter", "mode": "markers", "x": means.tolist(), "y": diffs.tolist(),
         "name": "Differences", "marker": {"color": "#005eb8"}},
        {"type": "scatter", "mode": "lines", "x": x_range, "y": [mean_diff, mean_diff],
         "name": f"Mean diff: {mean_diff:.3f}", "line": {"color": "#38a169", "dash": "dash"}},
        {"type": "scatter", "mode": "lines", "x": x_range, "y": [loa_upper, loa_upper],
         "name": f"+1.96 SD: {loa_upper:.3f}", "line": {"color": "#e53e3e", "dash": "dot"}},
        {"type": "scatter", "mode": "lines", "x": x_range, "y": [loa_lower, loa_lower],
         "name": f"-1.96 SD: {loa_lower:.3f}", "line": {"color": "#e53e3e", "dash": "dot"}},
    ]
    return {"chart_type": "bland_altman", "traces": traces,
            "layout": {"title": "Bland-Altman Plot", "xaxis": {"title": "Mean of two measurements"}, "yaxis": {"title": "Difference"}}}


def forest_plot_data(
    df: pd.DataFrame,
    label_col: str,
    estimate_col: str,
    ci_lower_col: str,
    ci_upper_col: str,
) -> Dict[str, Any]:
    """Forest plot — point estimates with confidence intervals."""
    for col in [label_col, estimate_col, ci_lower_col, ci_upper_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[label_col, estimate_col, ci_lower_col, ci_upper_col]].dropna()
    labels = [str(r[label_col]) for _, r in data.iterrows()]
    estimates = [float(r[estimate_col]) for _, r in data.iterrows()]
    ci_lowers = [float(r[ci_lower_col]) for _, r in data.iterrows()]
    ci_uppers = [float(r[ci_upper_col]) for _, r in data.iterrows()]
    x_err_lo = [e - l for e, l in zip(estimates, ci_lowers)]
    x_err_hi = [u - e for u, e in zip(ci_uppers, estimates)]
    traces = [{
        "type": "scatter", "mode": "markers",
        "x": estimates, "y": labels,
        "marker": {"color": "#005eb8", "size": 10},
        "error_x": {"type": "data", "symmetric": False, "array": x_err_hi, "arrayminus": x_err_lo, "color": "#a0aec0"},
        "name": "Estimate",
    }]
    return {"chart_type": "forest", "traces": traces,
            "layout": {"title": "Forest Plot", "xaxis": {"title": "Estimate (95% CI)"}, "yaxis": {"autorange": "reversed"}}}


# ═══════════════════════════════════════════════════════════════════════════
# New Medical/Clinical chart types
# ═══════════════════════════════════════════════════════════════════════════


def correlation_heatmap_data(
    df: pd.DataFrame,
    columns: list,
    method: str = "pearson",
) -> Dict[str, Any]:
    """Correlation heatmap — colored matrix of pairwise correlations."""
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[columns].dropna()
    corr = data.corr(method=method if method != "spearman" else "spearman").values
    z = np.round(corr, 4).tolist()
    traces = [{"type": "heatmap", "z": z, "x": columns, "y": columns, "colorscale": "RdBu_r", "zmin": -1, "zmax": 1}]
    return {"chart_type": "correlation_heatmap", "traces": traces,
            "layout": {"title": f"Correlation Heatmap ({method})", "xaxis": {"tickangle": -45}, "yaxis": {"autorange": "reversed"}, "width": 700, "height": 700}}


def swimmer_plot_data(
    df: pd.DataFrame,
    patient_col: str,
    start_col: str,
    end_col: str,
    response_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Swimmer plot — individual patient treatment timelines."""
    for col in [patient_col, start_col, end_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[patient_col, start_col, end_col] + ([response_col] if response_col else [])].dropna()
    patients = [str(p) for p in data[patient_col]]
    starts = pd.to_numeric(data[start_col], errors="coerce").fillna(0).tolist()
    durations = (pd.to_numeric(data[end_col], errors="coerce") - pd.to_numeric(data[start_col], errors="coerce")).fillna(0).tolist()
    traces = [{"type": "bar", "orientation": "h", "y": patients, "x": durations, "base": starts,
               "marker": {"color": "#005eb8"}, "name": "Treatment duration"}]
    if response_col and response_col in df.columns:
        responses = data[response_col].astype(str).tolist()
        response_map = {"CR": "#38a169", "PR": "#3182ce", "SD": "#ecc94b", "PD": "#e53e3e"}
        colors = [response_map.get(r, "#a0aec0") for r in responses]
        end_times = (pd.to_numeric(data[start_col], errors="coerce") + pd.to_numeric(data[end_col], errors="coerce")).fillna(0).tolist()
        traces.append({"type": "scatter", "mode": "markers", "y": patients, "x": end_times,
                       "marker": {"color": colors, "size": 12, "line": {"width": 1, "color": "white"}},
                       "name": "Best response"})
    return {"chart_type": "swimmer", "traces": traces,
            "layout": {"title": "Swimmer Plot", "xaxis": {"title": "Time"}, "yaxis": {"autorange": "reversed", "title": "Patient"},
                       "barmode": "overlay", "showlegend": True}}


def volcano_plot_data(
    df: pd.DataFrame,
    effect_col: str,
    pvalue_col: str,
    label_col: Optional[str] = None,
    log_p: bool = True,
) -> Dict[str, Any]:
    """Volcano plot — effect size vs p-value for biomarker discovery."""
    for col in [effect_col, pvalue_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[effect_col, pvalue_col] + ([label_col] if label_col else [])].dropna()
    effects = data[effect_col].values
    pvals = data[pvalue_col].values
    neg_log_p = -np.log10(pvals) if log_p else pvals
    colors = ["#e53e3e" if (abs(e) > 1 and p < 0.05) else "#a0aec0" for e, p in zip(effects, pvals)]
    traces = [{"type": "scatter", "mode": "markers", "x": effects.tolist(), "y": neg_log_p.tolist(),
               "marker": {"color": colors, "size": 6}, "name": "Features",
               "text": data[label_col].tolist() if label_col else None, "hoverinfo": "x+y+text" if label_col else "x+y"}]
    # Significance threshold lines
    max_y = float(np.max(neg_log_p)) * 1.1
    max_x = float(np.max(np.abs(effects))) * 1.2
    traces.append({"type": "scatter", "mode": "lines", "x": [-max_x, max_x], "y": [-np.log10(0.05), -np.log10(0.05)],
                   "name": "p=0.05", "line": {"dash": "dash", "color": "#e53e3e"}})
    if max_x > 1:
        traces.append({"type": "scatter", "mode": "lines", "x": [-1, -1], "y": [0, max_y],
                       "name": "FC=2", "line": {"dash": "dot", "color": "#3182ce"}})
        traces.append({"type": "scatter", "mode": "lines", "x": [1, 1], "y": [0, max_y],
                       "name": "", "line": {"dash": "dot", "color": "#3182ce"}, "showlegend": False})
    return {"chart_type": "volcano", "traces": traces,
            "layout": {"title": "Volcano Plot", "xaxis": {"title": "Effect Size (log2 fold change)"},
                       "yaxis": {"title": "-log10(p-value)"}, "height": 500}}


def ridgeline_plot_data(
    df: pd.DataFrame,
    value_col: str,
    group_col: str,
) -> Dict[str, Any]:
    """Ridgeline plot — distribution comparison across groups."""
    for col in [value_col, group_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[value_col, group_col]].dropna()
    from scipy import stats as sp_stats
    groups = sorted(data[group_col].unique())
    traces = []
    offset = 0
    for g in groups:
        vals = data.loc[data[group_col] == g, value_col].dropna().values
        if len(vals) < 3:
            continue
        kde = sp_stats.gaussian_kde(vals)
        x = np.linspace(float(vals.min()), float(vals.max()), 100)
        y = kde(x) * 0.8 + offset
        traces.append({"type": "scatter", "mode": "lines", "x": x.tolist(), "y": y.tolist(),
                       "fill": "tonexty", "name": str(g), "hoverinfo": "name+x+y"})
        offset += 1
    return {"chart_type": "ridgeline", "traces": traces,
            "layout": {"title": "Ridgeline Plot", "xaxis": {"title": value_col},
                       "yaxis": {"showticklabels": False, "title": group_col}, "height": 200 + 50 * len(traces),
                       "showlegend": True}}


def bubble_chart_data(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    size_col: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Bubble chart — 3-variable risk stratification."""
    for col in [x_col, y_col, size_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[x_col, y_col, size_col] + ([group_col] if group_col else [])].dropna()
    trace = {"type": "scatter", "mode": "markers", "x": data[x_col].tolist(), "y": data[y_col].tolist(),
             "marker": {"size": (data[size_col] / data[size_col].max() * 50 + 5).tolist(), "opacity": 0.7,
                        "color": data[group_col].astype("category").cat.codes.tolist() if group_col else "#005eb8",
                        "showscale": bool(group_col)},
             "text": data[group_col].tolist() if group_col else None, "name": "Risk stratification"}
    return {"chart_type": "bubble", "traces": [trace],
            "layout": {"title": "Bubble Chart", "xaxis": {"title": x_col}, "yaxis": {"title": y_col}, "height": 500}}


def calibration_plot_data(
    df: pd.DataFrame,
    predicted_col: str,
    actual_col: str,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Calibration plot — predicted vs observed probability."""
    for col in [predicted_col, actual_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[predicted_col, actual_col]].dropna()
    from sklearn import metrics as sk_metrics
    prob_true, prob_pred = sk_metrics.calibration_curve(data[actual_col], data[predicted_col], n_bins=n_bins)
    traces = [
        {"type": "scatter", "mode": "lines+markers", "x": prob_pred.tolist(), "y": prob_true.tolist(),
         "name": "Model", "marker": {"color": "#005eb8"}, "line": {"color": "#005eb8"}},
        {"type": "scatter", "mode": "lines", "x": [0, 1], "y": [0, 1],
         "name": "Perfect calibration", "line": {"dash": "dash", "color": "#a0aec0"}},
    ]
    return {"chart_type": "calibration", "traces": traces,
            "layout": {"title": "Calibration Plot", "xaxis": {"title": "Predicted Probability", "range": [0, 1]},
                       "yaxis": {"title": "Observed Proportion", "range": [0, 1]}, "height": 450}}


def pca_scatter_data(
    df: pd.DataFrame,
    columns: list,
    group_col: Optional[str] = None,
    n_components: int = 2,
) -> Dict[str, Any]:
    """PCA scatter — high-dimensional biomarker reduction."""
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    if len(columns) < 2:
        return error("Need at least 2 variables for PCA.")
    data = df[columns + ([group_col] if group_col else [])].dropna()
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    X = StandardScaler().fit_transform(data[columns].values)
    pca = PCA(n_components=n_components)
    coords = pca.fit_transform(X)
    var_explained = pca.explained_variance_ratio_ * 100
    trace = {"type": "scatter", "mode": "markers", "x": coords[:, 0].tolist(), "y": coords[:, 1].tolist(),
             "marker": {"color": data[group_col].astype("category").cat.codes.tolist() if group_col else "#005eb8",
                        "showscale": bool(group_col), "size": 8, "opacity": 0.7},
             "text": data[group_col].tolist() if group_col else None,
             "name": "PCA"}
    loadings = []
    for i, col in enumerate(columns):
        loadings.append({"variable": col, "pc1": round(float(pca.components_[0, i]), 4),
                         "pc2": round(float(pca.components_[1, i]), 4) if n_components > 1 else None})
    return {"chart_type": "pca", "traces": [trace],
            "layout": {"title": f"PCA Scatter ({var_explained[0]:.1f}% / {var_explained[1]:.1f}% variance)",
                       "xaxis": {"title": f"PC1 ({var_explained[0]:.1f}%)"},
                       "yaxis": {"title": f"PC2 ({var_explained[1]:.1f}%)" if n_components > 1 else "PC2"},
                       "height": 500},
            "loadings": loadings}


def correlation_network_data(
    df: pd.DataFrame,
    columns: list,
    threshold: float = 0.3,
) -> Dict[str, Any]:
    """Correlation network — graph of biomarker relationships."""
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[columns].dropna()
    corr = data.corr().values
    n = len(columns)
    np.fill_diagonal(corr, 0)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr[i, j]) >= threshold:
                edges.append({"source": columns[i], "target": columns[j], "weight": round(float(corr[i, j]), 4)})
    # Spring-like layout using simple force
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = {columns[i]: (float(np.cos(angles[i])), float(np.sin(angles[i]))) for i in range(n)}
    node_trace = {"type": "scatter", "mode": "markers+text", "x": [pos[c][0] for c in columns],
                  "y": [pos[c][1] for c in columns], "text": columns, "textposition": "top center",
                  "marker": {"size": 15, "color": "#005eb8"}, "name": "Variables"}
    edge_traces = []
    for e in edges:
        x0, y0 = pos[e["source"]]
        x1, y1 = pos[e["target"]]
        edge_traces.append({"type": "scatter", "mode": "lines", "x": [x0, x1], "y": [y0, y1],
                            "line": {"width": abs(e["weight"]) * 5, "color": "#e53e3e" if e["weight"] < 0 else "#38a169"},
                            "hoverinfo": "none", "showlegend": False})
    return {"chart_type": "correlation_network", "traces": edge_traces + [node_trace],
            "layout": {"title": "Correlation Network", "xaxis": {"visible": False}, "yaxis": {"visible": False},
                       "height": 500, "showlegend": False},
            "edges": edges}


def monthly_trend_heatmap_data(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
) -> Dict[str, Any]:
    """Monthly trend heatmap — values aggregated by month×year."""
    for col in [date_col, value_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[date_col, value_col]].dropna()
    try:
        dates = pd.to_datetime(data[date_col])
        data["year"] = dates.dt.year
        data["month"] = dates.dt.month
    except Exception:
        return error("Date column could not be parsed.")
    pivoted = data.pivot_table(index="year", columns="month", values=value_col, aggfunc="mean").fillna(0)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    traces = [{"type": "heatmap", "z": pivoted.values.tolist(), "x": [months[i] for i in range(len(pivoted.columns))],
               "y": pivoted.index.tolist(), "colorscale": "Viridis", "name": value_col}]
    return {"chart_type": "monthly_trend_heatmap", "traces": traces,
            "layout": {"title": "Monthly Trend Heatmap", "xaxis": {"title": "Month"}, "yaxis": {"title": "Year"}}}


def adverse_event_heatmap_data(
    df: pd.DataFrame,
    patient_col: str,
    event_col: str,
    grade_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Adverse event heatmap — patient × event severity matrix."""
    for col in [patient_col, event_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found.")
    data = df[[patient_col, event_col] + ([grade_col] if grade_col else [])].dropna()
    pivot = data.pivot_table(index=patient_col, columns=event_col, values=grade_col, aggfunc="max") if grade_col else \
             data.pivot_table(index=patient_col, columns=event_col, aggfunc="size")
    pivot = pivot.fillna(0)
    z = pivot.values.tolist()
    traces = [{"type": "heatmap", "z": z, "x": [str(c) for c in pivot.columns], "y": [str(i) for i in pivot.index],
               "colorscale": [[0, "#f0fff4"], [0.25, "#ecc94b"], [0.5, "#ed8936"], [0.75, "#e53e3e"], [1, "#742a2a"]],
               "name": "Grade" if grade_col else "Count"}]
    return {"chart_type": "adverse_event_heatmap", "traces": traces,
            "layout": {"title": "Adverse Event Heatmap", "xaxis": {"tickangle": -45, "title": "Event"},
                       "yaxis": {"title": "Patient"}, "height": max(400, len(pivot.index) * 15)}}


def downsample_series(x: list, y: list, max_points: int = MAX_CHART_POINTS) -> tuple:
    """Downsample (x, y) to at most *max_points* by taking evenly-spaced
    samples.  Returns (x_sampled, y_sampled)."""
    n = len(x)
    if n <= max_points:
        return x, y
    step = max(1, n // max_points)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)
    return [x[i] for i in indices], [y[i] for i in indices]
