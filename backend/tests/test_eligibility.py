"""
Eligibility Engine — automated tests.

Tests cover inferential, descriptive, and chart blocking rules.
Run with: pytest backend/tests/test_eligibility.py
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.eligibility import (
    check_ttest_eligibility,
    check_paired_ttest_eligibility,
    check_anova_eligibility,
    check_mannwhitney_eligibility,
    check_wilcoxon_eligibility,
    check_kruskal_eligibility,
    check_chi_square_eligibility,
    check_mcnemar_eligibility,
    check_regression_eligibility,
    check_logistic_eligibility,
    check_survival_eligibility,
    check_correlation_eligibility,
    check_reliability_eligibility,
    check_factor_eligibility,
    check_descriptive_eligibility,
    check_chart_eligibility,
    ALLOWED,
)


# ══════════════════════════════════════════════════════════════════════════
# Inferential blocking tests
# ══════════════════════════════════════════════════════════════════════════

def test_ttest_allowed():
    """Independent t-test with 2 groups should pass."""
    result = check_ttest_eligibility(n_groups=2)
    assert result["eligible"] is True, f"Expected allowed, got: {result}"


def test_ttest_too_many_groups():
    """T-test with 4 groups should be blocked."""
    result = check_ttest_eligibility(n_groups=4)
    assert result["blocked"], "Should block t-test with 4 groups"
    assert "ANOVA" in str(result["suggested_alternatives"])
    assert "4 levels" in result["details"]


def test_ttest_paired_structure():
    """T-test with paired data should be blocked."""
    result = check_ttest_eligibility(n_groups=2, is_paired=True)
    assert result["blocked"], "Should block when paired structure detected"
    assert "paired" in result["reason"].lower()


def test_ttest_one_group():
    """T-test with 1 group should be blocked."""
    result = check_ttest_eligibility(n_groups=1)
    assert result["blocked"]


def test_paired_ttest_independent():
    """Paired t-test with independent structure should be blocked."""
    result = check_paired_ttest_eligibility(is_paired=False)
    assert result["blocked"]
    assert "Mann-Whitney" in str(result["suggested_alternatives"]) or "independent" in result["reason"].lower()


def test_anova_allowed():
    """ANOVA with 3+ groups should pass."""
    result = check_anova_eligibility(n_groups=3)
    assert result["eligible"]


def test_anova_too_few_groups():
    """ANOVA with 2 groups should suggest t-test."""
    result = check_anova_eligibility(n_groups=2)
    assert result["blocked"]
    assert "t-test" in str(result["suggested_alternatives"])


def test_anova_paired():
    """ANOVA with paired data should suggest rm-ANOVA."""
    result = check_anova_eligibility(n_groups=3, is_paired=True)
    assert result["blocked"]
    assert "Friedman" in str(result["suggested_alternatives"])


def test_mannwhitney_paired():
    """Mann-Whitney with paired data should suggest Wilcoxon."""
    result = check_mannwhitney_eligibility(n_groups=2, is_paired=True)
    assert result["blocked"]
    assert "Wilcoxon" in str(result["suggested_alternatives"])


def test_mannwhitney_too_many_groups():
    """Mann-Whitney with 4 groups should suggest Kruskal-Wallis."""
    result = check_mannwhitney_eligibility(n_groups=4)
    assert result["blocked"]
    assert "Kruskal-Wallis" in str(result["suggested_alternatives"])


def test_wilcoxon_independent():
    """Wilcoxon signed-rank with independent data should be blocked."""
    result = check_wilcoxon_eligibility(is_paired=False)
    assert result["blocked"]
    assert "Mann-Whitney" in str(result["suggested_alternatives"])


def test_kruskal_too_few_groups():
    """Kruskal-Wallis with 2 groups should suggest Mann-Whitney."""
    result = check_kruskal_eligibility(n_groups=2)
    assert result["blocked"]
    assert "Mann-Whitney" in str(result["suggested_alternatives"])


def test_kruskal_paired():
    """Kruskal-Wallis with paired data should suggest Friedman."""
    result = check_kruskal_eligibility(n_groups=3, is_paired=True)
    assert result["blocked"]
    assert "Friedman" in str(result["suggested_alternatives"])


def test_chi_square_continuous():
    """Chi-square on continuous variable should be blocked."""
    result = check_chi_square_eligibility(dep_type="continuous")
    assert result["blocked"]
    assert "categorical" in result["reason"].lower()


def test_mcnemar_independent():
    """McNemar with independent data should be blocked."""
    result = check_mcnemar_eligibility(is_paired=False)
    assert result["blocked"]


def test_linear_regression_binary():
    """Linear regression with binary outcome should suggest logistic."""
    result = check_regression_eligibility(dep_type="binary")
    assert result["blocked"]
    assert "logistic" in str(result["suggested_alternatives"]).lower()


def test_linear_regression_survival():
    """Linear regression on time-to-event should suggest Cox."""
    result = check_regression_eligibility(is_time_to_event=True)
    assert result["blocked"]
    assert "Cox" in str(result["suggested_alternatives"])


def test_logistic_continuous():
    """Logistic regression with continuous outcome should suggest linear."""
    result = check_logistic_eligibility(dep_type="continuous")
    assert result["blocked"]
    assert "linear" in str(result["suggested_alternatives"]).lower()


def test_survival_no_event():
    """KM/Cox without event indicator should be blocked."""
    result = check_survival_eligibility(has_time=True, has_event=False)
    assert result["blocked"]
    assert "event indicator" in result["details"].lower() or "event" in result["reason"].lower()


def test_survival_no_time():
    """KM/Cox without time variable should be blocked."""
    result = check_survival_eligibility(has_time=False, has_event=True)
    assert result["blocked"]


def test_correlation_non_numeric():
    """Correlation with non-numeric variables should be blocked."""
    result = check_correlation_eligibility(var_types=["nominal", "nominal"])
    assert result["blocked"]


def test_reliability_too_few():
    """Reliability with 1 item should be blocked."""
    result = check_reliability_eligibility(n_items=1)
    assert result["blocked"]


def test_factor_too_few():
    """Factor analysis with 2 variables should be blocked."""
    result = check_factor_eligibility(n_vars=2)
    assert result["blocked"]
    assert "3 variables" in result["reason"]


# ══════════════════════════════════════════════════════════════════════════
# Descriptive blocking tests
# ══════════════════════════════════════════════════════════════════════════

def test_mean_for_nominal_blocked():
    """Mean for nominal data should be blocked."""
    result = check_descriptive_eligibility("mean", "nominal", "diagnosis")
    assert result["blocked"]
    assert "frequency" in str(result["suggested_alternatives"]).lower()


def test_mean_for_continuous_allowed():
    """Mean for continuous data should pass."""
    result = check_descriptive_eligibility("mean", "continuous", "age")
    assert result["eligible"]


def test_sd_for_ordinal_blocked():
    """SD for ordinal data should be blocked."""
    result = check_descriptive_eligibility("sd", "ordinal", "stage_label")
    assert result["blocked"]
    assert "IQR" in str(result["suggested_alternatives"])


def test_median_for_nominal_blocked():
    """Median for nominal data should be blocked."""
    result = check_descriptive_eligibility("median", "nominal", "treatment")
    assert result["blocked"]


def test_frequency_for_continuous_blocked():
    """Frequency table for continuous data should be blocked."""
    result = check_descriptive_eligibility("frequency", "continuous", "age")
    assert result["blocked"]
    assert "histogram" in str(result["suggested_alternatives"]).lower()


def test_proportion_for_continuous_blocked():
    """Proportion for continuous data should be blocked."""
    result = check_descriptive_eligibility("proportion", "continuous", "age")
    assert result["blocked"]


def test_survival_summary_for_non_survival_blocked():
    """Survival summary for non-survival data should be blocked."""
    result = check_descriptive_eligibility("survival_summary", "continuous", "age")
    assert result["blocked"]


# ══════════════════════════════════════════════════════════════════════════
# Chart blocking tests
# ══════════════════════════════════════════════════════════════════════════

def test_histogram_for_nominal_blocked():
    """Histogram for nominal data should be blocked."""
    result = check_chart_eligibility("histogram", x_type="nominal")
    assert result["blocked"]
    assert "bar" in str(result["suggested_alternatives"]).lower()


def test_scatter_for_categorical_x_blocked():
    """Scatter with categorical x should be blocked."""
    result = check_chart_eligibility("scatter", x_type="nominal", y_type="continuous")
    assert result["blocked"]


def test_scatter_for_categorical_y_blocked():
    """Scatter with categorical y should be blocked."""
    result = check_chart_eligibility("scatter", x_type="continuous", y_type="nominal")
    assert result["blocked"]


def test_line_for_nominal_blocked():
    """Line chart for unordered categories should be blocked."""
    result = check_chart_eligibility("line", x_type="nominal")
    assert result["blocked"]
    assert "bar" in str(result["suggested_alternatives"]).lower()


def test_pie_too_many_categories():
    """Pie chart with too many categories should be blocked."""
    result = check_chart_eligibility("pie", x_type="nominal", n_x_categories=14)
    assert result["blocked"]
    assert "bar" in str(result["suggested_alternatives"]).lower()


def test_boxplot_categorical_y():
    """Boxplot with categorical y-variable should be blocked."""
    result = check_chart_eligibility("boxplot", x_type="nominal", y_type="nominal")
    assert result["blocked"]


def test_km_no_event():
    """KM curve without event indicator should be blocked."""
    result = check_chart_eligibility("km", has_time=True, has_event=False)
    assert result["blocked"]
    assert "event" in result["reason"].lower()


def test_km_no_time():
    """KM curve without time variable should be blocked."""
    result = check_chart_eligibility("km", has_time=False, has_event=True)
    assert result["blocked"]


def test_stacked_bar_too_many():
    """Stacked bar with too many categories should be blocked."""
    result = check_chart_eligibility("stacked_bar", x_type="nominal", n_x_categories=15)
    assert result["blocked"]


def test_bar_for_continuous_suggests_histogram():
    """Bar chart for continuous data should suggest histogram."""
    result = check_chart_eligibility("bar", x_type="continuous")
    assert result["blocked"]
    assert "histogram" in str(result["suggested_alternatives"]).lower()


def test_pie_allowed():
    """Pie with few categories should pass."""
    result = check_chart_eligibility("pie", x_type="nominal", n_x_categories=3)
    assert result["eligible"]


def test_km_allowed():
    """KM with time and event should pass."""
    result = check_chart_eligibility("km", has_time=True, has_event=True)
    assert result["eligible"]


if __name__ == "__main__":
    # Run all tests manually
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test_fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed, {failed} failed")
