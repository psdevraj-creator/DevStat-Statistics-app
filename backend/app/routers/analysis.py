"""
DevStat — Analysis Router

Endpoints for statistical analyses (descriptive, group comparisons,
regression, survival, diagnostic tests).  All endpoints operate on the
dataset currently held in memory (``app.main._state.current_data``).

Each result is augmented with a plain-English ``interpretation`` field
via the appropriate function from ``app.services.interpreter``.

Mounted at ``/api/analysis`` in the main FastAPI application.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

import app.state as _state
from app.state import require_data
# Initialize file-based logging
from app.logging_config import elig_logger
from app.models.dataset import (
    AnalysisRequest,
    DiagnosticRequest,
    RegressionRequest,
    SurvivalRequest,
    TestRequest,
    # Response models
    FrequencyResponse,
    CrosstabResponse,
    KaplanMeierResponse,
    CoxResponse,
)

from ..validation import (
    validate_anova,
    validate_cluster,
    validate_correlation,
    validate_crosstab,
    validate_diagnostic,
    validate_factor_analysis,
    validate_mixed_model,
    validate_power,
    validate_regression,
    validate_survival,
    validate_ttest,
)
from ..eligibility import (
    check_survival_eligibility,
    check_ttest_eligibility,
    check_anova_eligibility,
    check_regression_eligibility,
    check_logistic_eligibility,
    check_correlation_eligibility,
    check_mannwhitney_eligibility,
    check_wilcoxon_eligibility,
    check_kruskal_eligibility,
    check_chi_square_eligibility,
    check_mcnemar_eligibility,
    check_reliability_eligibility,
    check_factor_eligibility,
    check_paired_ttest_eligibility,
    check_descriptive_eligibility,
    check_chart_eligibility,
    infer_variable_type,
)

# ── Analysis dispatcher ──────────────────────────────────────────────────
from r.dispatcher import run_analysis

from app.services.compare import (
    anova_twoway,
    chisquare as py_chisquare,
    kruskal_wallis,
    mannwhitney,
    ttest as py_ttest,
    wilcoxon,
)
from app.services.descriptive import crosstab as py_crosstab, descriptive_stats, explore, frequencies as py_frequencies, means
from app.services.diagnostic import diagnostic_test, roc_analysis
from app.services.interpreter import (
    interpret_anova,
    interpret_chisquare,
    interpret_correlation,
    interpret_diagnostic,
    interpret_p_value,
    interpret_regression,
    interpret_survival,
    interpret_ttest,
)
from app.services.regression import (
    correlation_matrix as py_correlation,
    linear_regression as py_linear_regression,
    logistic_regression as py_logistic_regression,
    partial_correlation,
)
from app.services.survival import cox_forest_data, cox_predict_survival, cox_regression as py_cox_regression, kaplan_meier as py_kaplan_meier
from app.services.factor_analysis import factor_analysis, reliability_analysis

router = APIRouter(prefix="", tags=["Analysis"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _safe_interpret(result: Dict[str, Any], interpret_fn, default: str = "") -> str:
    """Call an interpretation function safely, returning default on error."""
    try:
        return interpret_fn(result)
    except Exception as e:
        import logging
        logging.getLogger("devstat.interpret").warning(
            "INTERPRET_CRASH | func=%s | error=%s | result_keys=%s",
            interpret_fn.__name__, str(e), list(result.keys())[:10],
        )
        return default


_require_data = require_data



# ── Helpers ──────────────────────────────────────────────────────────────
# Safe eligibility wrapper — catches crashes, allows analysis to proceed


def _check_eligibility_safe(
    endpoint_name: str,
    eligibility_func,
    **kwargs,
):
    """Run an eligibility check with crash protection.
    
    If the eligibility check itself crashes, logs the error and returns None
    (meaning: allow analysis to proceed). Does NOT silently swallow.
    """
    import logging, traceback
    try:
        result = eligibility_func(**kwargs)
        if result.get("blocked"):
            return result
    except Exception as e:
        log = logging.getLogger("devstat.eligibility")
        log.warning(
            "ELIGIBILITY_CRASH | endpoint=%s | func=%s | error=%s\n%s",
            endpoint_name, eligibility_func.__name__, str(e),
            traceback.format_exc(),
        )
    return None



def _infer_var_type(col_name: str) -> str:
    """Infer statistical variable type from a column in the current dataset.
    
    Null-safe: returns 'unknown' if data is missing, dtype is ambiguous, or inference fails.
    """
    try:
        if _state.current_data is None:
            return "unknown"
        if col_name not in _state.current_data.columns:
            return "unknown"
        col = _state.current_data[col_name]
        if col.empty:
            return "unknown"
        # Drop nulls for inference
        non_null = col.dropna()
        if non_null.empty:
            return "unknown"
        unique_count = int(non_null.nunique())
        n_rows = int(len(non_null))
        # Handle dtype safely (pandas extension types too)
        try:
            is_numeric = bool(pd.api.types.is_numeric_dtype(col.dtype))
        except Exception:
            try:
                is_numeric = bool(np.issubdtype(col.dtype, np.number))
            except Exception:
                is_numeric = False
        dtype_str = str(col.dtype)
        return infer_variable_type(
            name=col_name,
            dtype=dtype_str,
            unique_count=unique_count,
            n_rows=n_rows,
            is_numeric=is_numeric,
        )
    except Exception:
        return "unknown"


def _n_unique(col_name: str) -> int:
    """Count unique values in a column (NaN excluded). Null-safe."""
    try:
        if _state.current_data is None:
            return 0
        if col_name not in _state.current_data.columns:
            return 0
        col = _state.current_data[col_name]
        if col.empty:
            return 0
        return int(col.nunique(dropna=True))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------


@router.post("/descriptive")
async def descriptive(req: AnalysisRequest) -> Dict[str, Any]:
    """Compute descriptive statistics via R for one or more columns."""
    _require_data()
    # Eligibility check per column
    if req.columns:
        for col in req.columns:
            elig = check_descriptive_eligibility("mean", _infer_var_type(col), col)
            if elig["blocked"]:
                return elig
    result = run_analysis("descriptive", {
        "columns": req.columns,
        "group_col": req.group_col,
    })
    return result


@router.post("/frequencies")
async def frequencies_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Build a frequency table using R for a categorical / discrete column."""
    _require_data()
    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    if column not in _state.current_data.columns:
        raise HTTPException(
            status_code=400, detail=f"Column '{column}' not found in dataset."
        )
    # Eligibility check
    elig = check_descriptive_eligibility("frequency", _infer_var_type(column), column)
    if elig["blocked"]:
        return elig
    result = run_analysis("frequencies", {"column": column})
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    result["chart_type"] = "frequencies"
    return result


@router.post("/crosstab")
async def crosstab_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Build a cross-tabulation using R with chi-square test and Cramer's V."""
    row = body.get("row")
    col = body.get("col")
    validate_crosstab(row, col)
    _require_data()
    # Eligibility checks
    elig1 = check_chi_square_eligibility(dep_type=_infer_var_type(row), var_types=[_infer_var_type(row), _infer_var_type(col)])
    if elig1["blocked"]:
        return elig1
    elig2 = check_chart_eligibility("bar", x_type=_infer_var_type(row), y_type=_infer_var_type(col))
    if elig2["blocked"]:
        return elig2
    result = run_analysis("crosstab", {"row": row, "col": col})
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


# ---------------------------------------------------------------------------
# Group comparisons
# ---------------------------------------------------------------------------


@router.post("/ttest")
async def ttest_endpoint(req: TestRequest) -> Dict[str, Any]:
    """Perform a t-test (independent, paired) or Mann-Whitney U test.

    * If ``req.test_type == \"mannwhitney\"`` → Mann-Whitney U (Python).
    * Otherwise → t-test via R.
    """
    validate_ttest(req.dependent, req.group, test_type=req.test_type)
    _require_data()

    # Eligibility check for t-test
    if req.test_type != "mannwhitney":
        n_groups = _n_unique(req.group) if req.group else 1
        dep_type = _infer_var_type(req.dependent[0]) if req.dependent else "continuous"
        elig = check_ttest_eligibility(n_groups=n_groups, is_paired=req.paired, dep_type=dep_type)
        if elig["blocked"]:
            return elig

    if req.test_type == "mannwhitney":
        if not req.dependent or not req.group:
            raise HTTPException(
                status_code=400,
                detail="Mann-Whitney U requires 'dependent' (one column) and 'group'.",
            )
        result = mannwhitney(_state.current_data, req.dependent[0], req.group)
        result["interpretation"] = _safe_interpret(result, interpret_ttest)
        return result

    # R-based t-test
    if req.paired:
        result = run_analysis("ttest", {
            "column1": req.dependent[0], "column2": req.dependent[1],
            "test_type": "paired",
        })
    elif req.group:
        result = run_analysis("ttest", {
            "column1": req.dependent[0], "column2": req.group,
            "test_type": "independent",
            "var_equal": True,
        })
    else:
        result = run_analysis("ttest", {
            "column1": req.dependent[0],
            "test_type": "one_sample",
        })
    return result


@router.post("/anova")
async def anova_endpoint(req: TestRequest) -> Dict[str, Any]:
    """Perform a one-way ANOVA via R or Kruskal-Wallis via Python."""
    validate_anova(req.dependent, req.group, req.test_type)
    _require_data()

    if not req.dependent or not req.group:
        raise HTTPException(
            status_code=400,
            detail="ANOVA / Kruskal-Wallis requires 'dependent' and 'group'.",
        )

    # Eligibility check for ANOVA
    n_groups = _n_unique(req.group)
    dep_type = _infer_var_type(req.dependent[0])
    elig = check_anova_eligibility(n_groups=n_groups, dep_type=dep_type, is_paired=req.paired)
    if elig["blocked"]:
        return elig

    if req.test_type == "kruskal":
        result = kruskal_wallis(_state.current_data, req.dependent[0], req.group)
        result["interpretation"] = _safe_interpret(result, interpret_anova)
        return result

    result = run_analysis("anova", {
        "dv": req.dependent[0],
        "between": req.group,
    })
    return result


@router.post("/chisquare")
async def chisquare_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a chi-square test via R."""
    _require_data()
    row = body.get("row")
    col = body.get("col")
    if not row or not col:
        raise HTTPException(
            status_code=400, detail="Both 'row' and 'col' are required."
        )
    # Eligibility check
    elig = check_chi_square_eligibility(dep_type=_infer_var_type(row), var_types=[_infer_var_type(row), _infer_var_type(col)])
    if elig["blocked"]:
        return elig
    result = run_analysis("chisquare", {"row": row, "col": col})
    return result


# ---------------------------------------------------------------------------
# ComparePage dedicated routes (paired t-test, Mann-Whitney, Wilcoxon, Kruskal-Wallis)
# ---------------------------------------------------------------------------


@router.post("/ttest-paired")
async def ttest_paired_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a paired-samples t-test via R."""
    var1 = body.get("variable1")
    var2 = body.get("variable2")
    validate_ttest([], variable1=var1, variable2=var2)
    _require_data()
    if not var1 or not var2:
        raise HTTPException(
            status_code=400, detail="Both 'variable1' and 'variable2' are required."
        )
    # Eligibility check
    elig = check_paired_ttest_eligibility(is_paired=True, dep_type=_infer_var_type(var1))
    if elig["blocked"]:
        return elig
    result = run_analysis("ttest", {
        "column1": var1, "column2": var2,
        "test_type": "paired",
    })
    return result


@router.post("/np-mannwhitney")
async def np_mannwhitney_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Mann-Whitney U test via R."""
    _require_data()
    dep = body.get("dependent", "")
    grp = body.get("group", "")
    if not dep or not grp:
        raise HTTPException(
            status_code=400, detail="Both 'dependent' and 'group' are required."
        )
    # Eligibility check
    n_groups = _n_unique(grp)
    elig = check_mannwhitney_eligibility(n_groups=n_groups, dep_type=_infer_var_type(dep))
    if elig["blocked"]:
        return elig
    result = run_analysis("mannwhitney", {"column": dep, "group_var": grp})
    return result


@router.post("/np-wilcoxon")
async def np_wilcoxon_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Wilcoxon signed-rank test via R."""
    _require_data()
    var1 = body.get("variable1")
    var2 = body.get("variable2")
    if not var1 or not var2:
        raise HTTPException(
            status_code=400, detail="Both 'variable1' and 'variable2' are required."
        )
    # Eligibility check
    elig = check_wilcoxon_eligibility(is_paired=True, dep_type=_infer_var_type(var1))
    if elig["blocked"]:
        return elig
    result = run_analysis("wilcoxon", {"column1": var1, "column2": var2})
    return result


@router.post("/np-kruskalwallis")
async def np_kruskalwallis_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Kruskal-Wallis H test via R."""
    _require_data()
    dep = body.get("dependent")
    grp = body.get("group")
    if not dep or not grp:
        raise HTTPException(
            status_code=400, detail="Both 'dependent' and 'group' are required."
        )
    # Eligibility check
    n_groups = _n_unique(grp)
    elig = check_kruskal_eligibility(n_groups=n_groups)
    if elig["blocked"]:
        return elig
    result = run_analysis("kruskal_wallis", {"column": dep, "group_var": grp})
    return result


# ---------------------------------------------------------------------------
# Non-parametric tests (one-sample / paired / runs / goodness-of-fit)
# ---------------------------------------------------------------------------


@router.post("/np-friedman")
async def np_friedman_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Friedman test (non-parametric repeated measures)."""
    _require_data()
    from scipy import stats as sp_stats

    variables: list = body.get("variables", [])
    if not variables or len(variables) < 2:
        raise HTTPException(
            status_code=400, detail="At least two 'variables' are required."
        )
    # Soft eligibility: check that variables are numeric
    for v in variables:
        vt = _infer_var_type(v)
        if vt not in ("continuous", "ordinal"):
            elig = {
                "eligible": False,
                "blocked": True,
                "requested_action": "Friedman test",
                "action_type": "test",
                "reason": "Friedman test requires numeric ordinal or continuous variables.",
                "details": f"Variable '{v}' is type '{vt}'.",
                "triggering_data_properties": [f"variable_type={vt}"],
                "suggested_alternatives": [],
                "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
                "inferred_data_role": {},
                "help_terms": [],
            }
            if elig["blocked"]:
                return elig
    samples = [
        _state.current_data[col].dropna().values for col in variables
    ]

    # Ensure all samples have same length (row-wise dropna)
    min_len = min(len(s) for s in samples)
    if min_len < 3:
        raise HTTPException(status_code=400, detail="Friedman test requires at least 3 complete cases across all variables.")
    samples = [s[:min_len] for s in samples]
    stat, p_value = sp_stats.friedmanchisquare(*samples)
    return {
        "test_name": "Friedman Test",
        "statistic": round(float(stat), 4),
        "statistic_name": "χ²",
        "p_value": float(p_value),
        "interpretation": interpret_p_value(float(p_value)),
    }


@router.post("/np-sign")
async def np_sign_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Sign test for paired data."""
    _require_data()
    from scipy import stats as sp_stats

    var1 = body.get("variable1")
    var2 = body.get("variable2")
    if not var1 or not var2:
        raise HTTPException(
            status_code=400, detail="Both 'variable1' and 'variable2' are required."
        )
    # Soft eligibility check
    for v in (var1, var2):
        vt = _infer_var_type(v)
        if vt not in ("continuous", "ordinal"):
            return {
                "eligible": False,
                "blocked": True,
                "requested_action": "Sign test",
                "action_type": "test",
                "reason": "Sign test requires numeric ordinal or continuous data.",
                "details": f"Variable '{v}' is type '{vt}'.",
                "triggering_data_properties": [f"variable_type={vt}"],
                "suggested_alternatives": ["Use McNemar test for binary paired data."],
                "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
                "inferred_data_role": {},
                "help_terms": [],
            }
    common = _state.current_data[[var1, var2]].dropna()
    diffs = common[var1] - common[var2]
    nonzero = diffs[diffs != 0]
    n = len(nonzero)
    if n < 1:
        raise HTTPException(status_code=400, detail="No non-zero differences after removing ties.")
    n_pos = int((nonzero > 0).sum())
    n_neg = int((nonzero < 0).sum())
    k = min(n_pos, n_neg)
    result = sp_stats.binomtest(k, n, p=0.5, alternative="two-sided")
    return {
        "test_name": "Sign Test",
        "statistic": int(k),
        "statistic_name": "Min(#+, #−)",
        "n": int(n),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "p_value": float(result.pvalue),
        "interpretation": interpret_p_value(float(result.pvalue)),
    }


@router.post("/np-mcnemar")
async def np_mcnemar_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a McNemar test for paired nominal data (2×2)."""
    _require_data()
    import numpy as np
    from scipy import stats as sp_stats

    var1 = body.get("variable1")
    var2 = body.get("variable2")
    if not var1 or not var2:
        raise HTTPException(
            status_code=400, detail="Both 'variable1' and 'variable2' are required."
        )
    # Eligibility check
    elig = check_mcnemar_eligibility(is_paired=True, dep_type=_infer_var_type(var1))
    if elig["blocked"]:
        return elig
    # Build the 2×2 contingency table of discordant pairs.
    common = _state.current_data[[var1, var2]].dropna()
    # Determine the two unique values in each column (assume binary).
    vals1 = sorted(common[var1].unique())
    vals2 = sorted(common[var2].unique())
    if len(vals1) != 2 or len(vals2) != 2:
        raise HTTPException(
            status_code=400,
            detail="Both variables must be binary (exactly two unique values each).",
        )
    # Map to 0/1.
    pos1, pos2 = vals1[1], vals2[1]
    b = int(((common[var1] == pos1) & (common[var2] != pos2)).sum())
    c = int(((common[var1] != pos1) & (common[var2] == pos2)).sum())
    n_discordant = b + c
    if n_discordant < 1:
        raise HTTPException(status_code=400, detail="No discordant pairs found.")
    # Use binomial exact test on discordant pairs (continuity-corrected chi-square as alternative).
    # Exact McNemar: binomtest(min(b, c), n=b+c, p=0.5)
    k = min(b, c)
    exact_result = sp_stats.binomtest(k, n_discordant, p=0.5, alternative="two-sided")
    # Chi-square approximation with continuity correction.
    chi2 = (abs(b - c) - 1) ** 2 / n_discordant if n_discordant > 0 else 0.0
    chi2_p = 1 - sp_stats.chi2.cdf(chi2, 1)
    return {
        "test_name": "McNemar Test",
        "statistic": round(float(chi2), 4),
        "statistic_name": "χ² (continuity corrected)",
        "p_value": float(exact_result.pvalue),
        "exact_p_value": float(exact_result.pvalue),
        "discordant_pairs": {"b": b, "c": c, "total": n_discordant},
        "interpretation": interpret_p_value(float(exact_result.pvalue)),
    }


@router.post("/np-chisquare")
async def np_chisquare_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a one-sample chi-square goodness-of-fit test."""
    _require_data()
    from scipy import stats as sp_stats

    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    # Eligibility check
    elig = check_chi_square_eligibility(dep_type=_infer_var_type(column))
    if elig["blocked"]:
        return elig
    col_data = _state.current_data[column].dropna()
    if len(col_data) == 0:
        raise HTTPException(status_code=400, detail="No non-missing data in column.")
    # Build observed frequencies.
    value_counts = col_data.value_counts()
    f_obs = value_counts.values.astype(float)
    # Uniform expected frequencies.
    f_exp = np.full_like(f_obs, f_obs.sum() / len(f_obs), dtype=float)
    stat, p_value = sp_stats.chisquare(f_obs, f_exp=f_exp)
    return {
        "test_name": "Chi-Square Goodness-of-Fit",
        "statistic": round(float(stat), 4),
        "statistic_name": "χ²",
        "df": int(len(f_obs) - 1),
        "p_value": float(p_value),
        "categories": {str(k): int(v) for k, v in value_counts.items()},
        "interpretation": interpret_p_value(float(p_value)),
    }


@router.post("/np-binomial")
async def np_binomial_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a binomial test."""
    _require_data()
    from scipy import stats as sp_stats

    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    test_proportion = body.get("test_proportion", 0.5)
    # Eligibility check: must be binary
    var_type = _infer_var_type(column)
    if var_type not in ("binary", "binary_nominal"):
        return {
            "eligible": False,
            "blocked": True,
            "requested_action": "Binomial test",
            "action_type": "test",
            "reason": "Binomial test requires a binary variable.",
            "details": f"Variable type is '{var_type}'.",
            "triggering_data_properties": [f"variable_type={var_type}"],
            "suggested_alternatives": ["Use chi-square goodness-of-fit for multi-category data."],
            "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
            "inferred_data_role": {},
            "help_terms": [],
        }
    col_data = _state.current_data[column].dropna()
    if len(col_data) == 0:
        raise HTTPException(status_code=400, detail="No non-missing data in column.")
    unique_vals = col_data.unique()
    if len(unique_vals) != 2:
        raise HTTPException(
            status_code=400,
            detail="Binomial test requires a binary column (exactly two unique values).",
        )
    # Count successes as the second unique value.
    target = sorted(unique_vals)[1]
    k = int((col_data == target).sum())
    n = int(len(col_data))
    result = sp_stats.binomtest(k, n, p=test_proportion, alternative="two-sided")
    return {
        "test_name": "Binomial Test",
        "statistic": k,
        "statistic_name": "k (successes)",
        "n": n,
        "test_proportion": float(test_proportion),
        "observed_proportion": round(float(k / n), 4),
        "p_value": float(result.pvalue),
        "interpretation": interpret_p_value(float(result.pvalue)),
    }


@router.post("/np-runs")
async def np_runs_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a Wald-Wolfowitz runs test for randomness."""
    _require_data()
    import numpy as np
    from scipy import stats as sp_stats

    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    col_data = _state.current_data[column].dropna()
    n = len(col_data)
    if n < 2:
        raise HTTPException(status_code=400, detail="At least 2 observations required.")
    # Dichotomize around the median.
    median = col_data.median()
    binary = (col_data > median).astype(int).values
    # Count runs.
    runs = 1 + int(np.sum(np.diff(binary) != 0))
    n1 = int(np.sum(binary == 1))
    n2 = int(np.sum(binary == 0))
    if n1 < 1 or n2 < 1:
        return {
            "test_name": "Runs Test (Wald-Wolfowitz)",
            "error": "Cannot compute runs test: all values on one side of the median.",
        }
    # Mean and variance of runs.
    mean_runs = (2 * n1 * n2) / (n1 + n2) + 1
    std_runs = np.sqrt(
        (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2))
        / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    )
    if std_runs == 0:
        p_value = 1.0
    else:
        z = (runs - mean_runs) / std_runs
        p_value = 2 * sp_stats.norm.sf(abs(z))
    return {
        "test_name": "Runs Test (Wald-Wolfowitz)",
        "statistic": int(runs),
        "statistic_name": "Runs",
        "expected_runs": round(float(mean_runs), 2),
        "z_value": round(float(z) if std_runs > 0 else 0.0, 4),
        "p_value": float(p_value),
        "n": int(n),
        "n1": int(n1),
        "n2": int(n2),
        "cut_point": round(float(median), 4),
        "interpretation": interpret_p_value(float(p_value)),
    }


@router.post("/np-ks")
async def np_ks_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a one-sample Kolmogorov-Smirnov test for normality."""
    _require_data()
    from scipy import stats as sp_stats

    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    col_data = _state.current_data[column].dropna()
    n = len(col_data)
    if n < 3:
        raise HTTPException(status_code=400, detail="At least 3 observations required.")
    # Standardize for test against N(0,1).
    standardized = (col_data - col_data.mean()) / col_data.std(ddof=1)
    stat, p_value = sp_stats.kstest(standardized, "norm")
    return {
        "test_name": "Kolmogorov-Smirnov Test",
        "statistic": round(float(stat), 4),
        "statistic_name": "D",
        "p_value": float(p_value),
        "n": int(n),
        "interpretation": interpret_p_value(float(p_value)),
    }


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


@router.post("/correlation")
async def correlation_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a correlation matrix via R (Pearson, Spearman, or Kendall)."""
    columns: list = body.get("columns", [])
    method: str = body.get("method", "pearson")
    validate_correlation(columns, method)
    _require_data()
    # Eligibility check
    var_types = [_infer_var_type(c) for c in columns]
    elig = check_correlation_eligibility(var_types=var_types, method=method)
    if elig["blocked"]:
        return elig
    result = run_analysis("correlation", {"columns": columns, "method": method})
    return result


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


@router.post("/linear-regression")
async def linear_regression_endpoint(req: RegressionRequest) -> Dict[str, Any]:
    """Perform ordinary least squares (linear) regression via R."""
    validate_regression(req.dependent, req.independents)
    _require_data()
    # Eligibility check
    dep_type = _infer_var_type(req.dependent)
    elig = check_regression_eligibility(dep_type=dep_type)
    if elig["blocked"]:
        return elig
    result = run_analysis("linear_regression", {
        "dv": req.dependent,
        "predictors": req.independents,
    })
    return result

@router.post("/logistic-regression")
async def logistic_regression_endpoint(req: RegressionRequest) -> Dict[str, Any]:
    """Perform binary logistic regression via R."""
    validate_regression(req.dependent, req.independents)
    _require_data()
    # Eligibility check
    dep_type = _infer_var_type(req.dependent)
    elig = check_logistic_eligibility(dep_type=dep_type)
    if elig["blocked"]:
        return elig
    result = run_analysis("logistic_regression", {
        "dv": req.dependent,
        "predictors": req.independents,
    })
    return result


# ---------------------------------------------------------------------------
# Survival Analysis
# ---------------------------------------------------------------------------


@router.post("/kaplan-meier")
async def kaplan_meier_endpoint(req: SurvivalRequest) -> Dict[str, Any]:
    """Perform Kaplan-Meier survival analysis via R (with optional grouping)."""
    validate_survival(req.time_col, req.status_col, factors=req.factors)
    elig = check_survival_eligibility(has_time=bool(req.time_col), has_event=bool(req.status_col))
    if elig["blocked"]:
        return elig
    _require_data()
    group_col = req.factors[0] if req.factors and len(req.factors) > 0 else None
    result = run_analysis("kaplan_meier", {
        "time_col": req.time_col,
        "status_col": req.status_col,
        "group_col": group_col,
    })
    if "error" in result:
        return result
    return result


@router.post("/cox-regression")
async def cox_regression_endpoint(req: SurvivalRequest) -> Dict[str, Any]:
    """Perform Cox proportional hazards regression via R."""
    covariates = (req.covariates or []) + (req.factors or [])
    validate_survival(req.time_col, req.status_col, covariates=covariates)
    # Eligibility check
    elig = check_survival_eligibility(has_time=bool(req.time_col), has_event=bool(req.status_col))
    if elig["blocked"]:
        return elig
    _require_data()
    if not covariates:
        raise HTTPException(
            status_code=400,
            detail="At least one covariate or factor is required for Cox regression.",
        )
    result = run_analysis("cox_regression", {
        "time_col": req.time_col,
        "status_col": req.status_col,
        "covariates": covariates,
    })
    if "error" in result:
        return result
    return result


# ---------------------------------------------------------------------------
# Diagnostic Tests
# ---------------------------------------------------------------------------


@router.post("/diagnostic")
async def diagnostic_endpoint(req: DiagnosticRequest) -> Dict[str, Any]:
    """Evaluate a diagnostic test against a gold standard via R (2x2 table)."""
    validate_diagnostic(req.test_col, req.gold_col)
    _require_data()
    result = run_analysis("diagnostic", {
        "test_col": req.test_col,
        "gold_col": req.gold_col,
    })
    return result


@router.post("/roc")
async def roc_endpoint(req: DiagnosticRequest) -> Dict[str, Any]:
    """Perform ROC curve analysis via R."""
    validate_diagnostic(req.test_col, req.gold_col)
    _require_data()
    result = run_analysis("roc_analysis", {
        "test_col": req.test_col,
        "gold_col": req.gold_col,
    })
    return result


# ---------------------------------------------------------------------------
# Factor Analysis & Reliability
# ---------------------------------------------------------------------------


@router.post("/factor")
async def factor_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform exploratory factor analysis via R (psych)."""
    columns: list = body.get("columns", [])
    n_factors: int = body.get("n_factors", 2)
    validate_factor_analysis(columns, n_factors)
    _require_data()
    rotation: str = body.get("rotation", "varimax")
    if not columns or len(columns) < 2:
        raise HTTPException(
            status_code=400, detail="At least two 'columns' are required."
        )
    # Eligibility check
    elig = check_factor_eligibility(n_vars=len(columns))
    if elig["blocked"]:
        return elig
    result = run_analysis("factor_analysis", {
        "columns": columns, "n_factors": n_factors, "rotation": rotation,
    })
    return result


@router.post("/reliability")
async def reliability_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Cronbach's alpha reliability analysis via R (psych)."""
    _require_data()
    columns: list = body.get("columns", [])
    if not columns or len(columns) < 2:
        raise HTTPException(
            status_code=400, detail="At least two 'columns' are required."
        )
    # Eligibility check
    elig = check_reliability_eligibility(n_items=len(columns))
    if elig["blocked"]:
        return elig
    result = run_analysis("reliability", {"columns": columns})
    return result


# ---------------------------------------------------------------------------
# Two-Way ANOVA
# ---------------------------------------------------------------------------


@router.post("/anova-twoway")
async def anova_twoway_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a two-way (factorial) ANOVA with interaction via R."""
    dependent = body.get("dependent")
    factor1 = body.get("factor1")
    factor2 = body.get("factor2")
    validate_anova(dependent, factor1, factor2, test_type='twoway')
    _require_data()
    if not dependent or not factor1 or not factor2:
        raise HTTPException(
            status_code=400,
            detail="'dependent', 'factor1', and 'factor2' are required.",
        )
    # Eligibility check: n_groups from factor1 * factor2
    n_groups = _n_unique(factor1) * _n_unique(factor2)
    dep_type = _infer_var_type(dependent)
    elig = check_anova_eligibility(n_groups=n_groups, dep_type=dep_type)
    if elig["blocked"]:
        return elig
    result = run_analysis("anova_twoway", {
        "dv": dependent, "factor1": factor1, "factor2": factor2
    })
    if "error" in result:
        return {"status": "error", "error": result["error"]}
    return result


# ---------------------------------------------------------------------------
# Partial Correlation
# ---------------------------------------------------------------------------


@router.post("/partial-correlation")
async def partial_correlation_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compute partial correlations via R controlling for covariates."""
    _require_data()
    columns: list = body.get("columns", [])
    control: list = body.get("control", [])
    method: str = body.get("method", "pearson")
    if not columns or len(columns) < 2:
        raise HTTPException(
            status_code=400, detail="At least two 'columns' are required."
        )
    if not control:
        raise HTTPException(
            status_code=400, detail="At least one 'control' variable is required."
        )
    # Eligibility check
    var_types = [_infer_var_type(c) for c in columns + control]
    elig = check_correlation_eligibility(var_types=var_types, method=method)
    if elig["blocked"]:
        return elig
    result = run_analysis("partial_correlation", {
        "columns": columns, "control": control, "method": method,
    })
    return result


# ---------------------------------------------------------------------------
# Explore & Means
# ---------------------------------------------------------------------------


@router.post("/explore")
async def explore_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform normality diagnostics via R for a numeric column."""
    _require_data()
    column = body.get("column")
    group_col = body.get("group_col")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    # Eligibility check
    elig = check_descriptive_eligibility("mean", _infer_var_type(column), column)
    if elig["blocked"]:
        return elig
    result = run_analysis("explore", {"column": column, "group_col": group_col})
    return result


@router.post("/means")
async def means_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compute grouped means with confidence intervals via R."""
    dependent = body.get("dependent")
    group = body.get("group")
    layers = body.get("layers")
    if not dependent:
        raise HTTPException(
            status_code=400, detail="'dependent' is required."
        )
    _require_data()
    # Eligibility check per column
    cols = [dependent] + ([group] if group else []) + (layers if layers else [])
    for col in cols:
        if col:
            elig = check_descriptive_eligibility("mean", _infer_var_type(col), col)
            if elig["blocked"]:
                return elig
    result = run_analysis("means", {
        "dependent": dependent, "group": group, "layers": layers,
    })
    return result


# ---------------------------------------------------------------------------
# Cox model prediction & forest plot
# ---------------------------------------------------------------------------


@router.post("/cox-predict")
async def cox_predict_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate predicted survival curves from a Cox model."""
    _require_data()
    time_col = body.get("time_col")
    status_col = body.get("status_col")
    covariates: list = body.get("covariates", [])
    event_code: int = body.get("event_code", 1)
    profiles: list = body.get("profiles")
    times: list = body.get("times")
    if not time_col or not status_col:
        raise HTTPException(
            status_code=400, detail="'time_col' and 'status_col' are required."
        )
    if not covariates:
        raise HTTPException(
            status_code=400, detail="At least one covariate is required."
        )
    result = cox_predict_survival(
        _state.current_data,
        time_col=time_col,
        status_col=status_col,
        covariates=covariates,
        event_code=event_code,
        profiles=profiles,
        times=times,
    )
    return result


@router.post("/cox-forest")
async def cox_forest_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate forest plot data from Cox regression coefficients.

    Expected payload::

        {
          "coefficients": [
            {
              "name": "age",
              "hr": 1.05,
              "hr_ci_lower": 1.01,
              "hr_ci_upper": 1.09,
              "p": 0.012
            }
          ]
        }

    Typically obtained from the ``data.coefficients`` array returned by
    ``POST /api/analysis/cox-regression``.
    """
    coefficients: list = body.get("coefficients", [])
    if not coefficients:
        raise HTTPException(
            status_code=400,
            detail=(
                "'coefficients' is required. "
                "Expected a list of Cox coefficient dicts, each with keys: "
                "name, hr, hr_ci_lower, hr_ci_upper, p. "
                "Get this from POST /api/analysis/cox-regression → data.coefficients."
            ),
        )
    result = cox_forest_data(coefficients)
    return result


# ── Advanced Modules ─────────────────────────────────────────────────────
#
# Mixed Models, Cluster Analysis, Power Analysis
# Powered by R packages lme4, stats, pwr


@router.post("/mixed-model")
async def mixed_model_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Fit a linear or generalized linear mixed model via R (lme4)."""
    dv = body.get("dv")
    fixed = body.get("fixed", [])
    random = body.get("random", [])
    validate_mixed_model(dv, fixed, random)
    _require_data()
    family = body.get("family", "gaussian")
    if not dv or not fixed:
        raise HTTPException(status_code=400, detail="'dv' and 'fixed' are required.")
    # Eligibility check: check dv is appropriate for the model family
    dep_type = _infer_var_type(dv)
    if family == "gaussian" and dep_type not in ("continuous",):
        return {
            "eligible": False,
            "blocked": True,
            "requested_action": "Linear mixed model",
            "action_type": "test",
            "reason": "Linear mixed model with Gaussian family requires a continuous outcome.",
            "details": f"Outcome type is '{dep_type}'.",
            "triggering_data_properties": [f"outcome_type={dep_type}"],
            "suggested_alternatives": ["Use binomial family for binary outcomes.", "Use Poisson family for count outcomes."],
            "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
            "inferred_data_role": {},
            "help_terms": [],
        }
    if family == "binomial" and dep_type not in ("binary", "binary_nominal"):
        return {
            "eligible": False,
            "blocked": True,
            "requested_action": "Binomial mixed model",
            "action_type": "test",
            "reason": "Binomial mixed model requires a binary outcome.",
            "details": f"Outcome type is '{dep_type}'.",
            "triggering_data_properties": [f"outcome_type={dep_type}"],
            "suggested_alternatives": ["Use Gaussian family for continuous outcomes."],
            "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
            "inferred_data_role": {},
            "help_terms": [],
        }
    result = run_analysis("mixed_model", {
        "dv": dv, "fixed": fixed, "random": random, "family": family,
    })
    return result


@router.post("/cluster")
async def cluster_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform cluster analysis (k-means or hierarchical) via R."""
    columns = body.get("columns", [])
    n_clusters = body.get("n_clusters", 3)
    validate_cluster(columns, n_clusters)
    _require_data()
    method = body.get("method", "kmeans")
    if not columns or len(columns) < 2:
        raise HTTPException(status_code=400, detail="At least two 'columns' required.")
    # Soft eligibility check
    if n_clusters < 2:
        return {
            "eligible": False,
            "blocked": True,
            "requested_action": f"Cluster analysis ({method})",
            "action_type": "test",
            "reason": "At least 2 clusters are required.",
            "details": f"Requested {n_clusters} cluster(s).",
            "triggering_data_properties": [f"n_clusters={n_clusters}"],
            "suggested_alternatives": ["Specify n_clusters >= 2."],
            "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
            "inferred_data_role": {},
            "help_terms": [],
        }
    result = run_analysis("cluster_analysis", {
        "columns": columns, "method": method, "n_clusters": n_clusters,
    })
    return result


@router.post("/power")
async def power_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Perform power analysis via R (pwr)."""
    test = body.get("test", "ttest")
    n = body.get("n")
    effect_size = body.get("effect_size")
    power = body.get("power")
    alpha = body.get("alpha", 0.05)
    k = body.get("k", 2)  # number of groups for ANOVA
    validate_power(test, effect_size, power, alpha)
    # Soft eligibility check
    supported = ("ttest", "anova", "chisq", "corr", "prop")
    if test not in supported:
        return {
            "eligible": False,
            "blocked": True,
            "requested_action": f"Power analysis ({test})",
            "action_type": "test",
            "reason": f"Test type '{test}' is not supported.",
            "details": f"Supported types: {', '.join(supported)}.",
            "triggering_data_properties": [f"test_type={test}"],
            "suggested_alternatives": ["Choose from: ttest, anova, chisq, corr, prop."],
            "alternative_ranked": {"preferred": [], "acceptable": [], "advanced": []},
            "inferred_data_role": {},
            "help_terms": [],
        }
    result = run_analysis("power_analysis", {
        "test": test, "n": n, "effect_size": effect_size,
        "power": power, "alpha": alpha, "k": k,
    })
    return result
