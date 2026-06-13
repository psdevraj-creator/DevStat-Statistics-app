"""
Regression service for DevStat.

Provides functions for linear regression, logistic regression, and
correlation matrices, each returning structured dicts with parameters,
model fit statistics, and interpretation text.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from app.services import error


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _round(value: float, decimals: int = 4) -> float:
    """Round a float to *decimals* places, preserving None."""
    if value is None:
        return None
    return round(float(value), decimals)


def _p_value(p: float) -> Dict[str, Any]:
    """Return structured p-value info."""
    if p < 0.001:
        return {"value": p, "label": "p < 0.001", "sig": "***"}
    if p < 0.01:
        return {"value": _round(p), "label": f"p = {p:.3f}", "sig": "**"}
    if p < 0.05:
        return {"value": _round(p), "label": f"p = {p:.3f}", "sig": "*"}
    return {"value": _round(p), "label": f"p = {p:.3f}", "sig": "ns"}


def _std_beta(coef: float, x_std: float, y_std: float) -> float:
    """Standardised beta coefficient."""
    if y_std == 0 or x_std == 0:
        return 0.0
    return float(coef * x_std / y_std)


# ---------------------------------------------------------------------------
# Linear Regression
# ---------------------------------------------------------------------------


def _ols_anova_table(result: sm.regression.linear_model.RegressionResultsWrapper) -> Dict[str, Any]:
    """Build an ANOVA table from an OLS result."""
    from statsmodels.stats.anova import anova_lm
    try:
        anova = anova_lm(result, typ=2)
        table = []
        for row_name in anova.index:
            row = anova.loc[row_name]
            table.append({
                "source": str(row_name),
                "df": int(row["df"]) if "df" in row else None,
                "sum_sq": _round(row["sum_sq"]) if "sum_sq" in row else None,
                "mean_sq": _round(row["mean_sq"]) if "mean_sq" in row else None,
                "f": _round(row["F"]) if "F" in row else None,
                "p_value": _round(row["PR(>F)"]) if "PR(>F)" in row else None,
            })
        return {"anova_table": table}
    except Exception:
        return {"anova_table": [], "note": "ANOVA table could not be computed (likely single-predictor model handled internally)."}


def _stepwise_selection(
    df: pd.DataFrame,
    dependent: str,
    independents: List[str],
    method: str,
    p_enter: float = 0.05,
    p_remove: float = 0.10,
) -> List[str]:
    """Simple stepwise selection based on p-value thresholds."""
    selected = []
    remaining = list(independents)
    changed = True

    while changed:
        changed = False

        # Forward step: add best candidate not yet in model.
        if method in ("forward", "stepwise") and remaining:
            best_p = float("inf")
            best_var = None
            for var in remaining:
                candidates = selected + [var]
                X = df[candidates]
                X = sm.add_constant(X)
                y = df[dependent]
                try:
                    model = sm.OLS(y, X).fit()
                    p_val = model.pvalues.get(var, 1.0)
                except Exception:
                    continue
                if p_val < best_p:
                    best_p = p_val
                    best_var = var
            if best_var is not None and best_p < p_enter:
                selected.append(best_var)
                remaining.remove(best_var)
                changed = True

        # Backward step: remove worst variable currently in model.
        if method in ("backward", "stepwise") and len(selected) > 0:
            X = df[selected]
            try:
                X = sm.add_constant(X)
                y = df[dependent]
                model = sm.OLS(y, X).fit()
            except Exception:
                break
            worst_p = 0.0
            worst_var = None
            for var in selected:
                p_val = model.pvalues.get(var, 0.0)
                if p_val > worst_p:
                    worst_p = p_val
                    worst_var = var
            if worst_var is not None and worst_p > p_remove:
                selected.remove(worst_var)
                changed = True

    return selected


def linear_regression(
    df: pd.DataFrame,
    dependent: str,
    independents: List[str],
    method: str = "enter",
) -> Dict[str, Any]:
    """Perform ordinary least squares (linear) regression.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Name of the dependent (outcome) variable.
    independents : list of str
        Names of the independent (predictor) variables.
    method : str, optional
        Variable entry method: ``'enter'`` (default, all variables),
        ``'forward'``, ``'backward'``, or ``'stepwise'``.

    Returns
    -------
    dict
        With keys ``coefficients``, ``model_summary``, ``anova_table``,
        ``residuals_notes``, and ``interpretation``.
    """
    # Validate columns.
    for col in [dependent] + independents:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    # Drop rows with missing in any used column.
    all_cols = [dependent] + independents
    df_clean = df[all_cols].dropna()
    # Coerce all columns to numeric
    for col in [dependent] + independents:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    df_clean = df_clean.dropna()
    n = len(df_clean)

    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")

    # Stepwise variable selection.
    if method != "enter":
        selected = _stepwise_selection(df_clean, dependent, independents, method)
        if not selected:
            return error("No variables met entry criteria in stepwise selection.")
        independents = selected
    else:
        independents = list(independents)

    # Build and fit model.
    X = df_clean[independents].astype(float)
    y = df_clean[dependent].astype(float)
    X = sm.add_constant(X)

    model = sm.OLS(y, X).fit()

    # Coefficients table.
    n_vars = len(independents)
    y_std = y.std(ddof=1)
    coefficients = []
    const_idx = 0
    for i, var in enumerate(["const"] + independents):
        coef = model.params[var]
        se = model.bse[var]
        t_val = model.tvalues[var]
        p_val = model.pvalues[var]
        ci = model.conf_int().loc[var].values

        # Standardised beta.
        if var == "const":
            sb = None
        else:
            x_std = df_clean[var].std(ddof=1)
            sb = _round(_std_beta(coef, x_std, y_std))

        coefficients.append({
            "name": var,
            "coef": _round(coef),
            "se": _round(se),
            "t": _round(t_val),
            "p": _round(p_val),
            "p_label": _p_value(p_val),
            "ci_lower": _round(ci[0]),
            "ci_upper": _round(ci[1]),
            "std_beta": sb,
        })

    # Model summary.
    r_sq = model.rsquared
    adj_r_sq = model.rsquared_adj
    f_stat = model.fvalue
    f_p = model.f_pvalue
    aic = model.aic
    bic = model.bic

    model_summary = {
        "r_squared": _round(r_sq),
        "adj_r_squared": _round(adj_r_sq),
        "f_stat": _round(f_stat),
        "f_p": _round(f_p),
        "f_p_label": _p_value(f_p),
        "aic": _round(aic),
        "bic": _round(bic),
        "n": n,
        "n_predictors": len(independents),
        "method": method,
        "dependent": dependent,
        "independents": independents,
    }

    # ANOVA table.
    anova = _ols_anova_table(model)

    # Residual diagnostics notes.
    residuals = model.resid
    standardized_residuals = model.get_influence().resid_studentized_internal
    shapiro_stat, shapiro_p = sp_stats.shapiro(residuals)
    # Durbin-Watson.
    dw = sm.stats.stattools.durbin_watson(residuals)

    residuals_notes = {
        "normality": {
            "test": "Shapiro-Wilk",
            "statistic": _round(shapiro_stat),
            "p": _round(shapiro_p),
            "p_label": _p_value(shapiro_p),
            "interpretation": "Residuals appear normally distributed" if shapiro_p > 0.05 else "Residuals deviate from normality",
        },
        "durbin_watson": {
            "statistic": _round(dw),
            "interpretation": "No significant autocorrelation" if 1.5 < dw < 2.5 else "Possible autocorrelation detected",
        },
        "n_outliers_std_resid_gt_3": int(np.sum(np.abs(standardized_residuals) > 3)),
    }

    # Interpretation.
    interp = _interpret_linear(coefficients, model_summary)

    return {
        "coefficients": coefficients,
        "model_summary": model_summary,
        "anova_table": anova,
        "residuals_notes": residuals_notes,
        "interpretation": interp,
    }


def _interpret_linear(coefficients: List[Dict], summary: Dict) -> str:
    """Generate plain-English interpretation for linear regression."""
    parts = []
    r2 = summary["r_squared"]
    f_p_lab = summary.get("f_p_label", {})
    f_lab = f_p_lab.get("label", "")

    parts.append(
        f"A linear regression was performed with {summary['dependent']} as the "
        f"dependent variable and {summary['n_predictors']} predictor(s) "
        f"({', '.join(summary['independents'])}). "
    )
    parts.append(
        f"The overall model was "
        f"{'statistically significant' if f_p_lab.get('sig','ns') != 'ns' else 'not statistically significant'}, "
        f"F({summary['n_predictors']}, {summary['n'] - summary['n_predictors'] - 1}) = {summary['f_stat']}, "
        f"{f_lab}. "
    )
    parts.append(
        f"The model explained {r2 * 100:.1f}% of the variance in the outcome "
        f"(adjusted R² = {summary['adj_r_squared']})."
    )

    # Significant predictors.
    sig_vars = [c for c in coefficients if c["name"] != "const" and c.get("p", 1) < 0.05]
    if sig_vars:
        parts.append("Significant predictors:")
        for c in sig_vars:
            sb = c.get("std_beta")
            sb_str = f", β = {sb}" if sb is not None else ""
            parts.append(
                f"  • {c['name']}: B = {c['coef']} (SE = {c['se']}), "
                f"t = {c['t']}, {c.get('p_label', {}).get('label', '')}{sb_str}"
            )
    else:
        parts.append("No individual predictors reached statistical significance (p < 0.05).")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Logistic Regression
# ---------------------------------------------------------------------------


def _classification_table(
    observed: pd.Series,
    predicted: pd.Series,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """Build a classification table (confusion matrix) for a binary classifier."""
    pred_class = (predicted >= threshold).astype(int)
    tp = int(((observed == 1) & (pred_class == 1)).sum())
    tn = int(((observed == 0) & (pred_class == 0)).sum())
    fp = int(((observed == 0) & (pred_class == 1)).sum())
    fn = int(((observed == 1) & (pred_class == 0)).sum())
    n = len(observed)
    accuracy = (tp + tn) / n if n > 0 else 0.0
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "accuracy": _round(accuracy),
        "sensitivity": _round(sensitivity),
        "specificity": _round(specificity),
        "ppv": _round(ppv),
        "npv": _round(npv),
        "threshold": threshold,
    }


def logistic_regression(
    df: pd.DataFrame,
    dependent: str,
    independents: List[str],
    method: str = "enter",
) -> Dict[str, Any]:
    """Perform binary logistic regression.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Name of the binary dependent (outcome) variable.
    independents : list of str
        Names of the independent (predictor) variables.
    method : str, optional
        Variable entry method: ``'enter'`` (default), ``'forward'``,
        ``'backward'``, or ``'stepwise'``.

    Returns
    -------
    dict
        With keys ``coefficients``, ``model_summary``,
        ``classification_table``, and ``interpretation``.
    """
    # Validate columns.
    for col in [dependent] + independents:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    all_cols = [dependent] + independents
    df_clean = df[all_cols].dropna()
    # Coerce all columns to numeric
    for col in [dependent] + independents:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    df_clean = df_clean.dropna()
    n = len(df_clean)

    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")

    # Stepwise variable selection (same p-value approach for logistic).
    if method != "enter":
        selected = _stepwise_selection_logistic(df_clean, dependent, independents, method)
        if not selected:
            return error("No variables met entry criteria in stepwise selection.")
        independents = selected
    else:
        independents = list(independents)

    # Build and fit model.
    X = df_clean[independents].astype(float)
    y = df_clean[dependent].astype(float)
    X = sm.add_constant(X)

    try:
        model = sm.Logit(y, X).fit(disp=False)
    except Exception as e:
        return error(f"Logistic regression failed to converge: {str(e)}")

    # Coefficients table with odds ratios.
    params = model.params
    bse = model.bse
    pvals = model.pvalues
    conf_int = model.conf_int()

    coefficients = []
    for var in ["const"] + independents:
        coef = params[var]
        se = bse[var]
        p_val = pvals[var]
        z_val = model.tvalues[var]
        or_val = np.exp(coef)
        ci = conf_int.loc[var].values
        or_ci_lower = float(np.exp(ci[0]))
        or_ci_upper = float(np.exp(ci[1]))

        coefficients.append({
            "name": var,
            "coef": _round(coef),
            "se": _round(se),
            "z": _round(z_val),
            "p": _round(p_val),
            "p_label": _p_value(p_val),
            "or": _round(or_val),
            "or_ci_lower": _round(or_ci_lower),
            "or_ci_upper": _round(or_ci_upper),
        })

    # Model summary.
    pseudo_r2 = model.prsquared
    llf = model.llf
    ll_null = model.llnull
    lr_stat = model.llr
    lr_p = model.llr_pvalue
    aic = model.aic
    bic = model.bic

    model_summary = {
        "pseudo_r_squared": _round(pseudo_r2),
        "log_likelihood": _round(llf),
        "null_log_likelihood": _round(ll_null),
        "lr_stat": _round(lr_stat),
        "lr_p": _round(lr_p),
        "lr_p_label": _p_value(lr_p),
        "aic": _round(aic),
        "bic": _round(bic),
        "n": n,
        "n_predictors": len(independents),
        "method": method,
        "dependent": dependent,
        "independents": independents,
    }

    # Classification table.
    predicted_probs = model.predict(X)
    class_table = _classification_table(y, predicted_probs)

    # Interpretation.
    interp = _interpret_logistic(coefficients, model_summary, class_table)

    return {
        "coefficients": coefficients,
        "model_summary": model_summary,
        "classification_table": class_table,
        "interpretation": interp,
    }


def _stepwise_selection_logistic(
    df: pd.DataFrame,
    dependent: str,
    independents: List[str],
    method: str,
    p_enter: float = 0.05,
    p_remove: float = 0.10,
) -> List[str]:
    """Stepwise selection for logistic regression based on p-values."""
    selected = []
    remaining = list(independents)
    changed = True

    while changed:
        changed = False

        if method in ("forward", "stepwise") and remaining:
            best_p = float("inf")
            best_var = None
            for var in remaining:
                candidates = selected + [var]
                X = df[candidates]
                X = sm.add_constant(X)
                y = df[dependent]
                try:
                    model = sm.Logit(y, X).fit(disp=False)
                    p_val = model.pvalues.get(var, 1.0)
                except Exception:
                    continue
                if p_val < best_p:
                    best_p = p_val
                    best_var = var
            if best_var is not None and best_p < p_enter:
                selected.append(best_var)
                remaining.remove(best_var)
                changed = True

        if method in ("backward", "stepwise") and len(selected) > 0:
            X = df[selected]
            try:
                X = sm.add_constant(X)
                y = df[dependent]
                model = sm.Logit(y, X).fit(disp=False)
            except Exception:
                break
            worst_p = 0.0
            worst_var = None
            for var in selected:
                p_val = model.pvalues.get(var, 0.0)
                if p_val > worst_p:
                    worst_p = p_val
                    worst_var = var
            if worst_var is not None and worst_p > p_remove:
                selected.remove(worst_var)
                changed = True

    return selected


def _interpret_logistic(
    coefficients: List[Dict],
    summary: Dict,
    class_table: Dict,
) -> str:
    """Generate plain-English interpretation for logistic regression."""
    parts = []
    lr_p_lab = summary.get("lr_p_label", {})
    pseudo_r2 = summary["pseudo_r_squared"]

    parts.append(
        f"A binary logistic regression was performed with {summary['dependent']} as "
        f"the outcome and {summary['n_predictors']} predictor(s) "
        f"({', '.join(summary['independents'])}). "
    )
    parts.append(
        f"The overall model was "
        f"{'statistically significant' if lr_p_lab.get('sig','ns') != 'ns' else 'not statistically significant'}, "
        f"χ²({summary['n_predictors']}) = {summary['lr_stat']}, "
        f"{lr_p_lab.get('label', '')}. "
    )
    parts.append(
        f"Nagelkerke pseudo-R² = {pseudo_r2:.3f}, "
        f"indicating that the model explains approximately {pseudo_r2 * 100:.1f}% "
        f"of the variance in the outcome."
    )

    # Classification accuracy.
    acc = class_table.get("accuracy", 0)
    parts.append(
        f"The model correctly classified {acc * 100:.1f}% of cases "
        f"(sensitivity = {class_table.get('sensitivity', 0) * 100:.1f}%, "
        f"specificity = {class_table.get('specificity', 0) * 100:.1f}%)."
    )

    # Significant predictors.
    sig_vars = [c for c in coefficients if c["name"] != "const" and c.get("p", 1) < 0.05]
    if sig_vars:
        parts.append("Significant predictors (odds ratios with 95% CI):")
        for c in sig_vars:
            parts.append(
                f"  • {c['name']}: OR = {c['or']} "
                f"(95% CI: {c['or_ci_lower']} – {c['or_ci_upper']}), "
                f"z = {c['z']}, {c.get('p_label', {}).get('label', '')}"
            )
    else:
        parts.append("No individual predictors reached statistical significance (p < 0.05).")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Correlation Matrix
# ---------------------------------------------------------------------------


def correlation_matrix(
    df: pd.DataFrame,
    columns: List[str],
    method: str = "pearson",
) -> Dict[str, Any]:
    """Compute a correlation matrix for the given columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str
        Column names to correlate.
    method : str, optional
        Correlation method: ``'pearson'`` (default), ``'spearman'``,
        or ``'kendall'``.

    Returns
    -------
    dict
        With keys ``matrix`` (r values), ``p_values``, ``n`` (pairwise N),
        ``method``, ``columns``, and ``interpretation``.
    """
    # Validate columns.
    for col in columns:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    valid_cols = [c for c in columns if c in df.columns]
    if len(valid_cols) < 2:
        return error("Need at least 2 valid columns for correlation.")

    df_clean = df[valid_cols].dropna()
    # Coerce all columns to numeric, then filter
    for col in valid_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    df_clean = df_clean.dropna()
    n = len(df_clean)

    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")

    k = len(valid_cols)

    if method == "pearson":
        # Use scipy's pearsonr for each pair.
        r_matrix = np.eye(k)
        p_matrix = np.eye(k)
        n_matrix = np.full((k, k), n)
        for i in range(k):
            for j in range(i + 1, k):
                r_val, p_val = sp_stats.pearsonr(df_clean[valid_cols[i]], df_clean[valid_cols[j]])
                r_matrix[i, j] = r_val
                r_matrix[j, i] = r_val
                p_matrix[i, j] = p_val
                p_matrix[j, i] = p_val

    elif method == "spearman":
        r_matrix = np.eye(k)
        p_matrix = np.eye(k)
        n_matrix = np.full((k, k), n)
        for i in range(k):
            for j in range(i + 1, k):
                r_val, p_val = sp_stats.spearmanr(df_clean[valid_cols[i]], df_clean[valid_cols[j]])
                r_matrix[i, j] = r_val
                r_matrix[j, i] = r_val
                p_matrix[i, j] = p_val
                p_matrix[j, i] = p_val

    elif method == "kendall":
        r_matrix = np.eye(k)
        p_matrix = np.eye(k)
        n_matrix = np.full((k, k), n)
        for i in range(k):
            for j in range(i + 1, k):
                r_val, p_val = sp_stats.kendalltau(df_clean[valid_cols[i]], df_clean[valid_cols[j]])
                r_matrix[i, j] = r_val
                r_matrix[j, i] = r_val
                p_matrix[i, j] = p_val
                p_matrix[j, i] = p_val

    else:
        return error(f"Unknown method '{method}'. Use 'pearson', 'spearman', or 'kendall'.")

    # Build serializable matrices.
    matrix_data = []
    pval_data = []
    n_data = []
    for i in range(k):
        matrix_data.append({valid_cols[j]: _round(r_matrix[i, j]) for j in range(k)})
        pval_data.append({valid_cols[j]: _round(p_matrix[i, j]) for j in range(k)})
        n_data.append({valid_cols[j]: int(n_matrix[i, j]) for j in range(k)})

    # Interpretation.
    interp = _interpret_correlation(matrix_data, valid_cols, method)

    return {
        "matrix": matrix_data,
        "p_values": pval_data,
        "n": n_data,
        "columns": valid_cols,
        "method": method,
        "n_complete": n,
        "interpretation": interp,
    }


def _interpret_correlation(matrix: List[Dict], columns: List[str], method: str) -> str:
    """Generate plain-English interpretation for a correlation matrix."""
    method_name = {"pearson": "Pearson", "spearman": "Spearman", "kendall": "Kendall"}.get(method, method)

    parts = [f"A {method_name} correlation matrix was computed for {len(columns)} variables "
             f"({', '.join(columns)})."]

    # Find significant correlations (abs(r) > 0.3 or notable).
    notable = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            r_val = matrix[i].get(columns[j], 0)
            if abs(r_val) >= 0.3:
                direction = "positive" if r_val > 0 else "negative"
                strength = "strong" if abs(r_val) >= 0.7 else ("moderate" if abs(r_val) >= 0.5 else "weak")
                notable.append(f"  • {columns[i]} and {columns[j]}: r = {r_val} ({strength} {direction} correlation)")

    if notable:
        parts.append("Notable correlations observed:")
        parts.extend(notable)
    else:
        parts.append("No notable correlations (|r| ≥ 0.3) were observed among the variables.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Partial Correlation
# ---------------------------------------------------------------------------


def partial_correlation(
    df: pd.DataFrame,
    columns: List[str],
    control: List[str],
    method: str = "pearson",
) -> Dict[str, Any]:
    """Compute partial correlations controlling for one or more covariates.

    Uses ``pingouin.partial_corr``.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    columns : list of str
        Variable names for which to compute pairwise partial correlations.
    control : list of str
        Covariate(s) to control for.
    method : str
        ``'pearson'`` (default) or ``'spearman'``.

    Returns
    -------
    dict
        With keys ``matrix``, ``p_values``, ``columns``, ``control_vars``,
        ``method``, ``n``, and ``interpretation``.
    """
    # Validate columns.
    all_cols = columns + control
    for col in all_cols:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    if len(columns) < 2:
        return error("Need at least 2 variables for partial correlation.")
    if len(control) < 1:
        return error("Need at least 1 control variable for partial correlation.")

    df_clean = df[all_cols].dropna()
    n = len(df_clean)

    if n < 5:
        return error("Insufficient data (need at least 5 complete cases).")

    try:
        import pingouin as pg
    except ImportError:
        return error("pingouin library is not installed. pip install pingouin")

    k = len(columns)
    r_matrix = np.eye(k)
    p_matrix = np.eye(k)

    for i in range(k):
        for j in range(i + 1, k):
            try:
                pc = pg.partial_corr(
                    data=df_clean,
                    x=columns[i],
                    y=columns[j],
                    covar=control,
                    method=method,
                )
                r_val = float(pc["r"].values[0])
                p_val = float(pc["p-val"].values[0])
            except Exception:
                r_val = 0.0
                p_val = 1.0
            r_matrix[i, j] = r_val
            r_matrix[j, i] = r_val
            p_matrix[i, j] = p_val
            p_matrix[j, i] = p_val

    # Build serializable matrices.
    matrix_data = []
    pval_data = []
    for i in range(k):
        matrix_data.append({columns[j]: _round(r_matrix[i, j]) for j in range(k)})
        pval_data.append({columns[j]: _round(p_matrix[i, j]) for j in range(k)})

    interpretation = _interpret_partial_correlation(matrix_data, columns, control, method)

    return {
        "matrix": matrix_data,
        "p_values": pval_data,
        "columns": columns,
        "control_vars": control,
        "method": method,
        "n": n,
        "interpretation": interpretation,
    }


def _interpret_partial_correlation(
    matrix: List[Dict],
    columns: List[str],
    control: List[str],
    method: str,
) -> str:
    """Generate plain-English interpretation for partial correlations."""
    method_name = {"pearson": "Pearson", "spearman": "Spearman"}.get(method, method)
    parts = [
        f"A {method_name} partial correlation analysis was performed for "
        f"{len(columns)} variables ({', '.join(columns)}), "
        f"controlling for {', '.join(control)}. "
    ]

    notable = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            r_val = matrix[i].get(columns[j], 0)
            if abs(r_val) >= 0.3:
                direction = "positive" if r_val > 0 else "negative"
                strength = "strong" if abs(r_val) >= 0.7 else ("moderate" if abs(r_val) >= 0.5 else "weak")
                notable.append(f"  • {columns[i]} and {columns[j]}: partial r = {r_val} ({strength} {direction})")

    if notable:
        parts.append("Notable partial correlations (controlling for " + ", ".join(control) + "):")
        parts.extend(notable)
    else:
        parts.append("No notable partial correlations (|r| ≥ 0.3) were observed.")

    return "\n".join(parts)
