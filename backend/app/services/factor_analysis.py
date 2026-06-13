"""
Factor Analysis and Reliability service for DevStat.

Provides functions for exploratory factor analysis (EFA) via
``factor_analyzer`` and Cronbach's alpha reliability analysis
via ``pingouin``.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from app.services import error


# ---------------------------------------------------------------------------
# Factor Analysis
# ---------------------------------------------------------------------------


def factor_analysis(
    df: pd.DataFrame,
    columns: List[str],
    n_factors: int = 2,
    rotation: str = "varimax",
) -> Dict[str, Any]:
    """Perform exploratory factor analysis (EFA).

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str
        Column names for the variables to include.
    n_factors : int
        Number of factors to extract (default 2).
    rotation : str
        Rotation method: ``'varimax'``, ``'promax'``, ``'oblimin'``,
        ``'quartimax'``, or ``None``.

    Returns
    -------
    dict
        With keys ``loadings``, ``eigenvalues``, ``variance_explained``,
        ``communalities``, ``rotation``, ``n_factors``, ``kmo``,
        ``bartlett``, and ``interpretation``.
    """
    # Validate columns.
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    df_clean = df[columns].dropna()
    n = len(df_clean)

    if n < 5:
        return error("Insufficient data (need at least 5 complete cases).")

    k = len(columns)
    if n_factors < 1:
        n_factors = 1
    if n_factors > k:
        return error(f"Number of factors ({n_factors}) cannot exceed number of variables ({k}).")

    try:
        from factor_analyzer import FactorAnalyzer
        from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo
    except ImportError:
        return error("factor_analyzer library is not installed. pip install factor-analyzer")

    # Bartlett's test of sphericity and KMO.
    try:
        chi2, bartlett_p = calculate_bartlett_sphericity(df_clean)
        kmo_all, kmo_model = calculate_kmo(df_clean)
    except Exception as e:
        return error(f"Failed to compute KMO / Bartlett: {e}")

    # Fit factor analyzer.
    try:
        fa = FactorAnalyzer(n_factors=n_factors, rotation=rotation)
        fa.fit(df_clean)
    except Exception as e:
        return error(f"Factor analysis failed: {e}")

    # Loadings.
    loadings_df = pd.DataFrame(
        fa.loadings_,
        index=columns,
        columns=[f"Factor {i+1}" for i in range(n_factors)],
    )
    loadings = []
    for var in columns:
        row = {"variable": var}
        for i in range(n_factors):
            row[f"factor_{i+1}"] = round(float(loadings_df.iloc[columns.index(var), i]), 4)
        loadings.append(row)

    # Eigenvalues (from correlation matrix).
    corr = df_clean.corr()
    eigenvalues_raw = np.linalg.eigvals(corr.values)
    eigenvalues = sorted([float(v.real) for v in eigenvalues_raw], reverse=True)

    # Variance explained.
    variance_explained = []
    cum_var = 0.0
    total_var = sum(eigenvalues)
    for i, ev in enumerate(eigenvalues[:k]):
        prop = float(ev / total_var * 100) if total_var > 0 else 0.0
        cum_var += prop
        variance_explained.append({
            "factor": i + 1,
            "eigenvalue": round(ev, 4),
            "variance_pct": round(prop, 2),
            "cumulative_pct": round(cum_var, 2),
        })

    # Communalities.
    communalities = [
        {"variable": columns[i], "communality": round(float(fa.get_communalities()[i]), 4)}
        for i in range(k)
    ]

    # Interpretation.
    interpretation = _interpret_factor_analysis(loadings, variance_explained, n_factors, rotation, kmo_model, bartlett_p)

    return {
        "loadings": loadings,
        "eigenvalues": eigenvalues[:k],
        "variance_explained": variance_explained,
        "communalities": communalities,
        "rotation": rotation or "none",
        "n_factors": n_factors,
        "n_variables": k,
        "n_observations": n,
        "kmo": {
            "model": round(float(kmo_model), 4),
            "interpretation": _interpret_kmo(kmo_model),
        },
        "bartlett": {
            "chi2": round(float(chi2), 4),
            "df": int(k * (k - 1) / 2),
            "p_value": float(bartlett_p),
        },
        "interpretation": interpretation,
    }


def _interpret_kmo(kmo: float) -> str:
    """Verbal label for KMO measure of sampling adequacy."""
    if kmo >= 0.9:
        return "marvelous"
    if kmo >= 0.8:
        return "meritorious"
    if kmo >= 0.7:
        return "middling"
    if kmo >= 0.6:
        return "mediocre"
    if kmo >= 0.5:
        return "miserable"
    return "unacceptable"


def _interpret_factor_analysis(
    loadings: List[Dict],
    variance_explained: List[Dict],
    n_factors: int,
    rotation: str,
    kmo: float,
    bartlett_p: float,
) -> str:
    """Generate plain-English interpretation for factor analysis."""
    parts = []
    parts.append(
        f"An exploratory factor analysis with {rotation or 'no'} rotation was performed "
        f"on {len(loadings)} variables using principal axis factoring. "
    )
    parts.append(
        f"KMO measure of sampling adequacy was {kmo:.3f} ({_interpret_kmo(kmo)}), "
        f"and Bartlett's test of sphericity was {'significant' if bartlett_p < 0.05 else 'not significant'} "
        f"(p = {bartlett_p:.4f}), "
        f"{'supporting' if bartlett_p < 0.05 else 'not supporting'} the suitability of the data for factor analysis. "
    )

    total_var = variance_explained[-1]["cumulative_pct"] if variance_explained else 0.0
    parts.append(
        f"The {n_factors}-factor solution explained {total_var:.2f}% of the total variance. "
    )

    # Summarise loadings per factor.
    for f_idx in range(n_factors):
        factor_loads = []
        for row in loadings:
            key = f"factor_{f_idx+1}"
            val = row.get(key, 0)
            if abs(val) >= 0.4:
                direction = "+" if val > 0 else "-"
                factor_loads.append(f"{row['variable']} ({direction}{abs(val):.2f})")
        if factor_loads:
            parts.append(
                f"Factor {f_idx+1} loaded on: {', '.join(factor_loads)}. "
            )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Reliability (Cronbach's Alpha)
# ---------------------------------------------------------------------------


def reliability_analysis(
    df: pd.DataFrame,
    columns: List[str],
) -> Dict[str, Any]:
    """Compute Cronbach's alpha and item-level reliability statistics.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str
        Column names of the scale items.

    Returns
    -------
    dict
        With keys ``alpha``, ``alpha_ci``, ``n_items``, ``n_observations``,
        ``item_stats`` (item-total correlations, alpha-if-deleted),
        and ``interpretation``.
    """
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    df_clean = df[columns].dropna()
    n = len(df_clean)
    k = len(columns)

    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")
    if k < 2:
        return error("Need at least 2 items for reliability analysis.")

    try:
        import pingouin as pg
    except ImportError:
        # Fallback using scipy/numpy.
        return _reliability_fallback(df_clean, columns)

    # Compute Cronbach's alpha via pingouin.
    alpha_result = pg.cronbach_alpha(data=df_clean, items=columns)
    alpha = round(float(alpha_result[0]), 4)
    alpha_ci = alpha_result[1] if len(alpha_result) > 1 else [alpha, alpha]

    # Item statistics.
    item_stats = []
    for i, col in enumerate(columns):
        # Item-total correlation (without this item).
        other_cols = [c for j, c in enumerate(columns) if j != i]
        if other_cols:
            total_other = df_clean[other_cols].sum(axis=1)
            item_total_r = round(float(df_clean[col].corr(total_other)), 4)
        else:
            item_total_r = 0.0

        # Alpha if item deleted.
        if len(other_cols) >= 2:
            alpha_del = pg.cronbach_alpha(data=df_clean, items=other_cols)
            alpha_if_deleted = round(float(alpha_del[0]), 4)
        else:
            alpha_if_deleted = None

        item_stats.append({
            "item": col,
            "mean": round(float(df_clean[col].mean()), 4),
            "sd": round(float(df_clean[col].std(ddof=1)), 4),
            "item_total_correlation": item_total_r,
            "alpha_if_deleted": alpha_if_deleted,
        })

    return {
        "alpha": alpha,
        "alpha_ci": [round(float(alpha_ci[0]), 4), round(float(alpha_ci[1]), 4)],
        "n_items": k,
        "n_observations": n,
        "item_stats": item_stats,
        "interpretation": _interpret_alpha(alpha),
    }


def _reliability_fallback(df_clean: pd.DataFrame, columns: List[str]) -> Dict[str, Any]:
    """Compute Cronbach's alpha using scipy/numpy directly."""
    from scipy import stats as sp_stats

    k = len(columns)
    n = len(df_clean)
    scores = df_clean[columns].values

    # Cronbach's alpha: (k / (k-1)) * (1 - sum(variances) / variance of total)
    item_variances = np.var(scores, axis=0, ddof=1)
    total_scores = np.sum(scores, axis=1)
    total_variance = np.var(total_scores, ddof=1)

    if total_variance == 0:
        return error("Total score variance is zero — cannot compute alpha.")

    alpha_coef = (k / (k - 1)) * (1 - np.sum(item_variances) / total_variance)
    alpha = round(float(alpha_coef), 4)

    # Approximate CI using Feldt formula.
    import math
    f_crit = sp_stats.f.ppf(0.975, n - 1, (n - 1) * (k - 1))
    alpha_lower = round(float(1 - (1 - alpha) * f_crit), 4)
    f_crit_u = sp_stats.f.ppf(0.025, n - 1, (n - 1) * (k - 1))
    alpha_upper = round(float(1 - (1 - alpha) * f_crit_u), 4)

    # Item statistics.
    item_stats = []
    for i, col in enumerate(columns):
        other_cols = [c for j, c in enumerate(columns) if j != i]
        if other_cols:
            total_other = df_clean[other_cols].sum(axis=1)
            item_total_r = round(float(df_clean[col].corr(total_other)), 4)
        else:
            item_total_r = 0.0

        # Alpha if deleted.
        if len(other_cols) >= 2:
            other_scores = df_clean[other_cols].values
            o_var = np.var(other_scores, axis=0, ddof=1)
            o_total = np.sum(other_scores, axis=1)
            o_totvar = np.var(o_total, ddof=1)
            if o_totvar > 0 and len(other_cols) > 1:
                a_del = (len(other_cols) / (len(other_cols) - 1)) * (1 - np.sum(o_var) / o_totvar)
                alpha_if_deleted = round(float(a_del), 4)
            else:
                alpha_if_deleted = None
        else:
            alpha_if_deleted = None

        item_stats.append({
            "item": col,
            "mean": round(float(df_clean[col].mean()), 4),
            "sd": round(float(df_clean[col].std(ddof=1)), 4),
            "item_total_correlation": item_total_r,
            "alpha_if_deleted": alpha_if_deleted,
        })

    return {
        "alpha": alpha,
        "alpha_ci": [alpha_lower, alpha_upper],
        "n_items": k,
        "n_observations": n,
        "item_stats": item_stats,
        "interpretation": _interpret_alpha(alpha),
    }


def _interpret_alpha(alpha: float) -> str:
    """Interpret Cronbach's alpha value."""
    if alpha >= 0.9:
        return "Excellent internal consistency (α ≥ 0.9). The scale shows very high reliability."
    if alpha >= 0.8:
        return "Good internal consistency (α ≥ 0.8). The scale demonstrates adequate reliability for research purposes."
    if alpha >= 0.7:
        return "Acceptable internal consistency (α ≥ 0.7). The scale meets the minimum threshold for reliability."
    if alpha >= 0.6:
        return "Questionable internal consistency (α ≥ 0.6). Consider revising or removing items to improve reliability."
    if alpha >= 0.5:
        return "Poor internal consistency (α ≥ 0.5). The scale needs substantial revision."
    return "Unacceptable internal consistency (α < 0.5). The items do not reliably measure a common construct."
