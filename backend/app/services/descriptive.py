"""
Descriptive statistics service for DevStat.

Provides functions for computing descriptive statistics, frequency tables,
and cross-tabulations with inferential measures (chi-square, Cramer's V).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.services import error


# ---------------------------------------------------------------------------
# JSON-safe helper — converts numpy/pandas types to native Python
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Convert a value to a JSON-serializable native Python type.

    Handles: numpy integers, floats, booleans, arrays, pandas NA/NaT,
    and dictionaries/lists recursively.
    """
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.ndarray,)):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (pd.Timedelta,)):
        return str(value)
    if pd.isna(value):
        return None
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _json_safe_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert all values in a dict to JSON-safe types."""
    return {k: _json_safe(v) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------


def descriptive_stats(
    df: pd.DataFrame,
    columns: List[str],
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute rich descriptive statistics for one or more columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str
        Column names to analyse (must be numeric).
    group_col : str, optional
        If provided, statistics are computed per group in this column.

    Returns
    -------
    dict
        For each column a dict with keys:
        ``n``, ``mean``, ``median``, ``mode``, ``std``, ``variance``,
        ``min``, ``max``, ``q1``, ``q3``, ``iqr``, ``skewness``,
        ``kurtosis``, ``missing``, ``range``, ``sem``,
        ``ci_95_lower``, ``ci_95_upper``.

        When *group_col* is given, the top level is
        ``{column: {group_value: stats_dict}}``.

        The top-level dict also includes a ``_columns`` key listing the
        columns processed and ``_group_col`` if grouping was applied.
    """
    result: Dict[str, Any] = {
        "_columns": columns,
        "_group_col": group_col,
    }

    for col in columns:
        if col not in df.columns:
            result[col] = error(f"Column '{col}' not found in DataFrame")
            continue

        series = df[col]
        if not pd.api.types.is_numeric_dtype(series):
            result[col] = error(f"Column '{col}' is not numeric")
            continue

        if group_col is not None and group_col in df.columns:
            grouped = series.groupby(df[group_col], dropna=True)
            col_result: Dict[str, Any] = {}
            for group_name, group_vals in grouped:
                col_result[str(group_name)] = _stats_dict(group_vals)
            result[col] = col_result
        else:
            result[col] = _stats_dict(series)

    return result


def _stats_dict(series: pd.Series) -> Dict[str, Any]:
    """Compute the full set of descriptive stats for a single numeric series."""
    # Drop missing for calculations.
    clean = series.dropna()
    n = len(clean)
    missing = int(series.isna().sum())

    if n == 0:
        return {
            "n": 0,
            "missing": missing,
            "error": "All values are missing",
        }

    arr = clean.to_numpy(dtype=float)

    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    variance_val = float(np.var(arr, ddof=1)) if n > 1 else 0.0
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    range_val = max_val - min_val

    # Mode – may return multiple modes; take the first.
    mode_result = sp_stats.mode(arr, keepdims=True)
    mode_val = float(mode_result.mode[0]) if mode_result.count[0] > 0 else None

    # Quartiles.
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    # Shape statistics.
    skewness = float(sp_stats.skew(arr, bias=False)) if n > 2 else 0.0
    # Fisher (excess) kurtosis; normal → 0.
    kurtosis = float(sp_stats.kurtosis(arr, bias=False)) if n > 3 else 0.0

    # Standard error of the mean.
    sem_val = float(sp_stats.sem(arr, ddof=1)) if n > 1 else 0.0

    # 95 % confidence interval for the mean.
    if n > 1 and sem_val > 0:
        ci = sem_val * sp_stats.t.ppf(0.975, df=n - 1)
        ci_lower = mean_val - ci
        ci_upper = mean_val + ci
    else:
        ci_lower = mean_val
        ci_upper = mean_val

    return {
        "n": n,
        "missing": missing,
        "mean": _round(mean_val),
        "median": _round(median_val),
        "mode": _round(mode_val) if mode_val is not None else None,
        "std": _round(std_val),
        "variance": _round(variance_val),
        "min": _round(min_val),
        "max": _round(max_val),
        "range": _round(range_val),
        "q1": _round(q1),
        "q3": _round(q3),
        "iqr": _round(iqr),
        "skewness": _round(skewness),
        "kurtosis": _round(kurtosis),
        "sem": _round(sem_val),
        "ci_95_lower": _round(ci_lower),
        "ci_95_upper": _round(ci_upper),
    }


# ---------------------------------------------------------------------------
# Frequency tables
# ---------------------------------------------------------------------------


def frequencies(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    """Build a frequency table for a categorical / discrete column.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    column : str
        Column to tabulate.

    Returns
    -------
    dict
        Keys:
        * ``column`` — the column name
        * ``n`` — total non-missing count
        * ``missing`` — number of missing values
        * ``table`` — list of dicts with ``value``, ``count``, ``percent``,
          ``cumulative_percent``
    """
    if column not in df.columns:
        return {"column": column, "error": f"Column '{column}' not found"}

    series = df[column]
    missing = int(series.isna().sum())

    # Drop missing and count.
    clean = series.dropna()
    n = len(clean)

    if n == 0:
        return {
            "column": column,
            "n": 0,
            "missing": missing,
            "table": [],
        }

    # Value counts, sorted descending.
    # Normalize categorical labels: trim whitespace, collapse repeated spaces
    if pd.api.types.is_string_dtype(clean) or clean.dtype == object:
        clean = clean.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    counts = clean.value_counts(dropna=True)
    total = int(counts.sum())

    rows: List[Dict[str, Any]] = []
    cumulative = 0.0
    for val, cnt in counts.items():
        cnt_int = int(cnt)
        pct = round(cnt_int / total * 100, 2) if total > 0 else 0.0
        cumulative += pct
        # Convert numpy/pandas types to native Python for JSON serialization
        if hasattr(val, 'item'):
            val = val.item()
        elif pd.isna(val):
            val = None
        rows.append(
            {
                "value": val,
                "count": cnt_int,
                "percent": pct,
                "cumulative_percent": round(cumulative, 2),
            }
        )

    return {
        "column": column,
        "n": int(n),
        "missing": int(missing),
        "table": rows,
    }


# ---------------------------------------------------------------------------
# Cross-tabulation
# ---------------------------------------------------------------------------


def crosstab(
    df: pd.DataFrame,
    row: str,
    col: str,
) -> Dict[str, Any]:
    """Build a cross-tabulation with chi-square test and association measures.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    row : str
        Row variable column name.
    col : str
        Column variable column name.

    Returns
    -------
    dict
        Keys:
        * ``row``, ``col`` — variable names
        * ``n`` — total observations used
        * ``table`` — list of list (contingency matrix with row/col labels)
        * ``row_totals``, ``col_totals`` — margin totals
        * ``grand_total``
        * ``expected`` — expected frequencies matrix
        * ``percentages`` — row, col, total percentages dicts
        * ``chi2``, ``df``, ``p_value`` — chi-square test
        * ``cramers_v`` — Cramer's V
        * ``fisher_exact`` — Fisher's exact test result (only for 2×2 tables)
        * ``min_expected`` — minimum expected frequency (for assumption check)
    """
    if row not in df.columns:
        return {"row": row, "col": col, "error": f"Row column '{row}' not found"}
    if col not in df.columns:
        return {"row": row, "col": col, "error": f"Column column '{col}' not found"}

    # Build contingency table — drop rows missing either variable.
    ctab = pd.crosstab(df[row], df[col], margins=True, margins_name="Total")
    # Separate the observed table (without margins) for inference.
    observed = pd.crosstab(df[row], df[col], margins=False)

    n_total = int(observed.values.sum())
    rows_labels = [str(v) for v in observed.index.tolist()]
    cols_labels = [str(v) for v in observed.columns.tolist()]
    n_rows = len(rows_labels)
    n_cols = len(cols_labels)

    # Contingency matrix as list of lists with labels.
    table: List[List[Any]] = [[""] + cols_labels]
    for i, rl in enumerate(rows_labels):
        table.append([rl] + [int(observed.iloc[i, j]) for j in range(n_cols)])

    # Row totals.
    row_totals_list = [int(observed.iloc[i].sum()) for i in range(n_rows)]
    row_totals: Dict[str, int] = dict(zip(rows_labels, row_totals_list))

    # Column totals.
    col_totals_list = [int(observed.iloc[:, j].sum()) for j in range(n_cols)]
    col_totals: Dict[str, int] = dict(zip(cols_labels, col_totals_list))

    grand_total = n_total

    # Chi-square test.
    chi2_stat, chi2_p, chi2_dof, expected_raw = sp_stats.chi2_contingency(
        observed.values, correction=False
    )
    expected_table: List[List[Any]] = [[""] + cols_labels]
    for i in range(n_rows):
        expected_table.append(
            [rows_labels[i]] + [round(float(expected_raw[i, j]), 4) for j in range(n_cols)]
        )

    min_expected = float(expected_raw.min())

    # Cramer's V.
    k = min(n_rows, n_cols)
    n_eff = n_total
    cramers_v = (
        float(np.sqrt(chi2_stat / (n_eff * (k - 1)))) if n_eff > 0 and k > 1 else 0.0
    )

    # Percentages.
    row_pcts: List[List[Any]] = [[""] + cols_labels]
    for i, rl in enumerate(rows_labels):
        rt = row_totals_list[i]
        vals = [
            round(observed.iloc[i, j] / rt * 100, 2) if rt > 0 else 0.0
            for j in range(n_cols)
        ]
        row_pcts.append([rl] + vals)

    col_pcts: List[List[Any]] = [[""] + cols_labels]
    for i, rl in enumerate(rows_labels):
        vals = [
            round(observed.iloc[i, j] / col_totals_list[j] * 100, 2)
            if col_totals_list[j] > 0
            else 0.0
            for j in range(n_cols)
        ]
        col_pcts.append([rl] + vals)

    total_pcts: List[List[Any]] = [[""] + cols_labels]
    for i, rl in enumerate(rows_labels):
        vals = [
            round(observed.iloc[i, j] / grand_total * 100, 2)
            if grand_total > 0
            else 0.0
            for j in range(n_cols)
        ]
        total_pcts.append([rl] + vals)

    result: Dict[str, Any] = {
        "row": row,
        "col": col,
        "n": n_total,
        "table": table,
        "row_totals": row_totals,
        "col_totals": col_totals,
        "grand_total": grand_total,
        "expected": expected_table,
        "percentages": {
            "row": row_pcts,
            "col": col_pcts,
            "total": total_pcts,
        },
        "chi2": round(float(chi2_stat), 4),
        "df": int(chi2_dof),
        "p_value": float(chi2_p),
        "cramers_v": round(cramers_v, 4),
        "min_expected": round(min_expected, 4),
    }

    # Fisher's exact for 2x2 tables.
    if n_rows == 2 and n_cols == 2:
        try:
            odds_ratio, fisher_p = sp_stats.fisher_exact(observed.values)
            result["fisher_exact"] = {
                "odds_ratio": round(float(odds_ratio), 4),
                "p_value": float(fisher_p),
            }
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _round(value: float, decimals: int = 4) -> float:
    """Safely round a float, returning 0.0 for NaN/Inf."""
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return round(float(value), decimals)


# ---------------------------------------------------------------------------
# Normality Exploration (Explore)
# ---------------------------------------------------------------------------


def explore(
    df: pd.DataFrame,
    column: str,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform normality diagnostics for a numeric column.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    column : str
        Column to analyse.
    group_col : str, optional
        If provided, diagnostics are run per group.

    Returns
    -------
    dict
        With keys ``column``, ``n``, ``missing``, ``descriptives``,
        ``normality_tests`` (Shapiro-Wilk, skewness, kurtosis with z-scores),
        ``outliers``, and ``interpretation``.
    """
    if column not in df.columns:
        return error(f"Column '{column}' not found in DataFrame.")

    series = df[column]
    if not pd.api.types.is_numeric_dtype(series):
        return error(f"Column '{column}' is not numeric.")

    clean = series.dropna()
    n = len(clean)
    missing = int(series.isna().sum())

    if n < 3:
        return error("Insufficient non-missing data (need at least 3 values).")

    arr = clean.to_numpy(dtype=float)

    if group_col is not None and group_col in df.columns:
        # Per-group exploration.
        groups_result = {}
        for grp_name, grp_series in clean.groupby(df.loc[clean.index, group_col]):
            groups_result[str(grp_name)] = explore(df.loc[grp_series.index], column, group_col=None)
        return {
            "column": column,
            "n": n,
            "missing": missing,
            "group_col": group_col,
            "groups": groups_result,
        }

    # Descriptives.
    from scipy import stats as sp_stats

    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    variance_val = float(np.var(arr, ddof=1)) if n > 1 else 0.0
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    range_val = max_val - min_val
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    # Skewness and Kurtosis with SE.
    skew_val = float(sp_stats.skew(arr, bias=False)) if n > 2 else 0.0
    kurt_val = float(sp_stats.kurtosis(arr, bias=False)) if n > 3 else 0.0
    skew_se = float(np.sqrt(6.0 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))) if n > 2 else None
    kurt_se = float(2.0 * skew_se * np.sqrt((n**2 - 1) / ((n - 3) * (n + 5)))) if skew_se and n > 3 else None
    skew_z = float(skew_val / skew_se) if skew_se and skew_se != 0 else None
    kurt_z = float(kurt_val / kurt_se) if kurt_se and kurt_se != 0 else None

    # Shapiro-Wilk test.
    try:
        shapiro_stat, shapiro_p = sp_stats.shapiro(arr)
    except Exception:
        shapiro_stat, shapiro_p = None, None

    # Kolmogorov-Smirnov (against normal).
    try:
        ks_stat, ks_p = sp_stats.kstest(arr, "norm", args=(mean_val, std_val))
    except Exception:
        ks_stat, ks_p = None, None

    # Outlier detection (Tukey's fences).
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers_low = [float(x) for x in arr if x < lower_fence]
    outliers_high = [float(x) for x in arr if x > upper_fence]
    n_outliers = len(outliers_low) + len(outliers_high)

    # Percentiles.
    percentiles = {}
    for p in [5, 10, 25, 50, 75, 90, 95]:
        percentiles[str(p)] = round(float(np.percentile(arr, p)), 4)

    descriptives = {
        "mean": _round(mean_val),
        "median": _round(median_val),
        "std": _round(std_val),
        "variance": _round(variance_val),
        "min": _round(min_val),
        "max": _round(max_val),
        "range": _round(range_val),
        "q1": _round(q1),
        "q3": _round(q3),
        "iqr": _round(iqr),
    }

    normality = {
        "shapiro_wilk": {
            "statistic": _round(shapiro_stat) if shapiro_stat is not None else None,
            "p_value": float(shapiro_p) if shapiro_p is not None else None,
            "normal": bool(shapiro_p > 0.05) if shapiro_p is not None else None,
        },
        "kolmogorov_smirnov": {
            "statistic": _round(ks_stat) if ks_stat is not None else None,
            "p_value": float(ks_p) if ks_p is not None else None,
        },
        "skewness": {
            "value": _round(skew_val),
            "se": _round(skew_se) if skew_se is not None else None,
            "z_score": _round(skew_z) if skew_z is not None else None,
            "interpretation": _interpret_skewness(skew_z) if skew_z is not None else "unknown",
        },
        "kurtosis": {
            "value": _round(kurt_val),
            "se": _round(kurt_se) if kurt_se is not None else None,
            "z_score": _round(kurt_z) if kurt_z is not None else None,
            "interpretation": _interpret_kurtosis(kurt_z) if kurt_z is not None else "unknown",
        },
    }

    outliers = {
        "method": "Tukey's fences (1.5 × IQR)",
        "lower_fence": _round(lower_fence),
        "upper_fence": _round(upper_fence),
        "n_outliers": n_outliers,
        "pct_outliers": round(n_outliers / n * 100, 2) if n > 0 else 0.0,
        "outliers_low": outliers_low if len(outliers_low) <= 20 else outliers_low[:20],
        "outliers_high": outliers_high if len(outliers_high) <= 20 else outliers_high[:20],
    }

    # Histogram data for stem-and-leaf or histogram.
    hist_counts, hist_bins = np.histogram(arr, bins="auto")
    histogram = [
        {"bin_start": round(float(hist_bins[i]), 4), "bin_end": round(float(hist_bins[i + 1]), 4), "count": int(hist_counts[i])}
        for i in range(len(hist_counts))
    ]

    interpretation = _interpret_explore(normality, n, column)

    return {
        "column": column,
        "n": n,
        "missing": missing,
        "descriptives": descriptives,
        "normality_tests": normality,
        "percentiles": percentiles,
        "outliers": outliers,
        "histogram": histogram,
        "interpretation": interpretation,
    }


def _interpret_skewness(z: Optional[float]) -> str:
    """Interpret skewness z-score."""
    if z is None:
        return "unknown"
    az = abs(z)
    if az < 1.96:
        return "approximately symmetric (not significantly skewed)"
    return "significantly skewed"


def _interpret_kurtosis(z: Optional[float]) -> str:
    """Interpret kurtosis z-score."""
    if z is None:
        return "unknown"
    az = abs(z)
    if az < 1.96:
        return "mesokurtic (not significantly different from normal)"
    if z > 0:
        return "leptokurtic (significantly heavier tails than normal)"
    return "platykurtic (significantly lighter tails than normal)"


def _interpret_explore(normality: Dict, n: int, column: str) -> str:
    """Generate plain-English interpretation for explore output."""
    parts = [f"Normality diagnostics for '{column}' (n = {n}). "]

    sw = normality.get("shapiro_wilk", {})
    sw_p = sw.get("p_value")
    if sw_p is not None:
        parts.append(
            f"Shapiro-Wilk test: W = {sw.get('statistic')}, p = {sw_p:.4f} — "
            f"{'the data does not significantly deviate from normality' if sw_p > 0.05 else 'the data deviates significantly from normality'}. "
        )

    skew = normality.get("skewness", {})
    if skew.get("z_score") is not None:
        parts.append(
            f"Skewness = {skew.get('value')} (z = {skew.get('z_score')}), "
            f"{skew.get('interpretation')}. "
        )

    kurt = normality.get("kurtosis", {})
    if kurt.get("z_score") is not None:
        parts.append(
            f"Kurtosis = {kurt.get('value')} (z = {kurt.get('z_score')}), "
            f"{kurt.get('interpretation')}. "
        )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Grouped Means (Means)
# ---------------------------------------------------------------------------


def means(
    df: pd.DataFrame,
    dependent: str,
    group: Optional[str] = None,
    layers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute grouped means with confidence intervals.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Dependent variable column name.
    group : str, optional
        Primary grouping variable.
    layers : list of str, optional
        Additional layer (stratification) variables for multi-way means.

    Returns
    -------
    dict
        With keys ``dependent``, ``overall``, ``grouped``, ``anova``, and
        ``interpretation``.
    """
    if dependent not in df.columns:
        return error(f"Column '{dependent}' not found in DataFrame.")

    if not pd.api.types.is_numeric_dtype(df[dependent]):
        return error(f"Column '{dependent}' is not numeric.")

    cols = [dependent]
    if group is not None:
        if group not in df.columns:
            return error(f"Group column '{group}' not found in DataFrame.")
        cols.append(group)
    if layers:
        for layer in layers:
            if layer not in df.columns:
                return error(f"Layer column '{layer}' not found in DataFrame.")
            cols.extend([l for l in layers if l in df.columns])

    df_clean = df[cols].dropna()
    n = len(df_clean)

    # Overall descriptives.
    overall = _mean_ci(df_clean[dependent])
    overall["n"] = n

    result: Dict[str, Any] = {
        "dependent": dependent,
        "n": n,
        "overall": overall,
    }

    # Grouped means.
    if group is not None:
        grouped = {}
        for grp_val, grp_data in df_clean.groupby(group):
            grp_series = grp_data[dependent]
            desc = _mean_ci(grp_series)
            desc["n"] = len(grp_series)
            grouped[str(grp_val)] = desc

        result["group_col"] = group
        result["grouped"] = grouped

        # One-way ANOVA for the grouping.
        group_vals = [df_clean.loc[df_clean[group] == g, dependent].dropna() for g in df_clean[group].unique()]
        if len(group_vals) >= 2 and all(len(gv) >= 2 for gv in group_vals):
            f_stat, p_val = sp_stats.f_oneway(*group_vals)
            result["anova"] = {
                "f": round(float(f_stat), 4),
                "p_value": float(p_val),
                "significant": bool(p_val < 0.05),
                "interpretation": f"The group means {'differ significantly' if p_val < 0.05 else 'do not differ significantly'} (p = {p_val:.4f}).",
            }
        else:
            result["anova"] = None

    interpretation = _interpret_means(result)
    result["interpretation"] = interpretation

    return result


def _interpret_means(result: Dict) -> str:
    """Generate plain-English interpretation for means output."""
    dep = result.get("dependent", "variable")
    overall = result.get("overall", {})
    n = result.get("n", 0)

    parts = [f"Mean analysis for '{dep}' (n = {n}). "]
    parts.append(
        f"Overall: M = {overall.get('mean', 'N/A')}, "
        f"SD = {overall.get('sd', 'N/A')}, "
        f"95% CI [{overall.get('ci_lower', 'N/A')}, {overall.get('ci_upper', 'N/A')}]. "
    )

    if "grouped" in result:
        group_col = result.get("group_col", "group")
        parts.append(f"Group means by '{group_col}': ")
        for grp, desc in result["grouped"].items():
            parts.append(
                f"  {grp}: M = {desc.get('mean', 'N/A')}, "
                f"SD = {desc.get('sd', 'N/A')}, "
                f"n = {desc.get('n', 'N/A')}, "
                f"95% CI [{desc.get('ci_lower', 'N/A')}, {desc.get('ci_upper', 'N/A')}]. "
            )

        anova = result.get("anova")
        if anova:
            parts.append(anova.get("interpretation", ""))

    return "".join(parts)
