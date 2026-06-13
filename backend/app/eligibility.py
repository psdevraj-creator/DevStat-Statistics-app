"""
Eligibility Engine — statistical guardrail system.

Blocks nonsensical analyses, descriptives, and charts before they run.
Single pre-execution layer with consistent response contract.

Contract:
    eligible: bool
    blocked: bool (True when blocked)
    requested_action: str
    action_type: "test" | "descriptive" | "chart"
    reason: str           -- one-line reason
    details: str          -- what property of the data triggered the block
    triggering_data_properties: list[str]
    suggested_alternatives: list[str]   -- flat list for frontend
    alternative_ranked: dict            -- {preferred: [], acceptable: [], advanced: []}
    inferred_data_role: dict           -- {outcome_type, grouping_type, paired_structure}
    help_terms: list[str]  -- terms that should have tooltips
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── Blocked response builder ──────────────────────────────────────────────

BLOCKED: Dict[str, Any] = {
    "eligible": False,
    "blocked": True,
    "requested_action": "",
    "action_type": "",
    "reason": "",
    "details": "",
    "triggering_data_properties": [],
    "suggested_alternatives": [],
    "help_terms": [],
}

ALLOWED: Dict[str, Any] = {"eligible": True, "blocked": False}


def _block(
    action: str,
    action_type: str,
    reason: str,
    details: str = "",
    properties: Optional[List[str]] = None,
    alternatives: Optional[List[str]] = None,
    ranked: Optional[Dict[str, List[str]]] = None,
    data_role: Optional[Dict[str, str]] = None,
    help_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "eligible": False,
        "blocked": True,
        "requested_action": action,
        "action_type": action_type,
        "reason": reason,
        "details": details,
        "triggering_data_properties": properties or [],
        "suggested_alternatives": alternatives or [],
        "alternative_ranked": ranked or {"preferred": [], "acceptable": [], "advanced": []},
        "inferred_data_role": data_role or {},
        "help_terms": help_terms or [],
    }


# ── Variable type inference ──────────────────────────────────────────────

def infer_variable_type(
    name: str,
    dtype: str,
    unique_count: int,
    n_rows: int,
    is_numeric: bool,
) -> str:
    """Infer statistical variable type from metadata."""
    # Time-to-event: check by name convention
    if any(kw in name.lower() for kw in ["survival", "surv_time", "time_to", "tt_event", "death_time"]):
        return "time_to_event"
    if "event" in name.lower() and unique_count <= 2:
        return "event_indicator"

    # Binary: exactly 2 unique values, 0/1 or TRUE/FALSE
    if unique_count == 2 and is_numeric:
        return "binary"
    if unique_count == 2:
        # Check if values look like yes/no, male/female
        return "binary_nominal"

    # Date
    if dtype == "date" or "date" in name.lower():
        return "date"

    # Count: integer with many unique values but no decimal
    if "count" in name.lower() or "num_" in name.lower() or is_numeric and unique_count > 10:
        return "continuous"

    # Nominal: string with few unique values
    if not is_numeric and unique_count <= 20:
        return "nominal"

    # Ordinal: named with stage/grade/level
    if any(kw in name.lower() for kw in ["stage", "grade", "level", "class"]):
        return "ordinal"

    # Default fallback
    return "nominal" if not is_numeric else "continuous"


# ── Descriptive eligibility ──────────────────────────────────────────────

DESCRIPTIVE_RULES: Dict[str, Dict[str, Any]] = {
    "mean": {
        "allow_types": ["continuous", "unknown"],
        "reason": "Mean is meaningful only for numeric continuous data.",
        "alternatives": {"nominal": "Use frequency table (counts and percentages).",
                         "binary_nominal": "Use proportions and percentages.",
                         "ordinal": "Use median and IQR, or frequency table.",
                         "binary": "Use proportions.",
                         "date": "Mean of dates is not meaningful. Use counts by period.",
                         "time_to_event": "Use survival summaries (KM median survival)."},
        "help": ["mean", "continuous"],
    },
    "median": {
        "allow_types": ["continuous", "ordinal", "unknown"],
        "reason": "Median requires ordered data.",
        "alternatives": {"nominal": "Use frequencies and mode instead.",
                         "binary_nominal": "Use proportions instead."},
        "help": ["median"],
    },
    "sd": {
        "allow_types": ["continuous", "unknown"],
        "reason": "Standard deviation is meaningful only for numeric continuous data.",
        "alternatives": {"ordinal": "Use IQR.",
                         "nominal": "Use frequency distribution.",
                         "time_to_event": "Use survival quartiles instead."},
        "help": ["sd", "interquartile_range"],
    },
    "iqr": {
        "allow_types": ["continuous", "ordinal", "unknown"],
        "reason": "IQR requires ordered data.",
        "alternatives": {"nominal": "Not applicable for categories."},
        "help": ["interquartile_range"],
    },
    "min_max": {
        "allow_types": ["continuous", "ordinal", "date"],
        "reason": "Range requires numeric or date data.",
        "alternatives": {"nominal": "Not applicable."},
        "help": [],
    },
    "frequency": {
        "allow_types": ["nominal", "binary_nominal", "ordinal", "binary"],
        "reason": "Frequency tables are for categorical data.",
        "alternatives": {"continuous": "Use histogram or descriptive statistics (mean, SD, median, IQR)."},
        "help": [],
    },
    "proportion": {
        "allow_types": ["nominal", "binary_nominal", "binary"],
        "reason": "Proportions require categorical or binary data.",
        "alternatives": {"continuous": "Use descriptive statistics.",
                         "ordinal": "Use median and IQR."},
        "help": [],
    },
    "survival_summary": {
        "allow_types": ["time_to_event"],
        "reason": "Survival summaries require time-to-event data with event indicator.",
        "alternatives": {"continuous": "Use ordinary descriptive statistics."},
        "help": ["censoring", "survival"],
    },
}


def check_descriptive_eligibility(
    action: str,
    var_type: str,
    var_name: str,
) -> Dict[str, Any]:
    """Check if a descriptive summary is allowed for the variable type."""
    rule = DESCRIPTIVE_RULES.get(action)
    if not rule:
        return ALLOWED

    if var_type in rule["allow_types"]:
        return ALLOWED

    alt = rule["alternatives"].get(var_type, "Try a different summary appropriate for this variable type.")
    return _block(
        action=f"{action} of {var_name}",
        action_type="descriptive",
        reason=rule["reason"],
        details=f"Variable '{var_name}' is type '{var_type}', which does not support '{action}'.",
        properties=[f"variable_type={var_type}"],
        alternatives=[alt] if isinstance(alt, str) else alt,
        help_terms=rule["help"],
    )


# ── Inferential test eligibility ─────────────────────────────────────────

def _n_groups_str(n: int) -> str:
    if n == 0: return "0 levels"
    if n == 1: return "1 level"
    if n == 2: return "2 levels"
    return f"{n} levels"


def check_ttest_eligibility(
    n_groups: int,
    is_paired: bool = False,
    dep_type: str = "continuous",
    outcome_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check independent/paired t-test eligibility."""
    if dep_type not in ("continuous", "ordinal", "unknown"):
        return _block("Independent-samples t-test", "test",
            "T-test requires a numeric continuous outcome variable.",
            f"Outcome variable type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use chi-square test for categorical outcomes.",
                          "Use Mann-Whitney U test for ordinal outcomes."],
            ranked={"preferred": ["Mann-Whitney U test"],
                    "acceptable": ["Chi-square test for categorical outcomes"],
                    "advanced": []},
            help_terms=["continuous"])

    if is_paired:
        return _block("Independent-samples t-test", "test",
            "Data appears to be paired or matched.",
            "Paired structure detected in the data.",
            properties=["paired_structure"],
            alternatives=["Use paired t-test.",
                          "Use Wilcoxon signed-rank test (non-parametric alternative)."],
            ranked={"preferred": ["Paired t-test"],
                    "acceptable": ["Wilcoxon signed-rank test"],
                    "advanced": []},
            help_terms=["paired_data", "independent_groups"])

    if n_groups > 2:
        return _block("Independent-samples t-test", "test",
            "This test compares exactly 2 independent groups.",
            f"Your grouping variable has {_n_groups_str(n_groups)}.",
            properties=[f"n_groups={n_groups}"],
            alternatives=["Use one-way ANOVA (parametric, 2+ groups).",
                          "Use Kruskal-Wallis test (non-parametric, 2+ groups)."],
            ranked={"preferred": ["One-way ANOVA"],
                    "acceptable": ["Kruskal-Wallis test"],
                    "advanced": []},
            help_terms=["independent_groups"])

    if n_groups == 1:
        return _block("Independent-samples t-test", "test",
            "This test compares exactly 2 independent groups.",
            "Your grouping variable has 1 level.",
            properties=["n_groups=1"],
            alternatives=["Use a one-sample t-test instead.",
                          "Use a one-sample Wilcoxon signed-rank test."],
            ranked={"preferred": ["One-sample t-test"],
                    "acceptable": ["One-sample Wilcoxon signed-rank test"],
                    "advanced": []},
            help_terms=["independent_groups"])

    return ALLOWED


def check_paired_ttest_eligibility(
    is_paired: bool = False,
    dep_type: str = "continuous",
) -> Dict[str, Any]:
    if dep_type not in ("continuous",):
        return _block("Paired t-test", "test",
            "Paired t-test requires a continuous outcome.",
            f"Outcome type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use McNemar test for paired binary data.",
                          "Use Wilcoxon signed-rank test for paired ordinal data."],
            ranked={"preferred": ["Wilcoxon signed-rank test"],
                    "acceptable": ["McNemar test for paired binary data"],
                    "advanced": []},
            help_terms=["paired_data"])
    if not is_paired:
        return _block("Paired t-test", "test",
            "Samples appear to be independent, not paired.",
            "Paired structure was not detected.",
            properties=["independent_structure"],
            alternatives=["Use independent-samples t-test.",
                          "Use Mann-Whitney U test."],
            ranked={"preferred": ["Independent-samples t-test"],
                    "acceptable": ["Mann-Whitney U test"],
                    "advanced": []},
            help_terms=["paired_data", "independent_groups"])
    return ALLOWED


def check_anova_eligibility(
    n_groups: int,
    dep_type: str = "continuous",
    is_paired: bool = False,
) -> Dict[str, Any]:
    if dep_type not in ("continuous", "unknown"):
        return _block("One-way ANOVA", "test",
            "ANOVA requires a continuous outcome variable.",
            f"Outcome type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use chi-square test for categorical outcomes.",
                          "Use Kruskal-Wallis test for ordinal outcomes."],
            ranked={"preferred": ["Kruskal-Wallis test"],
                    "acceptable": ["Chi-square test for categorical outcomes"],
                    "advanced": []},
            help_terms=["continuous"])
    if is_paired:
        return _block("One-way ANOVA", "test",
            "Data appears to be paired or repeated measures.",
            "Paired structure detected.",
            properties=["paired_structure"],
            alternatives=["Use repeated-measures ANOVA.",
                          "Use Friedman test (non-parametric)."],
            ranked={"preferred": ["Repeated-measures ANOVA"],
                    "acceptable": ["Friedman test"],
                    "advanced": []},
            help_terms=["paired_data"])
    if n_groups < 2:
        return _block("One-way ANOVA", "test",
            "ANOVA requires 2 or more groups to compare.",
            f"Grouping variable has {_n_groups_str(n_groups)}.",
            properties=[f"n_groups={n_groups}"],
            alternatives=["If you have 2 groups, use independent t-test.",
                          "If you have 1 group, use a one-sample test."],
            ranked={"preferred": ["Independent t-test (2 groups)"],
                    "acceptable": ["One-sample test (1 group)"],
                    "advanced": []},
            help_terms=[])
    if n_groups == 2:
        return _block("One-way ANOVA", "test",
            "ANOVA is for 3+ groups. For exactly 2 groups, a t-test is simpler.",
            f"Grouping variable has 2 levels.",
            properties=["n_groups=2"],
            alternatives=["Use independent-samples t-test (simpler, equivalent).",
                          "Use Mann-Whitney U test (non-parametric)."],
            ranked={"preferred": ["Independent-samples t-test"],
                    "acceptable": ["Mann-Whitney U test"],
                    "advanced": []},
            help_terms=[])
    return ALLOWED


def check_mannwhitney_eligibility(
    n_groups: int,
    is_paired: bool = False,
    dep_type: str = "continuous",
) -> Dict[str, Any]:
    if is_paired:
        return _block("Mann-Whitney U test", "test",
            "Mann-Whitney requires 2 independent groups.",
            "Paired structure detected.",
            properties=["paired_structure"],
            alternatives=["Use Wilcoxon signed-rank test for paired data."],
            ranked={"preferred": ["Wilcoxon signed-rank test"],
                    "acceptable": ["Paired t-test"],
                    "advanced": []},
            help_terms=["independent_groups", "paired_data"])
    if n_groups > 2:
        return _block("Mann-Whitney U test", "test",
            "This test compares exactly 2 independent groups.",
            f"Grouping variable has {_n_groups_str(n_groups)}.",
            properties=[f"n_groups={n_groups}"],
            alternatives=["Use Kruskal-Wallis test (3+ independent groups).",
                          "Use one-way ANOVA (if outcome is continuous)."],
            ranked={"preferred": ["Kruskal-Wallis test"],
                    "acceptable": ["One-way ANOVA"],
                    "advanced": []},
            help_terms=["independent_groups"])
    return ALLOWED


def check_wilcoxon_eligibility(
    is_paired: bool = False,
    dep_type: str = "continuous",
) -> Dict[str, Any]:
    if not is_paired:
        return _block("Wilcoxon signed-rank test", "test",
            "Wilcoxon signed-rank requires paired/repeated 2-condition data.",
            "Independent structure detected, not paired.",
            properties=["independent_structure"],
            alternatives=["Use Mann-Whitney U test for independent groups.",
                          "Use independent-samples t-test (if continuous and normally distributed)."],
            ranked={"preferred": ["Mann-Whitney U test"],
                    "acceptable": ["Independent-samples t-test"],
                    "advanced": []},
            help_terms=["paired_data"])
    return ALLOWED


def check_kruskal_eligibility(
    n_groups: int,
    is_paired: bool = False,
) -> Dict[str, Any]:
    if is_paired:
        return _block("Kruskal-Wallis test", "test",
            "Kruskal-Wallis requires 3+ independent groups.",
            "Paired structure detected.",
            properties=["paired_structure"],
            alternatives=["Use Friedman test for repeated-measures data."],
            ranked={"preferred": ["Friedman test"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["independent_groups", "paired_data"])
    if n_groups < 3:
        return _block("Kruskal-Wallis test", "test",
            "This test compares 3+ independent groups.",
            f"Grouping variable has {_n_groups_str(n_groups)}.",
            properties=[f"n_groups={n_groups}"],
            alternatives=["If 2 groups: use Mann-Whitney U test.",
                          "If 2 groups and normally distributed: use independent t-test."],
            ranked={"preferred": ["Mann-Whitney U test (2 groups)"],
                    "acceptable": ["Independent t-test (2 groups)"],
                    "advanced": []},
            help_terms=["independent_groups"])
    return ALLOWED


def check_chi_square_eligibility(
    dep_type: str = "nominal",
    var_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if dep_type not in ("nominal", "binary_nominal", "ordinal", "binary"):
        return _block("Chi-square test", "test",
            "Chi-square requires categorical variables.",
            "The variable type appears to be continuous.",
            properties=[f"variable_type={dep_type}"],
            alternatives=["Use correlation or regression for continuous variables."],
            ranked={"preferred": ["Correlation or regression for continuous variables"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["categorical_variable"])
    return ALLOWED


def check_mcnemar_eligibility(
    is_paired: bool = False,
    dep_type: str = "binary",
) -> Dict[str, Any]:
    if dep_type not in ("binary", "binary_nominal"):
        return _block("McNemar's test", "test",
            "McNemar requires a binary outcome.",
            f"Outcome type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use paired t-test for continuous outcomes.",
                          "Use Wilcoxon signed-rank for ordinal outcomes."],
            ranked={"preferred": ["Paired t-test (continuous outcome)"],
                    "acceptable": ["Wilcoxon signed-rank (ordinal outcome)"],
                    "advanced": []},
            help_terms=["binary"])
    if not is_paired:
        return _block("McNemar's test", "test",
            "McNemar requires paired binary data.",
            "Independent structure detected.",
            properties=["independent_structure"],
            alternatives=["Use chi-square test for independent groups.",
                          "Use Fisher's exact test for small samples."],
            ranked={"preferred": ["Chi-square test"],
                    "acceptable": ["Fisher's exact test"],
                    "advanced": []},
            help_terms=["paired_data"])
    return ALLOWED


def check_regression_eligibility(
    dep_type: str = "continuous",
    is_survival: bool = False,
    is_time_to_event: bool = False,
) -> Dict[str, Any]:
    is_binary = dep_type in ("binary", "binary_nominal")
    if dep_type == "unknown":
        return ALLOWED
    if is_time_to_event:
        return _block("Linear regression", "test",
            "Linear regression is for continuous outcomes, not time-to-event data.",
            "Outcome appears to be time-to-event.",
            properties=["outcome_type=time_to_event"],
            alternatives=["Use Cox proportional hazards regression for time-to-event outcomes."],
            ranked={"preferred": ["Cox proportional hazards regression"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["time_to_event", "cox_regression"])
    if is_binary:
        return _block("Linear regression", "test",
            "Outcome is binary, not continuous.",
            f"Outcome type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use logistic regression for binary outcomes."],
            ranked={"preferred": ["Logistic regression"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["binary", "logistic_regression"])
    return ALLOWED


def check_logistic_eligibility(
    dep_type: str = "binary",
) -> Dict[str, Any]:
    if dep_type not in ("binary", "binary_nominal"):
        return _block("Logistic regression", "test",
            "Logistic regression requires a binary outcome.",
            f"Outcome type is '{dep_type}'.",
            properties=[f"outcome_type={dep_type}"],
            alternatives=["Use linear regression for continuous outcomes.",
                          "Use Cox regression for time-to-event outcomes."],
            ranked={"preferred": ["Linear regression (continuous outcome)"],
                    "acceptable": ["Cox regression (time-to-event outcome)"],
                    "advanced": []},
            help_terms=["binary", "logistic_regression"])
    return ALLOWED


def check_survival_eligibility(
    has_event: bool = False,
    has_time: bool = False,
) -> Dict[str, Any]:
    if not has_time:
        return _block("Survival analysis", "test",
            "A time-to-event variable is required for survival analysis.",
            "No time variable detected.",
            properties=["missing_time_variable"],
            alternatives=["Use standard regression or group comparison methods."],
            ranked={"preferred": ["Standard regression or group comparison methods"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["time_to_event", "censoring"])
    if not has_event:
        return _block("Survival analysis", "test",
            "An event indicator (0/1 or TRUE/FALSE) is required.",
            "No event indicator variable detected.",
            properties=["missing_event_indicator"],
            alternatives=["Add an event/censoring column, or use non-survival methods.",
                          "Use ordinary descriptive statistics or regression instead."],
            ranked={"preferred": ["Standard regression or group comparison methods"],
                    "acceptable": [],
                    "advanced": []},
            help_terms=["event_indicator", "censoring"])
    return ALLOWED


def check_correlation_eligibility(
    var_types: List[str],
    method: str = "pearson",
) -> Dict[str, Any]:
    non_numeric = [v for v in var_types if v not in ("continuous",)]
    if non_numeric:
        return _block(f"{method.capitalize()} correlation", "test",
            "Correlation requires numeric continuous variables.",
            f"Non-numeric types detected: {', '.join(non_numeric)}.",
            properties=[f"non_numeric_variables={','.join(non_numeric)}"],
            alternatives=["Use Spearman correlation for ordinal data.",
                          "Use chi-square test for categorical associations.",
                          "Use Cramér's V for categorical association strength."],
            ranked={"preferred": ["Spearman correlation"],
                    "acceptable": ["Cramér's V", "Chi-square test"],
                    "advanced": []},
            help_terms=["continuous", "correlation"])
    if method.lower() == "pearson":
        return ALLOWED
    return ALLOWED


def check_reliability_eligibility(n_items: int) -> Dict[str, Any]:
    if n_items < 2:
        return _block("Reliability analysis (Cronbach's alpha)", "test",
            "At least 2 items are required.",
            f"Selected {n_items} item(s).",
            properties=[f"n_items={n_items}"],
            alternatives=["Select 2+ items from the same scale or construct.",
                          "Use inter-item correlation for 2 items."],
            ranked={"preferred": ["Select 2+ items from the same scale or construct"],
                    "acceptable": ["Use inter-item correlation for 2 items"],
                    "advanced": []},
            help_terms=[])
    return ALLOWED


def check_factor_eligibility(n_vars: int) -> Dict[str, Any]:
    if n_vars < 3:
        return _block("Factor analysis", "test",
            "At least 3 variables are required.",
            f"Selected {n_vars} variable(s).",
            properties=[f"n_vars={n_vars}"],
            alternatives=["Select at least 3 related variables.",
                          "Use PCA on 2+ variables.",
                          "Use reliability analysis if measuring a single construct."],
            ranked={"preferred": ["Select at least 3 related variables"],
                    "acceptable": ["Use PCA on 2+ variables", "Use reliability analysis"],
                    "advanced": []},
            help_terms=[])
    return ALLOWED


# ── Chart eligibility ──────────────────────────────────────────────────

CHART_RULES: Dict[str, Dict[str, Any]] = {
    "bar": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "reason": "Bar charts are for categorical comparisons.",
        "alternatives": {"continuous": "Use histogram for distribution, or scatter/line for trends."},
        "help": [],
    },
    "histogram": {
        "x_types": ["continuous", "count"],
        "reason": "Histograms show distribution of numeric data.",
        "alternatives": {"nominal": "Use bar chart for categories.",
                         "binary_nominal": "Use bar chart.",
                         "ordinal": "Use ordered bar chart.",
                         "date": "Use time-series line chart."},
        "help": [],
    },
    "scatter": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "reason": "Scatter plots require two numeric variables.",
        "alternatives": {"nominal": "Use boxplot or bar chart for categorical comparisons.",
                         "binary_nominal": "Use grouped bar chart."},
        "help": [],
    },
    "boxplot": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Boxplots show numeric distribution across groups.",
        "alternatives": {"nominal_y": "Use bar chart of frequencies.",
                         "continuous_x": "Use scatter plot instead."},
        "help": [],
    },
    "line": {
        "x_types": ["continuous", "ordinal", "date"],
        "reason": "Line charts require an ordered x-axis.",
        "alternatives": {"nominal": "Use bar chart for unordered categories.",
                         "binary_nominal": "Use bar chart."},
        "help": [],
    },
    "pie": {
        "max_categories": 5,
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "reason": "Pie charts are for part-to-whole data with few categories.",
        "alternatives": {"nominal": "Use sorted bar chart for comparison.",
                         "too_many": "Use sorted bar chart — too many categories for a readable pie."},
        "help": [],
    },
    "km": {
        "requires_time": True,
        "requires_event": True,
        "reason": "KM curves require time-to-event data with event indicator.",
        "alternatives": {"no_time": "Use bar chart or histogram for non-survival data.",
                         "no_event": "Add an event indicator column."},
        "help": ["time_to_event", "event_indicator", "censoring"],
    },
    "stacked_bar": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "max_categories_x": 10,
        "reason": "Stacked bars are for composition within a few categories.",
        "alternatives": {"too_many": "Use faceted bar chart or separate bars.",
                          "continuous": "Use area chart for continuous x."},
        "help": [],
    },

    # ── Distribution plots ─────────────────────────────────────────────
    "violin": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Violin plots show distribution of a numeric variable across groups.",
        "alternatives": {"continuous_x": "Use histogram or density plot.",
                         "nominal_y": "Use bar chart of frequencies."},
        "help": [],
    },
    "strip": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Strip/beeswarm plots show individual data points across groups.",
        "alternatives": {"continuous_x": "Use scatter plot.",
                         "nominal_y": "Use bar chart."},
        "help": [],
    },
    "ecdf": {
        "x_types": ["continuous"],
        "reason": "ECDF plots show the cumulative distribution of a numeric variable.",
        "alternatives": {"nominal": "Use bar chart for categorical distributions.",
                         "ordinal": "Use ordered bar chart."},
        "help": [],
    },
    "qq": {
        "x_types": ["continuous"],
        "reason": "Q-Q plots compare a numeric variable's distribution to a theoretical one.",
        "alternatives": {"nominal": "Not applicable for categories.",
                         "ordinal": "Use ordered bar chart."},
        "help": ["normality"],
    },
    "hexbin": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "min_rows": 1000,
        "reason": "Hexbin plots show density of large datasets (1000+ points).",
        "alternatives": {"small_n": "Use scatter plot for smaller datasets.",
                         "nominal": "Use bar chart."},
        "help": [],
    },

    # ── Comparison plots ───────────────────────────────────────────────
    "pareto": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Pareto charts show sorted contributions — one categorical, one numeric.",
        "alternatives": {"continuous_x": "Use histogram.",
                         "nominal_y": "Use bar chart."},
        "help": [],
    },
    "cleveland_dot": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Cleveland dot plots show ranked comparisons — one categorical, one numeric.",
        "alternatives": {"continuous_x": "Use scatter plot.",
                         "nominal_y": "Use bar chart."},
        "help": [],
    },
    "lollipop": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Lollipop charts show ranked values — one categorical, one numeric.",
        "alternatives": {"continuous_x": "Use scatter plot.",
                         "nominal_y": "Use bar chart."},
        "help": [],
    },
    "dumbbell": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "requires_paired": True,
        "reason": "Dumbbell plots show change between two time points for each category.",
        "alternatives": {"no_paired": "Use bar chart or Cleveland dot plot for single time point.",
                         "continuous_x": "Use scatter plot.",
                         "nominal_y": "Use bar chart."},
        "help": ["paired_data"],
    },
    "splom": {
        "x_types": ["continuous"],
        "min_columns": 3,
        "reason": "Scatter matrix (SPLOM) requires 3+ numeric variables.",
        "alternatives": {"few_columns": "Use correlation matrix or pairwise scatter for fewer variables.",
                         "nominal": "Use boxplot or grouped bar chart."},
        "help": [],
    },

    # ── Time / process charts ──────────────────────────────────────────
    "control_chart": {
        "x_types": ["continuous", "date", "ordinal"],
        "y_types": ["continuous"],
        "min_rows": 10,
        "reason": "Control charts require time-ordered data with at least 10 points.",
        "alternatives": {"small_n": "Use run chart or simple line chart for fewer points.",
                         "nominal_y": "Not applicable."},
        "help": [],
    },
    "run_chart": {
        "x_types": ["continuous", "date", "ordinal"],
        "y_types": ["continuous"],
        "min_rows": 5,
        "reason": "Run charts show a sequence of measurements over time.",
        "alternatives": {"small_n": "Use a simple bar or line chart.",
                         "nominal_y": "Not applicable."},
        "help": [],
    },
    "gantt": {
        "x_types": ["date"],
        "y_types": ["nominal"],
        "reason": "Gantt charts require a date/time start and a categorical task column.",
        "alternatives": {"no_date": "Use bar chart for non-timeline data.",
                         "continuous_y": "Use time-series line chart."},
        "help": [],
    },
    "calendar_heatmap": {
        "x_types": ["date"],
        "y_types": ["continuous"],
        "reason": "Calendar heatmaps show numeric values across a date grid.",
        "alternatives": {"no_date": "Use bar chart or heatmap.",
                         "nominal_y": "Use count per date as numeric."},
        "help": [],
    },

    # ── Specialized charts ─────────────────────────────────────────────
    "parallel_coordinates": {
        "x_types": ["continuous"],
        "min_columns": 3,
        "reason": "Parallel coordinates require 3+ numeric variables to compare across categories.",
        "alternatives": {"few_columns": "Use correlation matrix for fewer variables.",
                         "nominal": "Use boxplot or grouped bar chart."},
        "help": [],
    },
    "radar": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "min_columns": 3,
        "reason": "Radar/spider charts show multi-attribute profiles with 3+ numeric measures.",
        "alternatives": {"few_columns": "Use bar chart for fewer measures.",
                         "continuous_x": "Use parallel coordinates or scatter matrix."},
        "help": [],
    },
    "treemap": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Treemaps show hierarchical proportions — categories sized by a numeric value.",
        "alternatives": {"continuous_x": "Use histogram.",
                         "nominal_y": "Not applicable."},
        "help": [],
    },
    "sankey": {
        "x_types": ["nominal", "binary_nominal"],
        "y_types": ["nominal", "binary_nominal"],
        "reason": "Sankey diagrams show flow between two categorical variables.",
        "alternatives": {"continuous": "Bin into categories or use correlation matrix.",
                         "ordinal": "Use ordered bar chart or heatmap."},
        "help": [],
    },
    "waterfall": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Waterfall charts show sequential contribution to a total.",
        "alternatives": {"continuous_x": "Use bar chart.",
                         "nominal_y": "Not applicable."},
        "help": [],
    },
    "funnel": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "min_rows": 5,
        "reason": "Funnel plots show effect size vs precision — requires 5+ data points.",
        "alternatives": {"small_n": "Use scatter plot for fewer points.",
                         "nominal": "Not applicable."},
        "help": [],
    },
    "bland_altman": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "reason": "Bland-Altman plots compare two measurements of the same variable.",
        "alternatives": {"nominal": "Not applicable for categories.",
                         "single_var": "Select two different columns measuring the same thing."},
        "help": [],
    },
    "forest": {
        "x_types": ["nominal", "binary_nominal", "ordinal"],
        "y_types": ["continuous"],
        "reason": "Forest plots show point estimates with confidence intervals.",
        "alternatives": {"continuous_x": "Use scatter plot.",
                         "nominal_y": "Not applicable."},
        "help": [],
    },
    "correlation_heatmap": {
        "x_types": ["continuous"],
        "min_columns": 2,
        "reason": "Correlation heatmap requires 2+ numeric variables.",
        "alternatives": {"few_columns": "Use scatter plot or correlation table for fewer variables.",
                         "nominal": "Use crosstab or bar chart."},
        "help": [],
    },
    "swimmer": {
        "x_types": ["continuous"],
        "y_types": ["nominal"],
        "reason": "Swimmer plots show individual patient timelines.",
        "alternatives": {"no_patient": "Use Gantt chart for non-patient timeline data."},
        "help": [],
    },
    "volcano": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "reason": "Volcano plots require effect size and p-value columns.",
        "alternatives": {"single_var": "Use histogram or scatter plot for single variable analysis."},
        "help": [],
    },
    "ridgeline": {
        "x_types": ["continuous"],
        "y_types": ["nominal"],
        "reason": "Ridgeline plots require one numeric and one grouping variable.",
        "alternatives": {"continuous_y": "Use violin plot for single group comparison.",
                         "nominal_x": "Use bar chart for categorical comparison."},
        "help": [],
    },
    "bubble": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "reason": "Bubble charts require X, Y, and size variables, all numeric.",
        "alternatives": {"few_columns": "Use scatter plot for 2 variables."},
        "help": [],
    },
    "calibration": {
        "x_types": ["continuous"],
        "y_types": ["continuous"],
        "reason": "Calibration plots require predicted and actual probability columns (0-1).",
        "alternatives": {"non_probability": "Use scatter plot for non-probability data."},
        "help": [],
    },
    "pca": {
        "x_types": ["continuous"],
        "min_columns": 2,
        "reason": "PCA requires 2+ numeric variables for dimensionality reduction.",
        "alternatives": {"few_columns": "Use scatter plot or correlation for fewer variables.",
                         "nominal": "Use bar chart for categorical data."},
        "help": [],
    },
    "correlation_network": {
        "x_types": ["continuous"],
        "min_columns": 3,
        "reason": "Correlation network requires 3+ numeric variables.",
        "alternatives": {"few_columns": "Use correlation heatmap for fewer variables."},
        "help": [],
    },
    "monthly_trend": {
        "x_types": ["date"],
        "y_types": ["continuous"],
        "reason": "Monthly trend heatmap requires a date column and a numeric value column.",
        "alternatives": {"no_date": "Use run chart or bar chart for non-date data.",
                         "nominal_y": "Use count aggregation to create numeric values."},
        "help": [],
    },
    "adverse_event_heatmap": {
        "x_types": ["nominal", "binary_nominal"],
        "y_types": ["nominal", "binary_nominal"],
        "reason": "AE heatmap requires patient and event columns.",
        "alternatives": {"continuous": "Bin into categories or use heatmap for numeric data."},
        "help": [],
    },
}


def check_chart_eligibility(
    chart_type: str,
    x_type: str = "continuous",
    y_type: str = "continuous",
    n_x_categories: int = 0,
    n_y_categories: int = 0,
    has_time: bool = False,
    has_event: bool = False,
    n_rows: int = 0,
    has_paired: bool = False,
) -> Dict[str, Any]:
    """Check if a chart type is appropriate for the given variable types."""
    rule = CHART_RULES.get(chart_type)
    if not rule:
        return ALLOWED

    # KM special case
    if chart_type == "km":
        if not has_time:
            return _block("Kaplan-Meier curve", "chart",
                rule["reason"],
                "No time-to-event variable detected.",
                properties=["missing_time_variable"],
                alternatives=[rule["alternatives"].get("no_time", "")],
                help_terms=rule["help"])
        if not has_event:
            return _block("Kaplan-Meier curve", "chart",
                rule["reason"],
                "No event indicator detected.",
                properties=["missing_event_indicator"],
                alternatives=[rule["alternatives"].get("no_event", "")],
                help_terms=rule["help"])
        return ALLOWED

    # Pie: check max categories
    if chart_type == "pie":
        max_cat = rule.get("max_categories", 5)
        if n_x_categories > max_cat:
            return _block("Pie chart", "chart",
                f"Pie charts are readable for at most {max_cat} categories.",
                f"Data has {n_x_categories} categories.",
                properties=[f"n_categories={n_x_categories}"],
                alternatives=[rule["alternatives"].get("too_many", "Use sorted bar chart.")],
                help_terms=rule["help"])
        if x_type not in rule.get("x_types", []):
            return _block("Pie chart", "chart",
                rule["reason"],
                f"Variable type is '{x_type}'.",
                properties=[f"x_type={x_type}"],
                alternatives=[rule["alternatives"].get(x_type, "Use a different chart type.")],
                help_terms=rule["help"])
        return ALLOWED

    # Stacked bar: check max categories on x
    if chart_type == "stacked_bar":
        max_cat = rule.get("max_categories_x", 10)
        if n_x_categories > max_cat:
            return _block("Stacked bar chart", "chart",
                f"Stacked bars are readable for at most {max_cat} categories.",
                f"Data has {n_x_categories} categories on the x-axis.",
                properties=[f"n_x_categories={n_x_categories}"],
                alternatives=[rule["alternatives"].get("too_many", "Use faceted bar chart.")],
                help_terms=rule["help"])
        if x_type not in rule.get("x_types", []):
            return _block("Stacked bar chart", "chart",
                rule["reason"],
                f"X-axis variable type is '{x_type}'.",
                properties=[f"x_type={x_type}"],
                alternatives=[rule["alternatives"].get(x_type, "Use a different chart type.")],
                help_terms=rule["help"])
        return ALLOWED

    # General x-type check
    allowed_x = rule.get("x_types", [])
    if x_type not in allowed_x:
        alt = rule["alternatives"].get(x_type, "Use a chart type appropriate for this data.")
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            rule["reason"],
            f"X-axis variable type is '{x_type}', which is not suitable for '{chart_type}'.",
            properties=[f"x_type={x_type}"],
            alternatives=[alt] if isinstance(alt, str) else alt,
            help_terms=rule["help"],
        )

    # Y-type check for 2D charts
    y_allowed = rule.get("y_types", [])
    if y_allowed and y_type not in y_allowed:
        alt = rule["alternatives"].get(f"{y_type}_y", "Use a chart type appropriate for this data.")
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            rule["reason"],
            f"Y-axis variable type is '{y_type}', which is not suitable.",
            properties=[f"y_type={y_type}"],
            alternatives=[alt] if isinstance(alt, str) else alt,
            help_terms=rule["help"],
        )

    # Min rows check
    min_rows = rule.get("min_rows", 0)
    if min_rows and n_rows > 0 and n_rows < min_rows:
        alt = rule["alternatives"].get("small_n", "Collect more data or use a simpler chart.")
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            rule["reason"],
            f"Need at least {min_rows} data points; dataset has {n_rows}.",
            properties=[f"n_rows={n_rows}", f"min_rows={min_rows}"],
            alternatives=[alt],
            help_terms=rule["help"],
        )

    # Min columns check
    min_cols = rule.get("min_columns", 0)
    if min_cols:
        n_selected = max(1 if x_type else 0, 1 if y_type else 0)
        if n_selected < min_cols:
            alt = rule["alternatives"].get("few_columns", f"Select at least {min_cols} variables.")
            return _block(
                f"{chart_type.capitalize()} chart", "chart",
                rule["reason"],
                f"Need at least {min_cols} variables; {n_selected} selected.",
                properties=[f"n_selected={n_selected}", f"min_columns={min_cols}"],
                alternatives=[alt],
                help_terms=rule["help"],
            )

    # Paired data check
    if rule.get("requires_paired") and not has_paired:
        alt = rule["alternatives"].get("no_paired", "Use a chart that does not require paired data.")
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            rule["reason"],
            "Data does not appear to be paired (no pre/post or before/after columns detected).",
            properties=["paired_structure=False"],
            alternatives=[alt],
            help_terms=rule["help"],
        )

    return ALLOWED


# ── ID column detection ─────────────────────────────────────────────────

def is_id_column(name: str) -> bool:
    """Detect ID columns by name pattern."""
    lower = name.lower()
    if lower.endswith('_id') or lower.startswith('id_') or lower == 'id':
        return True
    for kw in ('patient', 'record', 'subject', 'identifier'):
        if kw in lower:
            return True
    return False


# ── Extended descriptive eligibility ───────────────────────────────────

def check_descriptive_eligibility_extended(
    action: str,
    var_type: str,
    var_name: str,
    n_unique: int = 0,
    is_binary: bool = False,
    is_id: bool = False,
    is_date: bool = False,
    is_few_values: bool = False,
) -> Dict[str, Any]:
    """Enhanced check with ID, binary, date, and few-values guardrails.

    Blocks ID columns entirely for any descriptive summary.
    Blocks mean/SD for binary (0/1) variables.
    Blocks frequency table on continuous with few unique coded values.
    Blocks date variables from mean/SD.
    Blocks survival summaries on non-survival data.
    """
    # Block ID columns entirely for any descriptive summary
    if is_id:
        return _block(
            action=f"{action} of {var_name}",
            action_type="descriptive",
            reason="This appears to be an identifier column. Identifiers should not be summarized.",
            details=f"Column '{var_name}' was identified as an ID column.",
            properties=["is_id=True"],
            alternatives=["Remove ID columns before analysis."],
            help_terms=[],
        )

    # Block mean/SD for binary variables
    if is_binary and action in ('mean', 'sd'):
        return _block(
            action=f"{action} of {var_name}",
            action_type="descriptive",
            reason="Use proportions/percentages for binary variables.",
            details=f"Variable '{var_name}' is binary (0/1). '{action}' is not appropriate.",
            properties=[f"is_binary=True", f"requested_action={action}"],
            alternatives=["Use proportion (percentage) summary instead.",
                          "Use frequency table (counts)."],
            help_terms=["binary"],
        )

    # Block frequency table on continuous with few unique coded values
    if is_few_values and action == 'frequency':
        return _block(
            action=f"frequency of {var_name}",
            action_type="descriptive",
            reason="This variable appears to be numeric with few values. It may represent coded categories.",
            details=f"Variable '{var_name}' has {n_unique} unique numeric values.",
            properties=[f"n_unique={n_unique}", "is_few_values=True"],
            alternatives=["Use frequencies if categorical, or descriptive stats if truly continuous."],
            help_terms=[],
        )

    # Block date variables from mean/SD
    if is_date and action in ('mean', 'sd'):
        return _block(
            action=f"{action} of {var_name}",
            action_type="descriptive",
            reason="Use counts by period, earliest/latest date, or time trend plots.",
            details=f"Variable '{var_name}' is a date type. '{action}' is not meaningful for dates.",
            properties=[f"is_date=True", f"requested_action={action}"],
            alternatives=["Use counts by period.",
                          "Report earliest/latest date.",
                          "Use time trend plots."],
            help_terms=[],
        )

    # Block survival summaries on non-survival data
    if action == 'survival_summary' and var_type != 'time_to_event':
        return _block(
            action=f"survival summary of {var_name}",
            action_type="descriptive",
            reason="Survival summaries require time-to-event data with event indicator.",
            details=f"Variable '{var_name}' is type '{var_type}', not time-to-event.",
            properties=[f"var_type={var_type}"],
            alternatives=["Use ordinary descriptive statistics (mean, median, etc.)."],
            help_terms=["time_to_event", "survival"],
        )

    return ALLOWED


# ── Extended chart eligibility ─────────────────────────────────────────

def check_chart_eligibility_extended(
    chart_type: str,
    x_type: str = "continuous",
    y_type: str = "continuous",
    n_x_categories: int = 0,
    n_y_categories: int = 0,
    has_time: bool = False,
    has_event: bool = False,
    x_is_id: bool = False,
    y_is_id: bool = False,
    x_is_date: bool = False,
    y_is_date: bool = False,
    x_is_binary: bool = False,
    y_is_binary: bool = False,
    x_few_values: bool = False,
    y_few_values: bool = False,
) -> Dict[str, Any]:
    """Enhanced chart eligibility with ID, binary, date, and 3D guardrails.

    Blocks any chart where x or y is an ID column.
    Blocks scatter/line/histogram for binary variables.
    Blocks pie for date variables.
    Blocks line charts on date variables with very few time points (<3).
    Blocks scatter where both x and y are binary.
    Blocks 3D charts entirely.
    """
    # Block any chart where x or y is an ID column
    if x_is_id:
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            "X-axis appears to be an identifier column. Identifiers should not be plotted.",
            details="Identifier columns are not suitable for visualization.",
            properties=["x_is_id=True"],
            alternatives=["Select a meaningful variable for the x-axis.",
                          "Remove ID columns from chart configuration."],
            help_terms=[],
        )
    if y_is_id:
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            "Y-axis appears to be an identifier column. Identifiers should not be plotted.",
            details="Identifier columns are not suitable for visualization.",
            properties=["y_is_id=True"],
            alternatives=["Select a meaningful variable for the y-axis.",
                          "Remove ID columns from chart configuration."],
            help_terms=[],
        )

    # Block 3D charts entirely
    if chart_type.startswith('3d') or '3d' in chart_type.lower():
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            "3D charts are not supported. Use 2D alternatives.",
            details=f"Chart type '{chart_type}' is 3D, which is blocked.",
            properties=[f"chart_type={chart_type}"],
            alternatives=["Use 2D scatter plot with color/shape encoding.",
                          "Use faceted or small-multiple plots.",
                          "Use heatmap for 3D surface data."],
            help_terms=[],
        )

    # Block scatter/line/histogram for binary variables — suggest bar chart
    if chart_type in ('scatter', 'line', 'histogram') and (x_is_binary or y_is_binary):
        return _block(
            f"{chart_type.capitalize()} chart", "chart",
            f"{chart_type.capitalize()} charts are not appropriate for binary variables. Use a bar chart instead.",
            details=f"{'X-axis' if x_is_binary else 'Y-axis'} variable is binary.",
            properties=[f"x_is_binary={x_is_binary}", f"y_is_binary={y_is_binary}"],
            alternatives=["Use bar chart for binary data."],
            help_terms=["binary"],
        )

    # Block scatter where both x and y are binary
    if chart_type == 'scatter' and x_is_binary and y_is_binary:
        return _block(
            "Scatter chart", "chart",
            "Use a contingency table or grouped bar chart for two binary variables.",
            details="Both x and y variables are binary. A scatter plot is not informative.",
            properties=["x_is_binary=True", "y_is_binary=True"],
            alternatives=["Use a contingency table.",
                          "Use grouped bar chart."],
            help_terms=["binary"],
        )

    # Block pie for date variables
    if chart_type == 'pie' and (x_is_date or y_is_date):
        return _block(
            "Pie chart", "chart",
            "Pie charts are not suitable for date variables.",
            details=f"{'X-axis' if x_is_date else 'Y-axis'} variable is a date.",
            properties=[f"x_is_date={x_is_date}", f"y_is_date={y_is_date}"],
            alternatives=["Use time-series line chart or histogram by period."],
            help_terms=[],
        )

    # Block line charts on date variables with very few time points (<3)
    if chart_type == 'line' and x_is_date and n_x_categories < 3:
        return _block(
            "Line chart", "chart",
            "Too few time points for a meaningful trend.",
            details=f"Date variable has only {n_x_categories} unique time points.",
            properties=[f"n_time_points={n_x_categories}"],
            alternatives=["Use a bar chart instead.",
                          "Collect more time points."],
            help_terms=[],
        )

    return ALLOWED


# ── Data role inference ─────────────────────────────────────────────────

def infer_data_role(variable_meta: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Infer data roles from variable metadata.

    Args:
        variable_meta: List of dicts with keys {name, dtype, unique_count, is_numeric}.

    Returns:
        dict with keys: outcome_type, grouping_type, paired_structure, id_columns
    """
    outcome_type: Optional[str] = None
    grouping_type: Optional[str] = None
    paired_structure: bool = False
    id_columns: List[str] = []

    outcome_keywords = ['outcome', 'result', 'event', 'survival', 'dependent', 'response', 'target']
    grouping_patterns = ['group', 'treatment', 'arm', 'condition', 'cohort', 'phase']

    for var in variable_meta:
        name = var.get('name', '')
        lower = name.lower()
        dtype = var.get('dtype', '')
        unique_count = var.get('unique_count', 0)
        is_numeric = var.get('is_numeric', False)

        # Check for ID columns
        if is_id_column(name):
            id_columns.append(name)
            continue

        # Check for paired structure patterns
        for pair_kw in ['pre_', 'post_', '_pre', '_post', 'time1', 'time2', 'before', 'after', 'baseline', 'followup']:
            if pair_kw in lower:
                paired_structure = True
                break

        # Try to infer outcome
        if outcome_type is None:
            # Check name patterns for outcome
            if any(kw in lower for kw in outcome_keywords):
                outcome_type = name
            # Binary variables are likely outcomes
            elif unique_count == 2 and is_numeric:
                outcome_type = name
            # Time-to-event variables
            elif any(kw in lower for kw in ['survival', 'surv_time', 'time_to', 'death']):
                outcome_type = name

        # Try to infer grouping
        if grouping_type is None:
            if any(kw in lower for kw in grouping_patterns):
                grouping_type = name
            elif 2 <= unique_count <= 10 and not is_numeric:
                grouping_type = name

    return {
        'outcome_type': outcome_type or '',
        'grouping_type': grouping_type or '',
        'paired_structure': paired_structure,
        'id_columns': id_columns,
    }


# ── Help terms library ──────────────────────────────────────────────────

HELP_TERMS: Dict[str, str] = {
    "independent_groups": "Different participants in each group; no one appears in more than one group.",
    "paired_data": "The same participants measured twice, or observations linked in matched pairs.",
    "continuous": "A numeric variable that can take any value within a range (e.g., age, blood pressure).",
    "binary": "A variable with exactly 2 possible values (e.g., yes/no, 0/1).",
    "nominal": "Categories with no natural order (e.g., blood type, diagnosis).",
    "ordinal": "Categories with a natural order (e.g., mild/moderate/severe, Stage I/II/III).",
    "categorical_variable": "A variable that takes one of a limited set of values (e.g., diagnosis, treatment arm).",
    "time_to_event": "A variable recording how long until an event occurred (e.g., survival months).",
    "event_indicator": "A variable showing whether the event happened (1=yes, 0=no/censored).",
    "censoring": "Follow-up ended before the event occurred, so the exact event time is not known.",
    "mean": "The arithmetic average. Appropriate for symmetric continuous data.",
    "median": "The middle value. Appropriate for skewed data or ordinal variables.",
    "standard_deviation": "A measure of spread around the mean. Appropriate for symmetric continuous data.",
    "interquartile_range": "IQR: the range of the middle 50% of the data (Q3 - Q1).",
    "confidence_interval": "A range that plausibly contains the true population value.",
    "correlation": "A measure of association between two variables, ranging from -1 to +1.",
    "pearson": "Pearson correlation measures linear relationships. Spearman is recommended for non-linear monotonic relationships.",
    "logistic_regression": "Used when the outcome is binary (e.g., yes/no, alive/dead).",
    "cox_regression": "Used when the outcome is time-to-event with censoring.",
    "survival": "Analysis of time until a specific event occurs. Accounts for censored observations.",
    "normality": "Whether the data follows a bell-shaped (normal) distribution. Many parametric tests assume normality.",
    "proportional_hazards": "The assumption that the effect of predictors on the hazard is constant over time.",
    "fishers_exact": "An alternative to chi-square when expected counts in any cell are below 5.",
}


def get_help_text(term: str) -> str:
    """Return help text for a technical term, or empty string if unknown."""
    return HELP_TERMS.get(term, "")
