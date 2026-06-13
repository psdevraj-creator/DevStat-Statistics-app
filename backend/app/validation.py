"""
Input validation for analysis endpoints.

Blocks obviously nonsensical parameter combinations with clear error messages
before they reach R. Each check raises HTTPException(400) with a readable detail.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException


def validate_survival(
    time_col: str,
    status_col: str,
    factors: Optional[List[str]] = None,
    covariates: Optional[List[str]] = None,
):
    """Validate survival analysis parameters (KM / Cox)."""
    if not time_col:
        raise HTTPException(400, detail="Time-to-event column ('time_col') is required for survival analysis.")
    if not status_col:
        raise HTTPException(400, detail="Event indicator ('status_col') is required for survival analysis. "
                              "This column must contain 0/1 or TRUE/FALSE values.")
    if time_col == status_col:
        raise HTTPException(400, detail="Time column and event column must be different.")
    # Group factor is optional for KM; Cox checks its own requirements separately


def validate_regression(
    dependent: str,
    independents: List[str],
    family: Optional[str] = None,
):
    """Validate regression parameters (linear / logistic)."""
    if not dependent:
        raise HTTPException(400, detail="Dependent variable is required.")
    if not independents or len(independents) == 0:
        raise HTTPException(400, detail="At least one independent variable is required for regression.")
    if len(independents) > 50:
        raise HTTPException(400, detail=f"Too many predictors ({len(independents)}). Maximum is 50.")
    if dependent in independents:
        raise HTTPException(400, detail=f"A variable cannot predict itself ({dependent}).")
    # Check for duplicate independents
    seen = set()
    for iv in independents:
        if iv in seen:
            raise HTTPException(400, detail=f"Duplicate predictor '{iv}' in independents list.")
        seen.add(iv)


def validate_ttest(
    dependent: List[str],
    group: Optional[str] = None,
    variable1: Optional[str] = None,
    variable2: Optional[str] = None,
    test_type: Optional[str] = None,
):
    """Validate t-test / comparison parameters."""
    if test_type in ("independent",) and group:
        if not dependent or len(dependent) == 0:
            raise HTTPException(400, detail="At least one dependent variable is required.")
        if not group:
            raise HTTPException(400, detail="Group variable is required for independent t-test.")
    elif test_type == "paired" or (variable1 and variable2):
        if not variable1 or not variable2:
            raise HTTPException(400, detail="Both variable1 and variable2 are required for paired t-test.")
        if variable1 == variable2:
            raise HTTPException(400, detail="Paired test requires two different variables.")


def validate_anova(
    dependent: List[str],
    group: str,
    test_type: Optional[str] = None,
    factor1: Optional[str] = None,
    factor2: Optional[str] = None,
):
    """Validate ANOVA parameters."""
    if not dependent or len(dependent) == 0:
        raise HTTPException(400, detail="At least one dependent variable is required.")
    if not group and not factor1:
        raise HTTPException(400, detail="A grouping/factor variable is required.")
    if test_type == "twoway" and factor1 == factor2:
        raise HTTPException(400, detail="Two-way ANOVA requires two different factors.")


def validate_correlation(
    columns: List[str],
    method: Optional[str] = None,
):
    """Validate correlation parameters."""
    if not columns or len(columns) < 2:
        raise HTTPException(400, detail="At least two variables are required for correlation.")
    if method and method not in ("pearson", "spearman", "kendall"):
        raise HTTPException(400, detail=f"Correlation method must be pearson, spearman, or kendall (got '{method}').")


def validate_crosstab(
    row: str,
    col: str,
):
    """Validate crosstab parameters."""
    if not row:
        raise HTTPException(400, detail="Row variable is required.")
    if not col:
        raise HTTPException(400, detail="Column variable is required.")
    if row == col:
        raise HTTPException(400, detail="Row and column variables must be different.")


def validate_diagnostic(
    test_col: str,
    gold_col: str,
):
    """Validate diagnostic test parameters."""
    if not test_col:
        raise HTTPException(400, detail="Test/biomarker column is required.")
    if not gold_col:
        raise HTTPException(400, detail="Gold standard column is required.")
    if test_col == gold_col:
        raise HTTPException(400, detail="Test and gold standard columns must be different.")


def validate_factor_analysis(
    columns: List[str],
    n_factors: Optional[int] = None,
):
    """Validate factor analysis parameters."""
    if not columns or len(columns) < 3:
        raise HTTPException(400, detail="At least 3 variables are required for factor analysis.")
    if n_factors is not None:
        if n_factors < 1:
            raise HTTPException(400, detail="Number of factors must be at least 1.")
        if n_factors > len(columns):
            raise HTTPException(400, detail=f"Number of factors ({n_factors}) cannot exceed number of variables ({len(columns)}).")


def validate_power(
    test: str,
    effect_size: Optional[float] = None,
    power: Optional[float] = None,
    alpha: Optional[float] = None,
):
    """Validate power analysis parameters."""
    if not test:
        raise HTTPException(400, detail="Test type is required for power analysis.")
    valid_tests = ["ttest", "anova", "chisq", "correlation", "r"]
    if test not in valid_tests:
        raise HTTPException(400, detail=f"Power test type must be one of: {', '.join(valid_tests)}")
    if effect_size is not None and effect_size <= 0:
        raise HTTPException(400, detail="Effect size must be positive.")
    if power is not None and (power <= 0 or power >= 1):
        raise HTTPException(400, detail="Power must be between 0 and 1.")
    if alpha is not None and (alpha <= 0 or alpha >= 1):
        raise HTTPException(400, detail="Significance level (alpha) must be between 0 and 1.")


def validate_cluster(
    columns: List[str],
    n_clusters: Optional[int] = None,
):
    """Validate cluster analysis parameters."""
    if not columns or len(columns) < 2:
        raise HTTPException(400, detail="At least 2 variables are required for clustering.")
    if n_clusters is not None:
        if n_clusters < 2:
            raise HTTPException(400, detail="Number of clusters must be at least 2.")
        if n_clusters > len(columns) * 10:
            raise HTTPException(400, detail=f"Number of clusters ({n_clusters}) is too high for {len(columns)} variables.")


def validate_mixed_model(
    dv: str,
    fixed: List[str],
    random: Optional[List[str]] = None,
):
    """Validate mixed model parameters."""
    if not dv:
        raise HTTPException(400, detail="Dependent variable is required.")
    if not fixed or len(fixed) == 0:
        raise HTTPException(400, detail="At least one fixed effect is required.")
    if random and len(random) > 0:
        for rv in random:
            if rv in fixed:
                raise HTTPException(400, detail=f"'{rv}' cannot be both a fixed and random effect.")
            if rv == dv:
                raise HTTPException(400, detail=f"'{rv}' cannot be both the dependent variable and a random effect.")
