"""
Diagnostic test service for DevStat.

Provides functions for diagnostic test evaluation (sensitivity, specificity,
predictive values, likelihood ratios) and ROC curve analysis.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn import metrics as sk_metrics
from app.services import error


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _round(value: float, decimals: int = 4) -> float:
    """Round a float to *decimals* places, preserving None and inf/nan."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
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
# Diagnostic Test (2x2 Table)
# ---------------------------------------------------------------------------


def diagnostic_test(
    df: pd.DataFrame,
    test_col: str,
    gold_col: str,
    positive_code: int = 1,
) -> Dict[str, Any]:
    """Evaluate a diagnostic test against a gold standard.

    Constructs a 2×2 contingency table and computes standard diagnostic
    accuracy metrics.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    test_col : str
        Column containing the test result (binary).
    gold_col : str
        Column containing the gold standard / true condition (binary).
    positive_code : int, optional
        Value representing a positive result in both columns (default 1).

    Returns
    -------
    dict
        With keys ``tp``, ``fp``, ``fn``, ``tn``, ``sensitivity``,
        ``specificity``, ``ppv``, ``npv``, ``positive_likelihood_ratio``,
        ``negative_likelihood_ratio``, ``prevalence``, ``accuracy``,
        ``f1_score``, ``youden_index``, ``mcc``, and ``interpretation``.
    """
    # Validate columns.
    for col in [test_col, gold_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    df_clean = df[[test_col, gold_col]].dropna()
    n = len(df_clean)

    if n == 0:
        return error("No valid data after dropping missing values.")

    # Convert to binary indicators.
    test_pos = (df_clean[test_col] == positive_code).astype(int)
    gold_pos = (df_clean[gold_col] == positive_code).astype(int)

    tp = int(((test_pos == 1) & (gold_pos == 1)).sum())
    fp = int(((test_pos == 1) & (gold_pos == 0)).sum())
    fn = int(((test_pos == 0) & (gold_pos == 1)).sum())
    tn = int(((test_pos == 0) & (gold_pos == 0)).sum())

    # Compute metrics with safe division.
    def _safe_div(num: float, denom: float) -> float:
        return float(num / denom) if denom != 0 else 0.0

    sensitivity = _safe_div(tp, tp + fn)
    specificity = _safe_div(tn, tn + fp)
    ppv = _safe_div(tp, tp + fp)
    npv = _safe_div(tn, tn + fn)
    prevalence = _safe_div(tp + fn, n)
    accuracy = _safe_div(tp + tn, n)

    # Likelihood ratios.
    lr_positive = _safe_div(sensitivity, 1.0 - specificity) if specificity < 1 else float("inf")
    lr_negative = _safe_div(1.0 - sensitivity, specificity) if specificity > 0 else float("inf")

    # F1 score.
    f1 = _safe_div(2 * tp, 2 * tp + fp + fn)

    # Youden index.
    youden = sensitivity + specificity - 1.0

    # Matthews correlation coefficient.
    num_mcc = tp * tn - fp * fn
    denom_mcc = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = _safe_div(num_mcc, denom_mcc) if denom_mcc > 0 else 0.0

    result = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": n,
        "sensitivity": _round(sensitivity),
        "specificity": _round(specificity),
        "ppv": _round(ppv),
        "npv": _round(npv),
        "positive_likelihood_ratio": _round(lr_positive),
        "negative_likelihood_ratio": _round(lr_negative),
        "prevalence": _round(prevalence),
        "accuracy": _round(accuracy),
        "f1_score": _round(f1),
        "youden_index": _round(youden),
        "mcc": _round(mcc),
        "test_positive_code": positive_code,
        "gold_positive_code": positive_code,
    }

    # Interpretation.
    result["interpretation"] = _interpret_diag(result)

    return result


def _interpret_diag(result: Dict[str, Any]) -> str:
    """Generate plain-English interpretation for diagnostic test results."""
    parts = []

    parts.append(
        f"A diagnostic test evaluation was performed on {result['n']} subjects using a 2×2 table. "
    )

    if result["sensitivity"] >= 0.8:
        sens_label = "high"
    elif result["sensitivity"] >= 0.5:
        sens_label = "moderate"
    else:
        sens_label = "low"

    if result["specificity"] >= 0.8:
        spec_label = "high"
    elif result["specificity"] >= 0.5:
        spec_label = "moderate"
    else:
        spec_label = "low"

    parts.append(
        f"The test demonstrates {sens_label} sensitivity ({result['sensitivity']*100:.1f}%) "
        f"and {spec_label} specificity ({result['specificity']*100:.1f}%). "
    )

    parts.append(
        f"Positive predictive value is {result['ppv']*100:.1f}%, "
        f"negative predictive value is {result['npv']*100:.1f}%. "
    )

    lr_plus = result.get("positive_likelihood_ratio")
    if isinstance(lr_plus, (int, float)):
        parts.append(
            f"The positive likelihood ratio is {lr_plus:.2f}, "
            f"{'providing strong diagnostic evidence' if lr_plus >= 10 else 'providing moderate evidence' if lr_plus >= 5 else 'providing limited diagnostic evidence'}."
        )

    parts.append(
        f"Overall accuracy: {result['accuracy']*100:.1f}%, "
        f"with a Youden index of {result['youden_index']:.3f} "
        f"and Matthews correlation coefficient (MCC) of {result['mcc']:.3f}."
    )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# ROC Analysis
# ---------------------------------------------------------------------------


def roc_analysis(
    df: pd.DataFrame,
    test_col: str,
    gold_col: str,
    positive_code: int = 1,
) -> Dict[str, Any]:
    """Perform ROC curve analysis for a continuous or ordinal test variable.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    test_col : str
        Column containing the test result (continuous or ordinal).
    gold_col : str
        Column containing the gold standard / true condition (binary).
    positive_code : int, optional
        Value representing a positive result in the gold standard (default 1).

    Returns
    -------
    dict
        With keys ``roc_coordinates`` (list of {fpr, tpr, threshold}),
        ``auc``, ``optimal_cutoff``, ``sensitivity_at_cutoff``,
        ``specificity_at_cutoff``, and ``interpretation``.
    """
    # Validate columns.
    for col in [test_col, gold_col]:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    df_clean = df[[test_col, gold_col]].dropna()
    n = len(df_clean)

    if n == 0:
        return error("No valid data after dropping missing values.")

    # Convert gold standard to binary.
    y_true = (df_clean[gold_col] == positive_code).astype(int)
    y_score = df_clean[test_col].values

    # Check that both classes exist.
    unique_classes = y_true.nunique()
    if unique_classes < 2:
        return error("ROC analysis requires both positive and negative cases in the gold standard.")

    # Compute ROC curve.
    fpr, tpr, thresholds = sk_metrics.roc_curve(y_true, y_score)

    # Paired-down thresholds (keep at most 200 points for serialization).
    if len(thresholds) > 200:
        idx = np.linspace(0, len(thresholds) - 1, 200, dtype=int)
        fpr = fpr[idx]
        tpr = tpr[idx]
        thresholds = thresholds[idx]

    roc_coords = []
    for i in range(len(thresholds)):
        roc_coords.append({
            "fpr": _round(float(fpr[i])),
            "tpr": _round(float(tpr[i])),
            "threshold": _round(float(thresholds[i])),
        })

    # AUC.
    auc = sk_metrics.roc_auc_score(y_true, y_score)

    # Optimal cutoff using Youden index.
    youden = tpr - fpr
    best_idx = int(np.argmax(youden))
    optimal_threshold = float(thresholds[best_idx])
    optimal_sensitivity = float(tpr[best_idx])
    optimal_specificity = 1.0 - float(fpr[best_idx])

    result = {
        "roc_coordinates": roc_coords,
        "auc": _round(auc),
        "optimal_cutoff": _round(optimal_threshold),
        "sensitivity_at_cutoff": _round(optimal_sensitivity),
        "specificity_at_cutoff": _round(optimal_specificity),
        "youden_index": _round(float(youden[best_idx])),
        "n": n,
        "n_positive": int(y_true.sum()),
        "n_negative": int((1 - y_true).sum()),
        "test_column": test_col,
        "gold_column": gold_col,
    }

    # Interpretation.
    result["interpretation"] = _interpret_roc(result)

    return result


def _interpret_roc(result: Dict[str, Any]) -> str:
    """Generate plain-English interpretation for ROC analysis."""
    parts = []
    auc = result["auc"]

    if auc >= 0.9:
        qual = "outstanding"
    elif auc >= 0.8:
        qual = "excellent"
    elif auc >= 0.7:
        qual = "acceptable"
    elif auc >= 0.6:
        qual = "poor"
    else:
        qual = "failing / no better than chance"

    parts.append(
        f"ROC analysis yielded an AUC of {auc:.4f}, which is considered {qual} discriminatory ability."
    )

    parts.append(
        f"The optimal cutoff value (by Youden index) is {result['optimal_cutoff']:.4f}, "
        f"with sensitivity = {result['sensitivity_at_cutoff']*100:.1f}% and "
        f"specificity = {result['specificity_at_cutoff']*100:.1f}%."
    )

    parts.append(
        f"Analysis performed on {result['n']} observations "
        f"({result['n_positive']} positive, {result['n_negative']} negative)."
    )

    return " ".join(parts)
