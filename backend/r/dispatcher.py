"""
DevStat Analysis Dispatcher — routes FastAPI endpoint calls to the Python engine.

Usage in router code::

    from r.dispatcher import run_analysis
    result = run_analysis("frequencies", {"column": "treatment_arm"})
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import app.state as _state


_engine_instance = None


def get_engine():
    global _engine_instance
    if _engine_instance is None:
        from r.engine import AnalysisEngine
        _engine_instance = AnalysisEngine()
    return _engine_instance
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

    # ── Free-trial gate (3 analyses per machine/IP, LIFETIME) ───────────
    # A signed-in, licensed user is exempt. Guests get 3 analyses before a
    # "create an account / pay" prompt. Count is stored in Firestore keyed by
    # the stable device id (or client IP) so it survives reloads.
    try:
        from app.state import get_uid, get_device
        from app.services.firebase_store import licence_live, guest_trial_status, guest_trial_consume
        uid = get_uid()
        licensed = bool(uid) and licence_live(uid)
        if not licensed:
            device = get_device() or "guest"
            status = guest_trial_status(device)
            if not status.get("eligible", True):
                log.warning("DISPATCH_GATE | id=%s | analysis=%s | trial_used=%s/%s",
                            dispatch_id, analysis_name, status.get("used"), status.get("limit"))
                return {
                    "blocked": True,
                    "requires_subscription": True,
                    "action_type": "subscription",
                    "reason": f"Your free trial of {status.get('limit')} analyses is used up. "
                              "Create an account and buy a £25/year licence to continue.",
                    "details": "Create a free account, then subscribe (£25/yr) to keep analysing.",
                    "suggested_alternatives": [],
                }
            guest_trial_consume(device)
    except Exception as gate_err:  # never let the gate break a run
        log.warning("DISPATCH_GATE_FAIL | id=%s | %s", dispatch_id, gate_err)

    try:
        result = get_engine().run(analysis_name, params)
    except Exception as exc:
        import traceback
        try:
            crash_log = _get_crash_path()
            with open(str(crash_log), "w") as f:
                f.write(f"Analysis: {analysis_name}\nParams: {params}\n\n{traceback.format_exc()}")
        except Exception:
            pass
        result = {"error": f"{type(exc).__name__}: {str(exc)}"}

    # ── Automatic quality control ──────────────────────────────────────
    # Validate + auto-correct the result (downsample huge point sets, clamp
    # probability CIs, clean non-finite values, flag degenerate data). The
    # frontend renders result["qa"] as a "Quality control" badge so the user
    # is informed rather than frustrated by a broken chart.
    try:
        from app.services.qa import apply_qa
        result = apply_qa(result, analysis_name)
    except Exception:
        # QA must never break the analysis path.
        pass

    elapsed = time.time() - t0
    has_error = "error" in result
    log.log(
        logging.WARNING if has_error else logging.INFO,
        "DISPATCH_DONE | id=%s | analysis=%s | engine=py | elapsed=%.3fs | has_error=%s",
        dispatch_id, analysis_name, elapsed, has_error,
    )

    return result


def _get_crash_path():
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('TEMP', sys._MEIPASS))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "devstat_crash.log"


def available_analyses() -> List[str]:
    """Return the list of analyses available."""
    return get_engine().available_analyses()
