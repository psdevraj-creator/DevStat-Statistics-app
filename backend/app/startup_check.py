"""
Startup Self-Check — runs once when the server starts.

Verifies all Python dependencies are available.
If anything is missing, the app starts but /api/health reports degraded state.
"""
from __future__ import annotations

import importlib
import logging
from typing import Dict, List

_log = logging.getLogger("devstat.startup_check")

# ── Python dependency check ──────────────────────────────────────────────

PYTHON_REQUIRED = [
    "fastapi", "uvicorn", "pydantic", "pandas", "numpy",
    "scipy", "statsmodels", "sklearn", "openpyxl", "plotly",
]

PYTHON_OPTIONAL = [
    "lifelines", "xlsxwriter", "pyreadstat", "matplotlib", "seaborn", "jinja2",
]


def _check_python() -> tuple:
    """Check Python imports. Returns (status: ok|degraded, missing: [...])"""
    missing: List[str] = []
    for pkg in PYTHON_REQUIRED:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    for pkg in PYTHON_OPTIONAL:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if not any(p in missing for p in PYTHON_REQUIRED):
        status = "degraded" if any(p in missing for p in PYTHON_OPTIONAL) else "ok"
        return status, missing
    return "failed", missing


# ── Public check — called at startup ─────────────────────────────────────


def run_startup_check() -> Dict:
    """Run all checks and return a structured report. Called once at startup."""
    py_status, py_missing = _check_python()

    report = {
        "python": {
            "status": py_status,
            "missing": py_missing,
            "message": "All Python deps OK" if not py_missing
            else f"Missing packages: {', '.join(py_missing)}",
        },
        "engine": "py",
        "overall": "healthy" if py_status == "ok" else "degraded",
    }

    sep = f"\n{'='*50}"
    _log.info("%s\n  STARTUP DEPENDENCY CHECK%s", sep, sep)
    _log.info("  Python: %s — %s", py_status, report['python']['message'])
    _log.info("  Engine: py")
    _log.info("  Overall: %s%s\n", report['overall'], sep)

    if py_missing:
        _log.warning("  ⚠ Missing Python packages: %s", ', '.join(py_missing))
        _log.warning("    → Run: pip install -r requirements.txt")
        _log.warning("%s\n", sep)

    return report
