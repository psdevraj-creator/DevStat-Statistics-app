"""
Unit tests for the suggest-test recommendation engine.

Run:  cd "C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\backend" && python -m pytest tests\test_suggest.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import pytest
from app.models.suggest import SuggestTestRequest, VariableInfo
from app.services.suggest import recommend_test, _infer_variable_type


# ── Test fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def df_simple():
    """6 rows: time, status, age, group"""
    return pd.DataFrame({
        "time": [1, 2, 3, 5, 7, 10],
        "status": [1, 0, 1, 0, 1, 0],
        "age": [45, 62, 58, 71, 55, 60],
        "group": ["A", "A", "B", "B", "A", "B"],
    })


@pytest.fixture
def df_binary():
    """Binary outcome for logistic regression testing."""
    return pd.DataFrame({
        "outcome": [0, 1, 0, 1, 0, 1],
        "predictor": [10, 20, 15, 25, 12, 22],
        "category": ["X", "Y", "X", "Y", "X", "Y"],
    })


def make_vars(*cols: str) -> list:
    return [VariableInfo(column=c) for c in cols]


# ── Variable type inference ───────────────────────────────────────────

def test_infer_continuous():
    s = pd.Series([1.5, 2.3, 3.7, 4.1, 5.9], name="weight")
    assert _infer_variable_type(s, "weight") == "continuous"


def test_infer_binary_numeric():
    s = pd.Series([0, 1, 0, 1, 0], name="died")
    assert _infer_variable_type(s, "died") == "binary"


def test_infer_binary_string():
    s = pd.Series(["Yes", "No", "Yes", "No"], name="response")
    assert _infer_variable_type(s, "response") == "binary"


def test_infer_categorical():
    s = pd.Series(["A", "B", "C", "A", "B", "C", "D"], name="treatment")
    assert _infer_variable_type(s, "treatment") == "categorical"


def test_infer_survival_time():
    s = pd.Series([30, 60, 90, 120], name="followup_time")
    assert _infer_variable_type(s, "followup_time") == "survival_time"


def test_infer_event_indicator():
    s = pd.Series([0, 1, 0, 1], name="event_status")
    assert _infer_variable_type(s, "event_status") == "event_indicator"


def test_infer_unknown_on_empty():
    s = pd.Series([], dtype=float, name="empty_col")
    assert _infer_variable_type(s, "empty_col") == "unknown"


# ── Compare groups ────────────────────────────────────────────────────

def test_compare_2_independent_groups(df_simple):
    req = SuggestTestRequest(
        goal="compare_groups",
        outcome_variable="age",
        group_variable="group",
        num_groups=2,
        paired=False,
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="group", inferred_type="categorical")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "independent_ttest"
    assert res.primary.test_name == "Independent samples t-test"
    assert "age" in res.primary.rationale
    assert res.fallback is not None
    assert res.fallback.test_id == "mannwhitney"


def test_compare_2_paired_groups(df_simple):
    req = SuggestTestRequest(
        goal="compare_groups",
        outcome_variable="age",
        group_variable="group",
        num_groups=2,
        paired=True,
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="group", inferred_type="categorical")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "paired_ttest"
    assert res.fallback.test_id == "wilcoxon"


def test_compare_3plus_groups(df_simple):
    # Create 3 groups
    df = df_simple.copy()
    df["group3"] = ["A", "A", "B", "B", "C", "C"]
    req = SuggestTestRequest(
        goal="compare_groups",
        outcome_variable="age",
        group_variable="group3",
        num_groups=3,
        paired=False,
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="group3", inferred_type="categorical")],
    )
    res = recommend_test(df, req)
    assert res.primary.test_id == "oneway_anova"
    assert res.fallback.test_id == "kruskalwallis"


# ── Association ───────────────────────────────────────────────────────

def test_association_categorical(df_simple):
    req = SuggestTestRequest(
        goal="test_association",
        outcome_variable="group",
        group_variable="status",
        variables=[VariableInfo(column="group", inferred_type="categorical"),
                   VariableInfo(column="status", inferred_type="binary")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "fisher_exact"  # 2x2 with small n → Fisher's


# ── Correlation ───────────────────────────────────────────────────────

def test_correlation_continuous(df_simple):
    req = SuggestTestRequest(
        goal="correlation",
        predictor_variables=["age", "time"],
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="time", inferred_type="survival_time")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "pearson"
    assert res.fallback.test_id == "spearman"


# ── Regression ────────────────────────────────────────────────────────

def test_linear_regression(df_simple):
    req = SuggestTestRequest(
        goal="model_predict",
        outcome_variable="age",
        predictor_variables=["time"],
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="time", inferred_type="survival_time")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "linear_regression"


def test_logistic_regression(df_binary):
    req = SuggestTestRequest(
        goal="model_predict",
        outcome_variable="outcome",
        predictor_variables=["predictor"],
        variables=[VariableInfo(column="outcome", inferred_type="binary"),
                   VariableInfo(column="predictor", inferred_type="continuous")],
    )
    res = recommend_test(df_binary, req)
    assert res.primary.test_id == "logistic_regression"


# ── Survival ──────────────────────────────────────────────────────────

def test_survival_km(df_simple):
    req = SuggestTestRequest(
        goal="survival_analysis",
        time_variable="time",
        event_variable="status",
        group_variable="group",
        variables=[VariableInfo(column="time", inferred_type="survival_time"),
                   VariableInfo(column="status", inferred_type="event_indicator"),
                   VariableInfo(column="group", inferred_type="categorical")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "kaplan_meier"


def test_survival_cox(df_simple):
    req = SuggestTestRequest(
        goal="survival_analysis",
        time_variable="time",
        event_variable="status",
        predictor_variables=["age"],
        variables=[VariableInfo(column="time", inferred_type="survival_time"),
                   VariableInfo(column="status", inferred_type="event_indicator"),
                   VariableInfo(column="age", inferred_type="continuous")],
    )
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "cox_regression"


# ── Validation & edge cases ───────────────────────────────────────────

def test_missing_outcome_variable(df_simple):
    req = SuggestTestRequest(goal="compare_groups")
    res = recommend_test(df_simple, req)
    assert res.primary.test_id == "none"
    assert len(res.warnings) > 0


def test_payload_ready_for_use(df_simple):
    """The analysis_payload should be immediately POST-able to the endpoint."""
    req = SuggestTestRequest(
        goal="compare_groups",
        outcome_variable="age",
        group_variable="group",
        num_groups=2,
        paired=False,
        variables=[VariableInfo(column="age", inferred_type="continuous"),
                   VariableInfo(column="group", inferred_type="categorical")],
    )
    res = recommend_test(df_simple, req)
    payload = res.primary.analysis_payload
    assert "test_type" in payload
    assert "dependent" in payload
    assert "group" in payload
    assert res.primary.analysis_endpoint == "/api/analysis/ttest"


def test_variable_type_override(df_simple):
    """Override should take precedence over inferred type."""
    req = SuggestTestRequest(
        goal="model_predict",
        outcome_variable="age",
        predictor_variables=["time"],
        variables=[VariableInfo(column="age", inferred_type="continuous", override_type="binary"),
                   VariableInfo(column="time", inferred_type="survival_time")],
    )
    res = recommend_test(df_simple, req)
    # age overridden to binary → should recommend logistic, not linear
    assert res.primary.test_id == "logistic_regression"
