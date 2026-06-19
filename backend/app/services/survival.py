""""
Survival analysis service for DevStat.

Provides functions for Kaplan-Meier estimation and Cox proportional hazards
regression, returning structured dicts with summary tables, tests, and
interpretation text.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import multivariate_logrank_test
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


# ---------------------------------------------------------------------------
# Kaplan-Meier
# ---------------------------------------------------------------------------


def kaplan_meier(
    df: pd.DataFrame,
    time_col: str,
    status_col: str,
    event_code: int = 1,
    group_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform Kaplan-Meier survival analysis.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    time_col : str
        Column name for follow-up time.
    status_col : str
        Column name for event status (1 = event, 0 = censored).
    event_code : int, optional
        Value in ``status_col`` that indicates the event occurred (default 1).
    group_col : str, optional
        Column name for grouping variable (e.g., treatment arm).

    Returns
    -------
    dict
        With keys ``summary_table``, ``median_survival``, ``log_rank_test``,
        ``group_comparisons`` (if grouped), ``km_curve`` (plot coordinates),
        and ``interpretation``.
    """
    for col in [time_col, status_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    if group_col and group_col not in df.columns:
        return error(f"Group column '{group_col}' not found in DataFrame.")

    all_cols = [time_col, status_col]
    if group_col:
        all_cols.append(group_col)
    df_clean = df[all_cols].dropna().copy()
    n = len(df_clean)
    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")

    # Validate time column is numeric -- lifelines requires numeric durations
    if not pd.api.types.is_numeric_dtype(df_clean[time_col]):
        try:
            df_clean[time_col] = pd.to_numeric(df_clean[time_col], errors="coerce")
            df_clean = df_clean.dropna(subset=[time_col])
            n = len(df_clean)
            if n < 3:
                return error(f"Insufficient numeric data in '{time_col}' after coercion (need >= 3).")
        except Exception:
            return error(f"Column '{time_col}' must be numeric (duration). Got dtype {df_clean[time_col].dtype}.")

    # Ensure time column is fully numeric — coerce any remaining non-numeric values
    df_clean[time_col] = pd.to_numeric(df_clean[time_col], errors="coerce")
    df_clean = df_clean.dropna(subset=[time_col])
    n = len(df_clean)
    if n < 3:
        return error("Insufficient numeric data in time column after cleaning (need >= 3).")

    df_clean["_event"] = (df_clean[status_col] == event_code).astype(int)
    n_events = int(df_clean["_event"].sum())
    n_censored = n - n_events

    result: Dict[str, Any] = {
        "time_col": time_col,
        "status_col": status_col,
        "event_code": event_code,
        "group_col": group_col,
        "n_total": n,
        "n_events": n_events,
        "n_censored": n_censored,
    }

    sum_rows_all = []
    median_rows_all: List[Dict[str, Any]] = []
    km_curve_all: List[Dict[str, Any]] = []

    if group_col:
        groups = sorted(str(g) for g in df_clean[group_col].unique())
        lr_stat = None
        lr_p = None

        for g in groups:
            mask = df_clean[group_col] == g
            subset = df_clean[mask]
            kmf = KaplanMeierFitter()
            try:
                kmf.fit(
                    durations=subset[time_col],
                    event_observed=subset["_event"],
                )
            except Exception as e:
                return error(f"Kaplan-Meier fit failed for group '{g}': {e}")
            tl = kmf.survival_function_.index.values
            sp = kmf.survival_function_.values.flatten()
            ci_l = kmf.confidence_interval_.iloc[:, 0].values
            ci_u = kmf.confidence_interval_.iloc[:, 1].values
            se_v = (ci_u - ci_l) / (2 * 1.96)
            for idx in range(len(tl)):
                at_risk = int(np.sum(subset[time_col] >= tl[idx]))
                n_ev = int(np.sum((subset[time_col] == tl[idx]) & (subset["_event"] == 1)))
                n_cen = int(np.sum((subset[time_col] == tl[idx]) & (subset["_event"] == 0)))
                sum_rows_all.append({
                    "group": g,
                    "timeline": float(tl[idx]),
                    "at_risk": at_risk,
                    "events": n_ev,
                    "censored": n_cen,
                    "survival_prob": _round(float(sp[idx])),
                    "se": _round(float(se_v[idx])),
                    "ci_lower": _round(float(ci_l[idx])),
                    "ci_upper": _round(float(ci_u[idx])),
                })
            med = float(kmf.median_survival_time_)
            median_rows_all.append({
                "group": g,
                "median": _round(med) if not np.isnan(med) else None,
                "ci_lower": None,
                "ci_upper": None,
            })
            km_curve_all.append({
                "group": g,
                "x": [float(t) for t in tl.tolist()],
                "y": [float(s) for s in sp.tolist()],
                "ci_lower": [float(c) for c in ci_l.tolist()],
                "ci_upper": [float(c) for c in ci_u.tolist()],
            })

        try:
            lr = multivariate_logrank_test(
                df_clean[time_col],
                df_clean[group_col],
                df_clean["_event"],
            )
            lr_stat = lr.test_statistic
            lr_p = lr.p_value
        except Exception:
            lr_stat = None
            lr_p = None

        result["log_rank_test"] = {
            "statistic": _round(lr_stat) if lr_stat is not None else None,
            "p": _round(lr_p) if lr_p is not None else None,
            "p_label": _p_value(lr_p) if lr_p is not None else None,
        }

        pairwise = []
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                g1, g2 = str(groups[i]), str(groups[j])
                mask1 = df_clean[group_col] == groups[i]
                mask2 = df_clean[group_col] == groups[j]
                subset_p = df_clean[mask1 | mask2]
                try:
                    lr_pair = multivariate_logrank_test(
                        subset_p[time_col],
                        subset_p[group_col],
                        subset_p["_event"],
                    )
                    pairwise.append({
                        "group1": g1,
                        "group2": g2,
                        "statistic": _round(lr_pair.test_statistic),
                        "p": _round(lr_pair.p_value),
                        "p_label": _p_value(lr_pair.p_value),
                    })
                except Exception:
                    pass
        result["pairwise_comparisons"] = pairwise if pairwise else None

    else:
        kmf = KaplanMeierFitter()
        try:
            kmf.fit(durations=df_clean[time_col], event_observed=df_clean["_event"])
        except Exception as e:
            return error(f"Kaplan-Meier fit failed: {e}")
        tl = kmf.survival_function_.index.values
        sp = kmf.survival_function_.values.flatten()
        ci_l = kmf.confidence_interval_.iloc[:, 0].values
        ci_u = kmf.confidence_interval_.iloc[:, 1].values
        se_v = (ci_u - ci_l) / (2 * 1.96)
        for idx in range(len(tl)):
            at_risk = int(np.sum(df_clean[time_col] >= tl[idx]))
            n_ev = int(np.sum((df_clean[time_col] == tl[idx]) & (df_clean["_event"] == 1)))
            n_cen = int(np.sum((df_clean[time_col] == tl[idx]) & (df_clean["_event"] == 0)))
            sum_rows_all.append({
                "timeline": float(tl[idx]),
                "at_risk": at_risk,
                "events": n_ev,
                "censored": n_cen,
                "survival_prob": _round(float(sp[idx])),
                "se": _round(float(se_v[idx])),
                "ci_lower": _round(float(ci_l[idx])),
                "ci_upper": _round(float(ci_u[idx])),
            })
        med = float(kmf.median_survival_time_)
        median_rows_all = [{
            "group": "overall",
            "median": _round(med) if not np.isnan(med) else None,
            "ci_lower": None, "ci_upper": None,
        }]
        km_curve_all = [{
            "group": "overall",
            "x": [float(t) for t in tl.tolist()],
            "y": [float(s) for s in sp.tolist()],
            "ci_lower": [float(c) for c in ci_l.tolist()],
            "ci_upper": [float(c) for c in ci_u.tolist()],
        }]
        result["log_rank_test"] = None

    result["summary_table"] = sum_rows_all
    result["median_survival"] = median_rows_all
    result["km_curve"] = km_curve_all
    result["interpretation"] = _interpret_km(result)
    return result


def _interpret_km(result: Dict[str, Any]) -> str:
    parts = [f"Kaplan-Meier survival analysis was performed on "
             f"{result['n_total']} subjects "
             f"({result['n_events']} events, {result['n_censored']} censored)."]
    groups = result.get("median_survival", [])
    for g in groups:
        name = g.get("group", "")
        med = g.get("median")
        if med is not None:
            parts.append(f"Median survival time for {name}: {med:.2f} time units.")
    lr = result.get("log_rank_test")
    if lr and lr.get("p") is not None:
        parts.append(f"The log-rank test comparing groups "
                     f"was {'statistically significant' if lr['p'] < 0.05 else 'not statistically significant'} "
                     f"(χ² = {lr['statistic']:.4f}, p = {lr['p']:.4f}).")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Cox proportional hazards
# ---------------------------------------------------------------------------


def cox_regression(
    df: pd.DataFrame,
    time_col: str,
    status_col: str,
    covariates: List[str],
    event_code: int = 1,
) -> Dict[str, Any]:
    """Perform Cox proportional hazards regression."""
    for col in [time_col, status_col] + covariates:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")
    all_cols = [time_col, status_col] + covariates
    df_clean = df[all_cols].dropna().copy()
    n = len(df_clean)
    if n < 3:
        return error("Insufficient data (need at least 3 complete cases).")

    # Validate time column is numeric
    if not pd.api.types.is_numeric_dtype(df_clean[time_col]):
        try:
            df_clean[time_col] = pd.to_numeric(df_clean[time_col], errors="coerce")
            df_clean = df_clean.dropna(subset=[time_col])
            n = len(df_clean)
            if n < 3:
                return error(f"Insufficient numeric data in '{time_col}' after coercion (need >= 3).")
        except Exception:
            return error(f"Column '{time_col}' must be numeric (duration). Got dtype {df_clean[time_col].dtype}.")

    df_clean["_event"] = (df_clean[status_col] == event_code).astype(int)
    n_events = int(df_clean["_event"].sum())
    if n_events < 1:
        return error("No events observed in the data.")

    # Convert categorical covariates to numeric (one-hot encode strings)
    model_cols = [time_col, "_event"]
    for cov in covariates:
        if not pd.api.types.is_numeric_dtype(df_clean[cov]):
            dummies = pd.get_dummies(df_clean[cov], prefix=cov, drop_first=True)
            df_clean = pd.concat([df_clean, dummies], axis=1)
            model_cols.extend(list(dummies.columns))
        else:
            model_cols.append(cov)

    try:
        cph = CoxPHFitter()
        cph.fit(df_clean[model_cols],
                duration_col=time_col, event_col="_event", show_progress=False)
    except Exception as e:
        return error(f"Cox regression failed: {str(e)}")

    # Build coefficient list — use actual model columns (handles one-hot encoded dummies)
    summary = cph.summary
    coefficients = []
    for var in [c for c in model_cols if c not in (time_col, "_event")]:
        row = summary.loc[var]
        ci = cph.confidence_intervals_.loc[var].values
        hr = float(row["exp(coef)"])
        coef = float(row["coef"])
        se = float(row["se(coef)"])
        z_val = float(row["z"])
        p_val = float(row["p"])
        coefficients.append({
            "name": var,
            "coef": _round(coef),
            "hr": _round(hr),
            "hr_ci_lower": _round(ci[0]),
            "hr_ci_upper": _round(ci[1]),
            "se": _round(se),
            "z": _round(z_val),
            "p": _round(p_val),
            "p_label": _p_value(p_val),
        })

    model_summary = {
        "concordance_index": _round(cph.concordance_index_),
        "log_likelihood": _round(cph.log_likelihood_),
        "aic": _round(cph.AIC_partial_),
        "n": n,
        "n_events": n_events,
        "n_covariates": len(covariates),
    }

    model_col_set = [c for c in model_cols if c not in (time_col, "_event")]
    try:
        schoenfeld = cph.check_assumptions(
            df_clean[model_cols],
            p_value_threshold=0.05)
        ph_test = {}
        if hasattr(schoenfeld, "result") and schoenfeld.result is not None:
            for var in model_col_set:
                if var in schoenfeld.result.index:
                    row = schoenfeld.result.loc[var]
                    ph_test[var] = {"test_statistic": _round(float(row["test_statistic"])),
                                    "p": _round(float(row["p"])),
                                    "p_label": _p_value(float(row["p"]))}
                else:
                    ph_test[var] = {"note": "Proportional hazards assumption could not be tested"}
        else:
            ph_test = {v: {"note": "Proportional hazards assumption test not computed"} for v in model_col_set}
    except Exception:
        ph_test = {v: {"note": "Proportional hazards assumption could not be tested"} for v in model_col_set}

    result = {
        "coefficients": coefficients,
        "model_summary": model_summary,
        "proportional_hazards_test": ph_test,
        "interpretation": _interpret_cox(coefficients, model_summary, ph_test),
    }
    return result


def _interpret_cox(coefficients, model_summary, ph_test):
    sig_vars = [c for c in coefficients if c.get("p", 1) < 0.05]
    n = model_summary["n"]
    n_events = model_summary["n_events"]
    n_cov = model_summary["n_covariates"]
    conc = model_summary.get("concordance_index", "?")
    aic = model_summary.get("aic", "?")

    parts = [
        f"Cox proportional hazards regression was performed with {n_cov} covariate(s) "
        f"on {n} subjects ({n_events} events). ",
        f"The model achieved a concordance index (C-statistic) of {conc:.3f}, "
        f"AIC = {aic:.4f}.",
    ]
    if sig_vars:
        parts.append(f"Significant predictors in the model: ")
        for c in sig_vars:
            parts.append(
                f"• {c['name']}: HR = {c['hr']:.4f} "
                f"(95% CI: {c['hr_ci_lower']:.4f} – {c['hr_ci_upper']:.4f}), "
                f"z = {c['z']:.4f}, {c.get('p_label', {}).get('label', '')}"
            )
    else:
        parts.append("No covariates were statistically significant at p < 0.05.")
    ph_violations = [v for v, r in ph_test.items() if r.get("p", 1) < 0.05]
    if ph_test and ph_violations:
        parts.append(
            f"The proportional hazards assumption may be violated "
            f"({len(ph_violations)} variable(s) with p < 0.05: "
            f"{', '.join(ph_violations)}). "
            f"Consider time-dependent covariates or stratified analysis."
        )
    else:
        parts.append("The proportional hazards assumption was not violated "
                     "(Schoenfeld residuals test, all p ≥ 0.05).")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Graph data generators
# ---------------------------------------------------------------------------

def cox_forest_data(coefficients: List[Dict]) -> Dict[str, Any]:
    """Generate forest plot data from Cox coefficients."""
    traces = []
    hr_values = []
    ci_lowers = []
    ci_uppers = []
    labels = []
    p_values = []

    for c in coefficients:
        labels.append(c["name"])
        hr_values.append(c.get("hr", 1))
        ci_lowers.append(c.get("hr_ci_lower", c.get("hr", 1)))
        ci_uppers.append(c.get("hr_ci_upper", c.get("hr", 1)))
        p_values.append(c.get("p", 1))

    # Convert to error bar format for horizontal plot
    x_err_lo = [hr - ci for hr, ci in zip(hr_values, ci_lowers)]
    x_err_hi = [ci - hr for ci, hr in zip(ci_uppers, hr_values)]

    traces = [{
        "type": "scatter", "mode": "markers",
        "x": hr_values, "y": labels,
        "marker": {"color": ["#e53e3e" if p < 0.05 else "#718096" for p in p_values], "size": 10},
        "error_x": {"type": "data", "symmetric": False, "array": x_err_hi, "arrayminus": x_err_lo},
        "name": "Hazard Ratio",
    }]

    layout = {
        "title": "Forest Plot — Cox Regression",
        "xaxis": {"title": "Hazard Ratio (95% CI)", "type": "log"},
        "yaxis": {"autorange": "reversed"},
        "shapes": [{"type": "line", "x0": 1, "x1": 1, "y0": -0.5, "y1": len(labels) - 0.5,
                    "line": {"color": "#cbd5e0", "dash": "dash"}}],
        "margin": {"l": 120},
    }
    return {"traces": traces, "layout": layout}


def cox_predict_survival(
    df: pd.DataFrame,
    time_col: str,
    status_col: str,
    covariates: List[str],
    event_code: int = 1,
    profiles: Optional[List[Dict[str, Any]]] = None,
    times: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Generate predicted survival curves from Cox model for given covariate profiles.

    If profiles is None, uses mean of each covariate as a default profile.
    """
    for col in [time_col, status_col] + covariates:
        if col not in df.columns:
            return error(f"Column '{col}' not found")

    all_cols = [time_col, status_col] + covariates
    df_clean = df[all_cols].dropna().copy()
    df_clean["_event"] = (df_clean[status_col] == event_code).astype(int)

    try:
        cph = CoxPHFitter()
        cph.fit(df_clean[[time_col, "_event"] + covariates],
                duration_col=time_col, event_col="_event", show_progress=False)
    except Exception as e:
        return {"error": str(e)}

    if profiles is None:
        avg = {v: float(df_clean[v].mean()) for v in covariates}
        profiles = [{"label": "At mean of covariates", "values": avg}]

    if times is None:
        max_t = float(df_clean[time_col].quantile(0.95))
        times = list(np.linspace(0, max_t, 100))

    traces = []
    for profile in profiles:
        vals = profile.get("values", {})
        label = profile.get("label", "Profile")
        surv = cph.predict_survival_function(
            pd.DataFrame([vals])[covariates], times=times).values.flatten()
        traces.append({
            "type": "scatter", "mode": "lines",
            "x": list(times), "y": [float(s) for s in surv],
            "name": label,
        })

    # Also add baseline survival, interpolated to the same time grid
    baseline = cph.baseline_survival_
    bl_raw_times = list(baseline.index.astype(float))
    bl_raw_surv = [float(s) for s in baseline.values.flatten()]
    bl_surv_interp = [float(np.interp(t, bl_raw_times, bl_raw_surv, left=1.0, right=bl_raw_surv[-1])) for t in times]
    traces.append({
        "type": "scatter", "mode": "lines",
        "x": list(times), "y": bl_surv_interp,
        "name": "Baseline survival",
        "line": {"dash": "dash"},
    })

    layout = {
        "title": "Predicted Survival Curves (Cox Model)",
        "xaxis": {"title": "Time"}, "yaxis": {"title": "Survival Probability", "range": [0, 1]},
    }
    return {"traces": traces, "layout": layout}


# ---------------------------------------------------------------------------
# Transform R output → frontend-ready chart + results format
# (pass-through — R scripts now output directly in the R_OUTPUT_FORMAT.md standard)
# ---------------------------------------------------------------------------


def transform_km_r_output(r_result: Dict[str, Any]) -> Dict[str, Any]:
    """R now outputs chart_type + series directly; this is a pass-through."""
    out = dict(r_result)
    if "chart_type" not in out:
        out["chart_type"] = "km_curve"
    return out


def transform_cox_r_output(r_result: Dict[str, Any]) -> Dict[str, Any]:
    """R now outputs chart_type + series directly; this is a pass-through."""
    out = dict(r_result)
    if "chart_type" not in out:
        out["chart_type"] = "scatter"
    return out
