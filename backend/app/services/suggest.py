"""
Suggest-Test recommendation engine.

Pure functions — no FastAPI dependency.  The router calls these and
wraps the result in Pydantic response models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from app.models.suggest import (
    AnalysisGoal,
    AssumptionInfo,
    SuggestTestRequest,
    SuggestTestResponse,
    TestRecommendation,
    VariableInfo,
    VariableType,
)


# ═══════════════════════════════════════════════════════════════════════
# Variable type inference
# ═══════════════════════════════════════════════════════════════════════

def _infer_variable_type(series: pd.Series, column_name: str) -> VariableType:
    """Heuristic type inference from a DataFrame column."""
    clean = series.dropna()
    if len(clean) == 0:
        return "unknown"

    n_unique = clean.nunique()

    # Heuristic: columns named like time/survival/duration
    name_lower = column_name.lower()
    if any(kw in name_lower for kw in ("time", "duration", "survival", "followup", "follow_up")):
        if pd.api.types.is_numeric_dtype(clean):
            return "survival_time"
        try:
            pd.to_numeric(clean, errors="raise")
            return "survival_time"
        except (ValueError, TypeError):
            pass

    # Heuristic: columns named like event/status/censor/death
    if any(kw in name_lower for kw in ("event", "status", "censor", "death", "dead", "outcome_binary")):
        if n_unique <= 3:
            return "event_indicator"

    if pd.api.types.is_numeric_dtype(clean):
        if n_unique == 2:
            return "binary"
        if n_unique <= 10 and all(float(v).is_integer() for v in clean if pd.notna(v)):
            return "ordinal"
        return "continuous"

    # String / object columns
    if n_unique == 2:
        return "binary"
    if n_unique <= 15:
        return "categorical"
    return "categorical"


def infer_variable_types(
    df: pd.DataFrame,
    variables: List[VariableInfo],
) -> List[VariableInfo]:
    """Populate ``inferred_type`` for each variable that exists in the DataFrame."""
    for v in variables:
        if v.column in df.columns:
            v.inferred_type = _infer_variable_type(df[v.column], v.column)
    return variables


# ═══════════════════════════════════════════════════════════════════════
# Assumption checks
# ═══════════════════════════════════════════════════════════════════════

def _check_normality(data: pd.Series) -> AssumptionInfo:
    clean = data.dropna()
    if len(clean) < 3:
        return AssumptionInfo(name="Normality", passed=None, detail="Too few observations to test.")
    if len(clean) > 5000:
        stat, p = sp_stats.kstest(clean, "norm", args=(clean.mean(), clean.std()))
        test_name = "Kolmogorov-Smirnov"
    else:
        stat, p = sp_stats.shapiro(clean)
        test_name = "Shapiro-Wilk"
    passed = p >= 0.05
    return AssumptionInfo(
        name="Normality",
        passed=passed,
        detail=f"{test_name}: W={stat:.4f}, p={p:.4f}",
        warning=None if passed else "Data may not be normally distributed. Consider a non-parametric alternative.",
    )


def _check_equal_variance(groups: Dict[Any, pd.Series]) -> AssumptionInfo:
    vals = [g.dropna().values for g in groups.values() if len(g.dropna()) > 1]
    if len(vals) < 2:
        return AssumptionInfo(name="Equal variance", passed=None, detail="Need at least 2 groups with >1 observation.")
    try:
        stat, p = sp_stats.levene(*vals)
    except Exception:
        return AssumptionInfo(name="Equal variance", passed=None, detail="Could not compute Levene's test.")
    passed = p >= 0.05
    return AssumptionInfo(
        name="Equal variance",
        passed=passed,
        detail=f"Levene: stat={stat:.4f}, p={p:.4f}",
        warning=None if passed else "Variances may be unequal. Consider Welch's t-test or a non-parametric alternative.",
    )


def _check_small_groups(n_per_group: List[int]) -> Optional[str]:
    if any(n < 5 for n in n_per_group):
        return "Some groups have fewer than 5 observations. Results may be unreliable."
    if any(n < 3 for n in n_per_group):
        return "Some groups have fewer than 3 observations. Analysis may not be possible."
    return None


# ═══════════════════════════════════════════════════════════════════════
# Decision tree
# ═══════════════════════════════════════════════════════════════════════

def _mk_test(
    test_id: str,
    test_name: str,
    rationale: str,
    payload: Dict[str, Any],
    endpoint: str,
    assumptions: Optional[List[AssumptionInfo]] = None,
    warnings: Optional[List[str]] = None,
    is_fallback: bool = False,
) -> TestRecommendation:
    return TestRecommendation(
        test_id=test_id,
        test_name=test_name,
        is_fallback=is_fallback,
        rationale=rationale,
        assumptions=assumptions or [],
        warnings=warnings or [],
        analysis_payload=payload,
        analysis_endpoint=endpoint,
    )


def _resolve_type(var_info: Optional[VariableInfo]) -> VariableType:
    if var_info is None:
        return "unknown"
    return var_info.effective_type


def _get_type_map(variables: List[VariableInfo]) -> Dict[str, VariableInfo]:
    return {v.column: v for v in variables}


def _compare_groups(
    df: pd.DataFrame,
    req: SuggestTestRequest,
    vmap: Dict[str, VariableInfo],
) -> Tuple[TestRecommendation, Optional[TestRecommendation], List[str]]:
    outcome = req.outcome_variable
    group_col = req.group_variable
    warnings: List[str] = []

    if not outcome or not group_col:
        return (
            _mk_test("none", "Cannot recommend", "Missing outcome or group variable.", {}, ""),
            None,
            ["Both an outcome variable and a group variable are required."],
        )

    outcome_type = _resolve_type(vmap.get(outcome))
    groups = sorted(df[group_col].dropna().unique())
    n_groups = len(groups) if len(groups) > 0 else req.num_groups or 0
    paired = req.paired

    # Build per-group data
    group_data: Dict[Any, pd.Series] = {}
    n_per_group: List[int] = []
    for g in groups:
        mask = df[group_col] == g
        vals = df.loc[mask, outcome].dropna()
        group_data[str(g)] = vals
        n_per_group.append(len(vals))

    assumptions: List[AssumptionInfo] = []
    norm_check = None
    var_check = None

    if outcome_type in ("continuous", "ordinal"):
        if outcome in df.columns:
            norm_check = _check_normality(df[outcome])
            assumptions.append(norm_check)
        var_check = _check_equal_variance(group_data)
        assumptions.append(var_check)

    small_warn = _check_small_groups(n_per_group)
    if small_warn:
        warnings.append(small_warn)

    # ── Continuous outcome ──────────────────────────────────────────
    if outcome_type in ("continuous", "ordinal"):
        if n_groups == 2:
            if paired:
                primary = _mk_test(
                    "paired_ttest",
                    "Paired t-test",
                    f"Outcome '{outcome}' is continuous, group '{group_col}' has 2 paired levels.",
                    {"test_type": "paired", "dependent": [outcome], "group": group_col, "paired": True},
                    "/api/analysis/ttest",
                    assumptions=assumptions,
                    warnings=warnings,
                )
                fallback = _mk_test(
                    "wilcoxon",
                    "Wilcoxon signed-rank test",
                    "Non-parametric alternative when normality is questionable.",
                    {"variable1": outcome, "variable2": group_col},
                    "/api/analysis/np-wilcoxon",
                    is_fallback=True,
                )
            else:
                primary = _mk_test(
                    "independent_ttest",
                    "Independent samples t-test",
                    f"Outcome '{outcome}' is continuous, group '{group_col}' has 2 independent levels.",
                    {"test_type": "independent", "dependent": [outcome], "group": group_col},
                    "/api/analysis/ttest",
                    assumptions=assumptions,
                    warnings=warnings,
                )
                fallback = _mk_test(
                    "mannwhitney",
                    "Mann–Whitney U test",
                    "Non-parametric alternative when normality is questionable.",
                    {"dependent": outcome, "group": group_col},
                    "/api/analysis/np-mannwhitney",
                    is_fallback=True,
                )
        else:
            primary = _mk_test(
                "oneway_anova",
                "One-way ANOVA",
                f"Outcome '{outcome}' is continuous, group '{group_col}' has {n_groups} independent levels.",
                {"test_type": "anova", "dependent": [outcome], "group": group_col},
                "/api/analysis/anova",
                assumptions=assumptions,
                warnings=warnings,
            )
            fallback = _mk_test(
                "kruskalwallis",
                "Kruskal–Wallis test",
                "Non-parametric alternative when ANOVA assumptions are questionable.",
                {"dependent": outcome, "group": group_col},
                "/api/analysis/np-kruskalwallis",
                is_fallback=True,
            )

        return primary, fallback, warnings

    # ── Binary / categorical outcome ────────────────────────────────
    return (
        _mk_test("none", "Cannot recommend",
                 f"Outcome type '{outcome_type}' with group comparison is not directly supported. Try association testing.",
                 {}, ""),
        None,
        warnings + [f"Group comparison with outcome type '{outcome_type}' is not standard."],
    )


def _test_association(
    df: pd.DataFrame,
    req: SuggestTestRequest,
    vmap: Dict[str, VariableInfo],
) -> Tuple[TestRecommendation, Optional[TestRecommendation], List[str]]:
    outcome = req.outcome_variable
    group_col = req.group_variable

    if not outcome or not group_col:
        return (
            _mk_test("none", "Cannot recommend", "Two categorical variables are needed for association testing.", {}, ""),
            None,
            ["Select two categorical variables for association testing."],
        )

    outcome_type = _resolve_type(vmap.get(outcome))
    predictor_type = _resolve_type(vmap.get(group_col))

    if outcome_type in ("categorical", "binary", "ordinal", "event_indicator") and predictor_type in ("categorical", "binary", "ordinal", "event_indicator"):
        # Check for 2x2 for Fisher
        n_outcome = df[outcome].dropna().nunique()
        n_predictor = df[group_col].dropna().nunique()
        warnings: List[str] = []

        ct = pd.crosstab(df[outcome], df[group_col])
        min_expected = None
        try:
            _, _, _, expected = sp_stats.chi2_contingency(ct.values)
            min_expected = float(expected.min())
        except Exception:
            pass

        if n_outcome == 2 and n_predictor == 2 and min_expected is not None and min_expected < 5:
            return (
                _mk_test(
                    "fisher_exact",
                    "Fisher's exact test",
                    f"2×2 table with small expected counts (min={min_expected:.1f}).",
                    {"row": outcome, "col": group_col},
                    "/api/analysis/crosstab",
                ),
                _mk_test("chisquare", "Chi-square test", "Use if expected counts ≥ 5.", {"row": outcome, "col": group_col}, "/api/analysis/chisquare", is_fallback=True),
                warnings,
            )

        return (
            _mk_test(
                "chisquare",
                "Chi-square test of independence",
                f"Testing association between '{outcome}' and '{group_col}'.",
                {"row": outcome, "col": group_col},
                "/api/analysis/chisquare",
            ),
            _mk_test("fisher_exact", "Fisher's exact test", "Alternative for small samples.", {"row": outcome, "col": group_col}, "/api/analysis/crosstab", is_fallback=True),
            warnings,
        )

    return (
        _mk_test("none", "Cannot recommend", "Association testing requires two categorical variables.", {}, ""),
        None,
        [f"Variable types ({outcome_type}, {predictor_type}) are not both categorical."],
    )


def _correlation(
    df: pd.DataFrame,
    req: SuggestTestRequest,
    vmap: Dict[str, VariableInfo],
) -> Tuple[TestRecommendation, Optional[TestRecommendation], List[str]]:
    predictors = req.predictor_variables
    if not predictors or len(predictors) < 2:
        return (
            _mk_test("none", "Cannot recommend", "At least two numeric variables are needed for correlation.", {}, ""),
            None,
            ["Select at least two continuous variables."],
        )

    types = [_resolve_type(vmap.get(p)) for p in predictors]
    if all(t in ("continuous", "ordinal", "survival_time") for t in types):
        primary = _mk_test(
            "pearson",
            "Pearson correlation",
            f"Correlation between continuous variables: {', '.join(predictors[:3])}.",
            {"columns": predictors, "method": "pearson"},
            "/api/analysis/correlation",
        )
        fallback = _mk_test(
            "spearman",
            "Spearman rank correlation",
            "Non-parametric alternative when data is skewed or ordinal.",
            {"columns": predictors, "method": "spearman"},
            "/api/analysis/correlation",
            is_fallback=True,
        )
        return primary, fallback, []

    return (
        _mk_test("none", "Cannot recommend", "Correlation requires continuous or ordinal variables.", {}, ""),
        None,
        [f"Variable types {types} are not suitable for correlation."],
    )


def _model_predict(
    df: pd.DataFrame,
    req: SuggestTestRequest,
    vmap: Dict[str, VariableInfo],
) -> Tuple[TestRecommendation, Optional[TestRecommendation], List[str]]:
    outcome = req.outcome_variable
    predictors = req.predictor_variables

    if not outcome or not predictors:
        return (
            _mk_test("none", "Cannot recommend", "Outcome and at least one predictor are required.", {}, ""),
            None,
            ["Select an outcome variable and at least one predictor."],
        )

    outcome_type = _resolve_type(vmap.get(outcome))

    if outcome_type in ("continuous", "ordinal"):
        return (
            _mk_test(
                "linear_regression",
                "Linear regression",
                f"Predict continuous outcome '{outcome}' from {len(predictors)} predictor(s).",
                {"dependent": outcome, "independents": predictors, "method": "enter", "family": "linear"},
                "/api/analysis/linear-regression",
            ),
            None,
            [],
        )

    if outcome_type == "binary":
        return (
            _mk_test(
                "logistic_regression",
                "Logistic regression",
                f"Predict binary outcome '{outcome}' from {len(predictors)} predictor(s).",
                {"dependent": outcome, "independents": predictors, "method": "enter", "family": "logistic"},
                "/api/analysis/logistic-regression",
            ),
            None,
            [],
        )

    return (
        _mk_test("none", "Cannot recommend", f"Outcome type '{outcome_type}' is not supported for regression.", {}, ""),
        None,
        [f"Regression requires a continuous or binary outcome, got '{outcome_type}'."],
    )


def _survival_analysis(
    df: pd.DataFrame,
    req: SuggestTestRequest,
    vmap: Dict[str, VariableInfo],
) -> Tuple[TestRecommendation, Optional[TestRecommendation], List[str]]:
    time_col = req.time_variable
    event_col = req.event_variable
    group_col = req.group_variable

    if not time_col or not event_col:
        return (
            _mk_test("none", "Cannot recommend", "Time and event variables are required for survival analysis.", {}, ""),
            None,
            ["Select a time-to-event variable and an event indicator variable."],
        )

    if req.predictor_variables:
        # Has covariates → Cox
        covariates = req.predictor_variables
        return (
            _mk_test(
                "cox_regression",
                "Cox proportional hazards regression",
                f"Survival analysis with time '{time_col}', event '{event_col}', and {len(covariates)} covariate(s).",
                {"time_col": time_col, "status_col": event_col, "event_code": req.event_code, "covariates": covariates, "model_type": "cox"},
                "/api/analysis/cox-regression",
            ),
            None,
            [],
        )

    # Group comparison only → KM
    payload: Dict[str, Any] = {
        "time_col": time_col,
        "status_col": event_col,
        "event_code": req.event_code,
        "model_type": "kaplan-meier",
    }
    if group_col:
        payload["factors"] = [group_col]

    return (
        _mk_test(
            "kaplan_meier",
            "Kaplan–Meier survival analysis",
            f"Compare survival curves for time '{time_col}' and event '{event_col}'" + (f" grouped by '{group_col}'." if group_col else "."),
            payload,
            "/api/analysis/kaplan-meier",
        ),
        None,
        [],
    )


# ═══════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════

def recommend_test(df: pd.DataFrame, req: SuggestTestRequest) -> SuggestTestResponse:
    """Entry point: given a DataFrame and wizard input, return a recommendation."""
    # Infer variable types if not already done
    if req.variables:
        req.variables = infer_variable_types(df, req.variables)
    vmap = _get_type_map(req.variables)

    # Determine outcome / predictor types
    outcome_type: VariableType = "unknown"
    if req.outcome_variable:
        outcome_type = _resolve_type(vmap.get(req.outcome_variable))

    predictor_type: VariableType = "unknown"
    if req.group_variable:
        predictor_type = _resolve_type(vmap.get(req.group_variable))

    # Dispatch to the correct branch
    primary: TestRecommendation
    fallback: Optional[TestRecommendation] = None
    warnings: List[str] = []

    if req.goal == "compare_groups":
        primary, fallback, warnings = _compare_groups(df, req, vmap)
    elif req.goal == "test_association":
        primary, fallback, warnings = _test_association(df, req, vmap)
    elif req.goal == "correlation":
        primary, fallback, warnings = _correlation(df, req, vmap)
    elif req.goal == "model_predict":
        primary, fallback, warnings = _model_predict(df, req, vmap)
    elif req.goal == "survival_analysis":
        primary, fallback, warnings = _survival_analysis(df, req, vmap)
    else:
        primary = _mk_test("none", "Unknown goal", f"Goal '{req.goal}' is not recognized.", {}, "")
        warnings = [f"Unrecognized analysis goal: {req.goal}"]

    return SuggestTestResponse(
        goal=req.goal,
        outcome_type=outcome_type,
        predictor_type=predictor_type,
        paired=req.paired,
        num_groups=req.num_groups,
        primary=primary,
        fallback=fallback,
        warnings=warnings,
    )
