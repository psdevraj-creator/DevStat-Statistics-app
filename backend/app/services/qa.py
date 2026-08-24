"""
DevStat QA (quality control) pass.

Runs on every analysis result *before* it is shown to the user. It inspects the
result for common quality problems (huge point counts, degenerate data, wide or
inverted confidence intervals, non-finite values, empty series) and — where a
safe automatic fix exists — re-processes the output so the user sees a good
result instead of a broken or frustrating one.

The frontend can render ``result["qa"]`` as a small "Quality control" badge with
the list of warnings and the auto-corrections that were applied.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

# Beyond this many points in a single chart series we downsample for display.
# Large series (e.g. 100k-row scatter) would choke the browser and look messy.
POINT_CAP = 3000

# Confidence-interval band wider than this (for probability/KM series) is flagged.
MAX_CI_WIDTH = 0.6

# Fewest observations for a non-trivial numeric result.
MIN_N = 5

# Sub-sampled flag set when we re-processed a series to keep its size sane.
DOWNSAMPLED = "downsampled_for_display"


def _is_finite(x) -> bool:
    try:
        return bool(np.isfinite(x))
    except Exception:
        return True


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _downsample(values: List, max_points: int) -> List:
    """Keep at most ``max_points`` evenly spaced values (or fewer)."""
    n = len(values)
    if n <= max_points:
        return values
    idx = np.linspace(0, n - 1, max_points).round().astype(int).tolist()
    return [values[i] for i in idx]


def _walk_series(obj: Any, qa: Dict[str, Any]) -> Any:
    """Recursively walk a result, applying fixes to any 'series' arrays."""
    if isinstance(obj, dict):
        series = obj.get("series")
        if isinstance(series, list) and series and all(
            isinstance(s, dict) for s in series
        ) and any(k in series[0] for k in ("x", "y", "values", "categories", "ci_lower")):
            fixed = []
            for s in series:
                s = dict(s)
                length = None
                for k in ("x", "y", "values", "categories"):
                    if isinstance(s.get(k), list):
                        length = len(s[k])
                        break
                if length is not None and length > POINT_CAP:
                    for k in ("x", "y", "values", "categories"):
                        if isinstance(s.get(k), list):
                            s[k] = _downsample(s[k], POINT_CAP)
                    if isinstance(s.get("errors"), list) and len(s["errors"]) == length:
                        s["errors"] = _downsample(s["errors"], POINT_CAP)
                    qa["auto"].append(
                        f"Chart had {length} points; downsampled to {POINT_CAP} for a cleaner view."
                    )
                    qa["flags"].add(DOWNSAMPLED)
                else:
                    # still clean non-finite / sanitise CIs even without downsampling
                    if isinstance(s.get("y"), list):
                        s["y"] = [_clamp_prob(v) for v in s["y"]] if _is_prob_series(s) else s["y"]
                # 1) clamp probability CIs to [0,1] and 2) keep them ordered
                for c in ("ci_lower", "ci_upper"):
                    if isinstance(s.get(c), list):
                        ci = [_clamp01(_num(v)) for v in s[c]]
                        if c == "ci_lower":
                            s[c] = ci
                        else:
                            s[c] = [_max(v, lo) for v, lo in zip(ci, s.get("ci_lower", [0.0] * len(ci)))]
                # 3) flag an unhelpfully wide confidence band
                if isinstance(s.get("ci_lower"), list) and isinstance(s.get("ci_upper"), list):
                    widths = [_num(u) - _num(l) for l, u in zip(s["ci_lower"], s["ci_upper"])]
                    if any(w > MAX_CI_WIDTH for w in widths):
                        qa["warnings"].append(
                            "Very wide confidence intervals in one or more series — small sample or few events; "
                            "interpret the precision of the estimate with caution."
                        )
                fixed.append(s)
            obj["series"] = fixed
        for k, v in obj.items():
            if k != "series":
                obj[k] = _walk_series(v, qa)
    elif isinstance(obj, list):
        return [_walk_series(v, qa) for v in obj]
    return obj


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _clamp_prob(v):
    return _clamp01(_num(v))


def _is_prob_series(s) -> bool:
    # Heuristic: survival-type series (has group at least) — clamp y to [0,1]. Be
    # conservative: only clamp when every y is within a plausible probability range
    # but some exceed 1 slightly (KM curves never exceed 1).
    y = s.get("y") or []
    if not y:
        return False
    try:
        ys = [float(v) for v in y]
    except Exception:
        return False
    return (max(ys) > 1.0 or min(ys) < 0.0) and s.get("group") is not None


def _max(a: float, b: float) -> float:
    return b if b > a else a


# ---------------------------------------------------------------------------
# Quality checks that don't need series walking
# ---------------------------------------------------------------------------


def _check_numeric(result: Dict[str, Any], qa: Dict[str, Any]) -> None:
    # n / observations fields
    for key in ("n", "n_total", "n_observations", "N"):
        v = result.get(key)
        if isinstance(v, (int, float)) and v < MIN_N:
            qa["warnings"].append(
                f"Only {int(v)} observations. Results are imprecise and may not be reliable; "
                "interpret with caution (wide confidence intervals, low power)."
            )
            break

    # Degenerate (zero-variance) numeric arrays
    for key in ("y", "values", "statistic"):
        vals = result.get(key)
        if isinstance(vals, list) and len(vals) > 0:
            nums = [_num(v) for v in vals]
            if max(nums) - min(nums) == 0 and max(nums) != 0:
                qa["warnings"].append(
                    f"'{key}' has no variance (all values identical). Most statistical tests are not "
                    "meaningful for a constant variable."
                )
                break
            if any(not _is_finite(v) for v in nums):
                qa["auto"].append("Removed non-finite (NaN/inf) values from the result for display.")

    # extremes in effect sizes (huge HR / OR -> near-perfect separation)
    for key in ("hazard_ratio", "odds_ratio", "exp_coef", "coef"):
        v = result.get(key)
        if isinstance(v, (int, float)) and abs(v) > 10:
            qa["warnings"].append(
                "A very large model coefficient was produced — this often indicates near-perfect "
                "separation in the data; the estimate may be unstable."
            )
            break


def apply_qa(result: Dict[str, Any], analysis_name: str = "") -> Dict[str, Any]:
    """Validate + auto-correct an analysis result in place and attach ``qa``.

    Returns the same result dict with ``result["qa"]`` added.
    """
    qa: Dict[str, Any] = {
        "status": "ok",
        "analysis": analysis_name,
        "warnings": [],
        "auto": [],
        "flags": set(),
    }

    if not isinstance(result, dict):
        return result

    if result.get("error"):
        qa["status"] = "error"
        qa["warnings"].append(str(result["error"]))
        result["qa"] = qa
        return result

    # Deep-walk series to fix sizes + CIs.
    try:
        result = _walk_series(result, qa)
    except Exception:
        qa["warnings"].append("Output passed through a quality check that encountered an unexpected field.")

    _check_numeric(result, qa)

    # Status + dedupe warnings.
    qa["warnings"] = list(dict.fromkeys(qa["warnings"]))
    qa["auto"] = list(dict.fromkeys(qa["auto"]))
    qa["flags"] = sorted(qa["flags"])  # set -> list for JSON serialisation
    if qa["warnings"]:
        qa["status"] = "warning"
    result["qa"] = qa
    return result
