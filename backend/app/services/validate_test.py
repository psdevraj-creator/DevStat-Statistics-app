"""
Test compatibility matrix and 3-tier safety validation.

Each supported test defines its input contract.  When a user manually
overrides the recommendation and selects a different test, the engine
checks it against this matrix and returns one of three tiers:

  soft      – suboptimal but acceptable; warn and allow "Continue anyway"
  interrupt – likely wrong; require a structured override reason
  hard      – fundamentally incompatible; block and explain why
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from app.models.suggest import VariableType

# ── Types ─────────────────────────────────────────────────────────────

SafetyTier = Literal["compatible", "soft", "interrupt", "hard"]

def _rule(tier: SafetyTier, message: str, violated_rule: str = "", recommended: str = "") -> dict:
    return {"tier": tier, "message": message, "violated_rule": violated_rule or message, "recommended_alternative": recommended or None}

# ═══════════════════════════════════════════════════════════════════════
# Test compatibility matrix
# ═══════════════════════════════════════════════════════════════════════

# Each entry defines the ideal input contract for a test.
# Keys match the test_id used in recommendations.

TEST_CONTRACTS: Dict[str, dict] = {
    # ── T-tests ──────────────────────────────────────────────────────
    "independent_ttest": {
        "name": "Independent samples t-test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal"],
        "group_type": ["categorical", "binary"],
        "min_groups": 2,
        "max_groups": 2,
        "paired": False,
        "endpoint": "/api/analysis/ttest",
    },
    "paired_ttest": {
        "name": "Paired t-test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal"],
        "group_type": ["categorical", "binary"],
        "min_groups": 2,
        "max_groups": 2,
        "paired": True,
        "endpoint": "/api/analysis/ttest",
    },

    # ── Non-parametric ───────────────────────────────────────────────
    "mannwhitney": {
        "name": "Mann–Whitney U test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal", "survival_time"],
        "group_type": ["categorical", "binary"],
        "min_groups": 2,
        "max_groups": 2,
        "paired": False,
        "endpoint": "/api/analysis/np-mannwhitney",
    },
    "wilcoxon": {
        "name": "Wilcoxon signed-rank test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal"],
        "group_type": ["categorical", "binary"],
        "min_groups": 2,
        "max_groups": 2,
        "paired": True,
        "endpoint": "/api/analysis/np-wilcoxon",
    },
    "kruskalwallis": {
        "name": "Kruskal–Wallis test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal", "survival_time"],
        "group_type": ["categorical", "binary"],
        "min_groups": 3,
        "max_groups": 99,
        "paired": False,
        "endpoint": "/api/analysis/np-kruskalwallis",
    },
    "oneway_anova": {
        "name": "One-way ANOVA",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["continuous", "ordinal"],
        "group_type": ["categorical", "binary"],
        "min_groups": 3,
        "max_groups": 99,
        "paired": False,
        "endpoint": "/api/analysis/anova",
    },

    # ── Association ──────────────────────────────────────────────────
    "chisquare": {
        "name": "Chi-square test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["categorical", "binary", "ordinal", "event_indicator"],
        "group_type": ["categorical", "binary", "ordinal", "event_indicator"],
        "min_groups": 2,
        "max_groups": 99,
        "paired": False,
        "endpoint": "/api/analysis/chisquare",
    },
    "fisher_exact": {
        "name": "Fisher's exact test",
        "requires": ["outcome_variable", "group_variable"],
        "outcome_type": ["categorical", "binary", "ordinal", "event_indicator"],
        "group_type": ["categorical", "binary", "ordinal", "event_indicator"],
        "min_groups": 2,
        "max_groups": 2,
        "paired": False,
        "endpoint": "/api/analysis/crosstab",
    },

    # ── Correlation ──────────────────────────────────────────────────
    "pearson": {
        "name": "Pearson correlation",
        "requires": ["predictor_variables"],
        "outcome_type": [],  # N/A — uses predictor_variables
        "group_type": [],
        "min_groups": 0,
        "max_groups": 0,
        "paired": False,
        "endpoint": "/api/analysis/correlation",
    },
    "spearman": {
        "name": "Spearman rank correlation",
        "requires": ["predictor_variables"],
        "outcome_type": [],
        "group_type": [],
        "min_groups": 0,
        "max_groups": 0,
        "paired": False,
        "endpoint": "/api/analysis/correlation",
    },

    # ── Regression ───────────────────────────────────────────────────
    "linear_regression": {
        "name": "Linear regression",
        "requires": ["outcome_variable", "predictor_variables"],
        "outcome_type": ["continuous", "ordinal", "survival_time"],
        "group_type": [],
        "min_groups": 0,
        "max_groups": 0,
        "paired": False,
        "endpoint": "/api/analysis/linear-regression",
    },
    "logistic_regression": {
        "name": "Logistic regression",
        "requires": ["outcome_variable", "predictor_variables"],
        "outcome_type": ["binary", "event_indicator"],
        "group_type": [],
        "min_groups": 0,
        "max_groups": 0,
        "paired": False,
        "endpoint": "/api/analysis/logistic-regression",
    },

    # ── Survival ─────────────────────────────────────────────────────
    "kaplan_meier": {
        "name": "Kaplan–Meier survival analysis",
        "requires": ["time_variable", "event_variable"],
        "outcome_type": [],
        "group_type": ["categorical", "binary"],
        "min_groups": 0,
        "max_groups": 99,
        "paired": False,
        "endpoint": "/api/analysis/kaplan-meier",
    },
    "cox_regression": {
        "name": "Cox proportional hazards regression",
        "requires": ["time_variable", "event_variable", "predictor_variables"],
        "outcome_type": [],
        "group_type": [],
        "min_groups": 0,
        "max_groups": 0,
        "paired": False,
        "endpoint": "/api/analysis/cox-regression",
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════

def validate_test_choice(
    test_id: str,
    outcome_variable: Optional[str],
    group_variable: Optional[str],
    predictor_variables: List[str],
    time_variable: Optional[str],
    event_variable: Optional[str],
    outcome_type: VariableType,
    group_type: VariableType,
    paired: bool,
    num_groups: int,
) -> dict:
    """
    Check a user-chosen test against its input contract.

    Returns a dict with:
      - ``tier``: "compatible" | "soft" | "interrupt" | "hard"
      - ``message``: human-readable explanation
      - ``violated_rule``: which rule was broken (for logging)
      - ``recommended_alternative``: suggested better test (if known)
    """
    contract = TEST_CONTRACTS.get(test_id)
    if contract is None:
        return _rule("hard", f"Unknown test '{test_id}'. Please select a supported test.")

    name = contract["name"]
    issues: List[dict] = []

    # ── Hard stops: missing required inputs ─────────────────────────
    for field in contract["requires"]:
        if field == "outcome_variable" and not outcome_variable:
            return _rule("hard",
                f"{name} requires an outcome variable. Please select one.",
                "missing_outcome")
        if field == "group_variable" and not group_variable:
            return _rule("hard",
                f"{name} requires a group variable. Please select one.",
                "missing_group")
        if field == "predictor_variables" and (not predictor_variables or len(predictor_variables) == 0):
            return _rule("hard",
                f"{name} requires at least one predictor variable. Please select one or more.",
                "missing_predictors")
        if field == "time_variable" and not time_variable:
            return _rule("hard",
                f"{name} requires a time variable. Please select one.",
                "missing_time")
        if field == "event_variable" and not event_variable:
            return _rule("hard",
                f"{name} requires an event variable. Please select one.",
                "missing_event")

    # ── Outcome type compatibility ──────────────────────────────────
    allowed_outcome = contract["outcome_type"]
    if allowed_outcome and outcome_type not in allowed_outcome:
        allowed_str = ", ".join(allowed_outcome)
        issues.append(_rule("hard",
            f"{name} requires an outcome of type {allowed_str}, but yours is '{outcome_type}'. "
            f"Cannot run this test with this outcome variable.",
            "incompatible_outcome_type",
            _find_alternative(test_id, outcome_type)))

    # ── Group type compatibility ────────────────────────────────────
    allowed_group = contract["group_type"]
    if allowed_group and group_variable and group_type not in allowed_group:
        allowed_str = ", ".join(allowed_group)
        issues.append(_rule("hard",
            f"{name} expects group type {allowed_str}, but yours is '{group_type}'.",
            "incompatible_group_type"))

    # ── Number of groups ────────────────────────────────────────────
    min_g = contract["min_groups"]
    max_g = contract["max_groups"]
    if min_g > 0 and group_variable and num_groups < min_g:
        issues.append(_rule("hard",
            f"{name} requires at least {min_g} groups, but you have {num_groups}.",
            "too_few_groups"))
    if max_g > 0 and group_variable and num_groups > max_g:
        issues.append(_rule("hard",
            f"{name} supports up to {max_g} groups, but you have {num_groups}.",
            "too_many_groups"))

    # ── Paired vs independent ───────────────────────────────────────
    if contract["paired"] and not paired:
        issues.append(_rule("interrupt",
            f"{name} is a paired test, but your design is independent. "
            f"Consider an independent-samples test instead.",
            "design_paired_mismatch",
            "independent_ttest" if "ttest" in test_id else None))
    if not contract["paired"] and paired:
        issues.append(_rule("interrupt",
            f"{name} is an independent-samples test, but your design is paired. "
            f"Consider a paired test instead.",
            "design_independent_mismatch",
            "paired_ttest" if "ttest" in test_id else None))

    # ── Soft: suboptimal but possible ───────────────────────────────
    # (e.g., non-parametric chosen when parametric would work fine)
    if test_id in ("mannwhitney", "wilcoxon", "kruskalwallis", "spearman"):
        if outcome_type in ("continuous",) and test_id not in ("kruskalwallis",):
            issues.append(_rule("soft",
                f"{name} is a non-parametric test. Your data appears continuous; "
                f"a parametric test may have more statistical power. You can still proceed.",
                "parametric_available",
                {"mannwhitney": "independent_ttest", "wilcoxon": "paired_ttest",
                 "kruskalwallis": "oneway_anova", "spearman": "pearson"}.get(test_id)))

    # ── Determine overall tier ──────────────────────────────────────
    if not issues:
        return _rule("compatible", f"{name} is compatible with your data and design.")

    tiers = [i["tier"] for i in issues]
    if "hard" in tiers:
        hard_issues = [i for i in issues if i["tier"] == "hard"]
        return _rule("hard",
            "; ".join(i["message"] for i in hard_issues),
            hard_issues[0]["violated_rule"],
            hard_issues[0].get("recommended_alternative"))

    if "interrupt" in tiers:
        interrupt_issues = [i for i in issues if i["tier"] == "interrupt"]
        return _rule("interrupt",
            "; ".join(i["message"] for i in interrupt_issues),
            interrupt_issues[0]["violated_rule"],
            interrupt_issues[0].get("recommended_alternative"))

    soft_issues = [i for i in issues if i["tier"] == "soft"]
    return _rule("soft",
        "; ".join(i["message"] for i in soft_issues),
        soft_issues[0]["violated_rule"],
        soft_issues[0].get("recommended_alternative"))


def _find_alternative(test_id: str, outcome_type: VariableType) -> Optional[str]:
    """Suggest an alternative test that accepts the given outcome type."""
    alt_map = {
        "binary": "logistic_regression",
        "continuous": "linear_regression",
        "categorical": "chisquare",
        "survival_time": "cox_regression",
        "event_indicator": "logistic_regression",
    }
    return alt_map.get(outcome_type)
