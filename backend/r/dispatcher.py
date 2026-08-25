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

    # ── Account + free-tier gate (bound to machine+IP, NOT the session) ─────
    # No anonymous use: a visitor must sign in to compute anything. A licensed
    # account (paid/admin) is unlimited. A signed-in free account is capped at
    # 5 analyses (+5 charts, gated in the charts router) on this machine+IP;
    # exhausting it — even after creating a new account or clearing cookies on
    # the same machine/address — returns a warm paywall prompt. This is
    # fail-CLOSED: on any gate error the request is blocked, never given away.
    try:
        from app.state import (get_uid, get_device, get_client_ip, get_teaching,
                               get_teaching_session)
        from app.services.firebase_store import licence_live, trial_check_and_consume
        uid = get_uid()
        # Guests may do the FREE teaching lesson (its tests are free), but no
        # other anonymous compute: the free-analysis path requires a signed-in
        # account (or being inside a loaded free teaching scenario).
        free_teaching = bool(get_teaching() and (get_teaching_session() or {}).get("free"))
        if not uid and not free_teaching:
            log.warning("DISPATCH_GATE | id=%s | analysis=%s | reason=no_account", dispatch_id, analysis_name)
            return {
                "blocked": True,
                "requires_subscription": True,
                "action_type": "account",
                "reason": ("A warm hello! 👋 Pop in with a quick free account and we'll save "
                           "your work for you. Your first 5 analyses and 5 charts are free, "
                           "no card needed."),
                "details": "Create a free account to start using DevStat.",
                "suggested_alternatives": [],
            }
        if licence_live(uid):
            pass  # paid / admin account — unlimited, skip counters
        elif get_teaching():
            pass  # guided Teaching mode — free, consumes no credit
        else:
            gate = trial_check_and_consume(get_device(), get_client_ip(), "analysis")
            if gate.get("blocked"):
                log.warning("DISPATCH_GATE | id=%s | analysis=%s | trial_used identity=%s",
                            dispatch_id, analysis_name, gate.get("identity", ""))
                return {
                    "blocked": True,
                    "requires_subscription": True,
                    "action_type": "subscription",
                    "reason": gate.get("reason") or (
                        "You've had a lovely free run of it! ✨ Your first 5 analyses and "
                        "5 charts are used up — a £25/year licence keeps you going."),
                    "details": "Upgrade to a £25/year licence to keep analysing.",
                    "suggested_alternatives": [],
                }
    except Exception as gate_err:  # NEVER fail-open on a gate error
        log.exception("DISPATCH_GATE_FAIL | id=%s | %s", dispatch_id, gate_err)
        return {
            "blocked": True,
            "requires_subscription": True,
            "action_type": "account",
            "reason": "We're having a small hiccup. Please sign in and try again.",
            "details": "If this keeps happening, please contact support.",
            "suggested_alternatives": [],
        }

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
