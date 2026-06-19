"""
DevStat Analysis Dispatcher — routes FastAPI endpoint calls to the Python engine.

Usage in router code::

    from r.dispatcher import run_analysis
    result = run_analysis("frequencies", {"column": "treatment_arm"})
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import app.state as _state
from r.engine import AnalysisEngine

_engine = AnalysisEngine()

_ANALYSIS_PATH_MAP: Dict[str, str] = {
    "frequencies": "frequencies",
    "descriptive": "descriptive",
    "crosstab": "crosstab",
    "ttest": "ttest",
    "ttest_paired": "ttest",
    "anova": "anova",
    "chisquare": "chisquare",
    "kaplan_meier": "kaplan_meier",
    "cox_regression": "cox_regression",
    "correlation": "correlation",
    "linear_regression": "linear_regression",
    "logistic_regression": "logistic_regression",
    "mannwhitney": "mannwhitney",
    "wilcoxon": "wilcoxon",
    "kruskal_wallis": "kruskal_wallis",
    "explore": "explore",
    "anova_twoway": "twoway_anova",
    "diagnostic": "diagnostic",
    "factor_analysis": "factor_analysis",
    "reliability": "reliability",
    "partial_correlation": "partial_correlation",
    "means": "means",
    "mixed_model": "mixed_model",
    "cluster_analysis": "cluster",
    "power_analysis": "power",
}


def run_analysis(
    analysis_name: str,
    params: Dict[str, Any],
    timeout: int = 120,
) -> Dict[str, Any]:
    """Run an analysis with the current in-memory dataset."""
    log = logging.getLogger("devstat.analysis")
    dispatch_id = f"{time.time_ns():x}"
    t0 = time.time()

    if _state.current_data is None:
        log.warning("DISPATCH_FAIL | id=%s | analysis=%s | reason=no_data", dispatch_id, analysis_name)
        return {"error": "No dataset is currently loaded. Upload a file first."}

    n_rows = len(_state.current_data)
    n_cols = len(_state.current_data.columns)

    log.info("DISPATCH | id=%s | analysis=%s | rows=%d | cols=%d | params=%s",
             dispatch_id, analysis_name, n_rows, n_cols,
             {k: v for k, v in params.items()})

    result = _engine.run(analysis_name, params)

    elapsed = time.time() - t0
    has_error = "error" in result
    log.log(
        logging.WARNING if has_error else logging.INFO,
        "DISPATCH_DONE | id=%s | analysis=%s | engine=py | elapsed=%.3fs | has_error=%s",
        dispatch_id, analysis_name, elapsed, has_error,
    )

    return result


def available_analyses() -> List[str]:
    """Return the list of analyses available."""
    return _engine.available_analyses()
