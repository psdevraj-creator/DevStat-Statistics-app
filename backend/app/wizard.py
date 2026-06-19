"""
DevStat — Deterministic Rule-Based Help Wizard (No LLM)

A three-component wizard that guides the user to the correct statistical
test through keyword matching + structured decision-tree traversal.

Classes
-------
IntentClassifier
    Maps free-text queries to an analysis family via regex rules.
DecisionTree
    Asks structured multiple-choice questions and narrows to a test.
WizardEngine
    Orchestrates the full conversation between the two components.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# IntentClassifier
# ═══════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """Classify free-text user input into an analysis family.

    Uses a list of (regex_pattern, analysis_family) tuples checked in order.
    The first match wins.  Entirely deterministic — no API calls, no ML.
    """

    # ── Analysis families exposed by the DevStat API ─────────────────
    ANALYSIS_FAMILIES = (
        "descriptives",
        "ttest",
        "nonparametric",
        "anova",
        "correlation",
        "regression",
        "survival",
        "diagnostic",
        "factor",
        "cluster",
        "power",
        "graph",
    )

    # ── Ordered rules: first match wins ─────────────────────────────
    INTENT_RULES: List[Tuple[str, str]] = [
        # --- survival ---
        (r"(?:survival|kaplan.meier|km\b|log.rank|cox|hazard|time.to.event|survive)", "survival"),
        # --- t-test ---
        (r"(?:t.test|ttest|student.s.t|one.sample.t|paired.t|independent.t)", "ttest"),
        # --- non-parametric ---
        (r"(?:non.param|nonparam|mann.whitney|wilcoxon|kruskal.wallis|friedman|sign.test|mcnemar)", "nonparametric"),
        # --- correlation ---
        (r"(?:correlation|pearson|spearman|kendall|associat|relationship. between|relate)", "correlation"),
        # --- regression ---
        (r"(?:regression|linear.regress|logistic.regress|predict|ols\b|glm\b|mixed.model|multilevel)", "regression"),
        # --- ANOVA ---
        (r"(?:anova|one.way|two.way|factorial|between.subject|within.subject|repeated.measure)", "anova"),
        # --- diagnostic ---
        (r"(?:diagnostic|sensitivity|specificity|roc\b|auc\b|gold.standard|test.accuracy)", "diagnostic"),
        # --- factor analysis ---
        (r"(?:factor.anal|efa\b|pca\b|principal.component|reliability|cronbach|latent)", "factor"),
        # --- cluster ---
        (r"(?:cluster|k.means|hierarchical|grouping|segmentation)", "cluster"),
        # --- power analysis ---
        (r"(?:power|sample.size|effect.size|statistical.power)", "power"),
        # --- descriptive ---
        (r"(?:descriptive|summary|mean.median|frequency|distribution|explore|summary.stat)", "descriptives"),
        # --- graph / chart ---
        (r"(?:graph|chart|plot\b|histogram|boxplot|scatter|bar.chart|pie.chart|visuali)", "graph"),
    ]

    def __init__(self) -> None:
        # Pre-compile patterns for speed
        self._compiled: List[Tuple[re.Pattern, str]] = [
            (re.compile(pat, re.IGNORECASE), family) for pat, family in self.INTENT_RULES
        ]

    # ── Public API ──────────────────────────────────────────────────

    def classify(self, text: str) -> Optional[str]:
        """Return the analysis family for *text*, or None if no rule matches.

        Normalisation applied before matching:
            - Lowercase
            - Strip leading/trailing whitespace
            - Collapse runs of punctuation into a single space
        """
        if not text or not isinstance(text, str):
            return None

        normalized = text.lower().strip()
        # Replace runs of non-alphanumeric characters with a single space
        normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        for pattern, family in self._compiled:
            if pattern.search(normalized):
                return family

        return None


# ═══════════════════════════════════════════════════════════════════════
# DecisionTree
# ═══════════════════════════════════════════════════════════════════════

class DecisionTree:
    """Deterministic decision tree for structured question navigation.

    The tree starts from the root question ``"what_analysis"`` and
    branches through nested dictionaries of ``question_id -> {...}``.
    Leaf nodes contain the final test recommendation with:
        - test_name
        - alternative   (fallback if assumptions fail)
        - graphs         (recommended visualisations)
        - assumptions    (list of checks to run)
        - module         (analysis router endpoint name)

    The tree is fully hard-coded — no database, no API, no LLM.
    """

    # ── Question definitions ────────────────────────────────────────

    QUESTIONS: Dict[str, Dict[str, Any]] = {
        # ═══════════════════════════════════════════════════════════
        # ROOT
        # ═══════════════════════════════════════════════════════════
        "what_analysis": {
            "id": "what_analysis",
            "text": "What type of analysis are you doing?",
            "type": "choice",
            "options": {
                "describe_data": "Describe / summarise my data",
                "compare_groups": "Compare groups or conditions",
                "relate_variables": "Relate two or more variables",
                "predict": "Predict an outcome from predictors",
                "survival": "Analyse time-to-event / survival data",
                "diagnose": "Evaluate a diagnostic test",
                "explore_structure": "Explore underlying structure (factor / cluster)",
                "power": "Calculate power or sample size",
                "graph": "Create a graph or chart",
                "not_sure": "I am not sure — help me choose",
            },
            "next": {
                "describe_data": "descriptives_done",
                "compare_groups": "compare_outcome_type",
                "relate_variables": "correlation_variables",
                "predict": "regression_outcome_type",
                "survival": "survival_groups",
                "diagnose": "diagnostic_done",
                "explore_structure": "structure_choice",
                "power": "power_done",
                "graph": "graph_done",
                "not_sure": "need_more_info",
            },
        },

        # ═══════════════════════════════════════════════════════════
        # NEED MORE INFO (root fallback)
        # ═══════════════════════════════════════════════════════════
        "need_more_info": {
            "id": "need_more_info",
            "text": "Let's narrow it down. What best describes your main goal?",
            "type": "choice",
            "options": {
                "summarise": "Get summary statistics or frequencies",
                "compare": "See if groups differ from each other",
                "relationship": "Find relationships between variables",
                "forecast": "Predict one variable from others",
                "time_event": "Analyse time until an event (survival)",
                "test_accuracy": "Test how well a test detects a condition",
            },
            "next": {
                "summarise": "descriptives_done",
                "compare": "compare_outcome_type",
                "relationship": "correlation_variables",
                "forecast": "regression_outcome_type",
                "time_event": "survival_groups",
                "test_accuracy": "diagnostic_done",
            },
        },

        # ═══════════════════════════════════════════════════════════
        # COMPARE GROUPS TREE
        # ═══════════════════════════════════════════════════════════
        "compare_outcome_type": {
            "id": "compare_outcome_type",
            "text": "What type of outcome variable are you comparing?",
            "type": "choice",
            "options": {
                "continuous": "Continuous (e.g. age, height, score)",
                "binary": "Binary / dichotomous (e.g. yes/no, 0/1)",
                "categorical": "Categorical / nominal (e.g. blood type)",
                "time_to_event": "Time-to-event (survival data)",
            },
            "next": {
                "continuous": "compare_num_groups",
                "binary": "compare_binary",
                "categorical": "compare_categorical",
                "time_to_event": "survival_groups",
            },
        },

        "compare_num_groups": {
            "id": "compare_num_groups",
            "text": "How many groups are you comparing?",
            "type": "choice",
            "options": {
                "one": "One group (compare to a known value)",
                "two": "Two groups",
                "three_plus": "Three or more groups",
            },
            "next": {
                "one": "compare_one_sample",
                "two": "compare_independent_paired",
                "three_plus": "compare_anova_leaf",
            },
        },

        "compare_one_sample": {
            "id": "compare_one_sample",
            "text": "Do you know the population mean (mu) to compare against?",
            "type": "choice",
            "options": {
                "yes": "Yes, I have a known value",
                "no": "No, skip",
            },
            "next": {
                "yes": "compare_onesample_t_leaf",
                "no": "compare_onesample_t_leaf",
            },
        },

        "compare_independent_paired": {
            "id": "compare_independent_paired",
            "text": "Are the two groups independent or paired?",
            "type": "choice",
            "options": {
                "independent": "Independent (different subjects in each group)",
                "paired": "Paired (same subjects, before/after, matched)",
            },
            "next": {
                "independent": "compare_independent_t_leaf",
                "paired": "compare_paired_t_leaf",
            },
        },

        # --- Comparison leaf nodes ---

        "compare_onesample_t_leaf": {
            "id": "compare_onesample_t_leaf",
            "result": {
                "test_name": "One-sample t-test",
                "alternative": "Wilcoxon signed-rank test",
                "graphs": ["Histogram", "Q-Q plot", "Box plot"],
                "assumptions": [
                    "Normality (Shapiro-Wilk test)",
                    "Independence of observations",
                ],
                "module": "/api/analysis/ttest",
                "prefill_params": {"test_type": "one_sample"},
            },
        },

        "compare_independent_t_leaf": {
            "id": "compare_independent_t_leaf",
            "result": {
                "test_name": "Independent samples t-test",
                "alternative": "Mann-Whitney U test",
                "graphs": ["Grouped box plot", "Histogram (by group)", "Q-Q plot"],
                "assumptions": [
                    "Normality (Shapiro-Wilk test)",
                    "Equality of variances (Levene's test)",
                    "Independence of observations",
                ],
                "module": "/api/analysis/ttest",
                "prefill_params": {"test_type": "independent"},
            },
        },

        "compare_paired_t_leaf": {
            "id": "compare_paired_t_leaf",
            "result": {
                "test_name": "Paired t-test",
                "alternative": "Wilcoxon signed-rank test",
                "graphs": ["Paired scatter plot", "Difference histogram", "Q-Q plot"],
                "assumptions": [
                    "Normality of differences (Shapiro-Wilk test)",
                    "Paired observations (dependency accounted for)",
                ],
                "module": "/api/analysis/ttest",
                "prefill_params": {"test_type": "paired"},
            },
        },

        "compare_anova_leaf": {
            "id": "compare_anova_leaf",
            "result": {
                "test_name": "One-way ANOVA",
                "alternative": "Kruskal-Wallis test",
                "graphs": ["Grouped box plot", "Mean plot with error bars", "Q-Q plot"],
                "assumptions": [
                    "Normality within each group (Shapiro-Wilk test)",
                    "Equality of variances (Levene's test)",
                    "Independence of observations",
                ],
                "module": "/api/analysis/anova",
                "prefill_params": {"test_type": "anova"},
            },
        },

        "compare_binary": {
            "id": "compare_binary",
            "result": {
                "test_name": "Chi-square test of independence",
                "alternative": "Fisher's exact test",
                "graphs": ["Grouped bar chart", "Clustered bar chart", "Mosaic plot"],
                "assumptions": [
                    "Expected frequency ≥ 5 in each cell",
                    "Independence of observations",
                    "Categorical variables (nominal)",
                ],
                "module": "/api/analysis/chisquare",
                "prefill_params": {},
            },
        },

        "compare_categorical": {
            "id": "compare_categorical",
            "result": {
                "test_name": "Chi-square test of independence",
                "alternative": "Fisher's exact test",
                "graphs": ["Grouped bar chart", "Mosaic plot"],
                "assumptions": [
                    "Expected frequency ≥ 5 in each cell",
                    "Independence of observations",
                ],
                "module": "/api/analysis/chisquare",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # CORRELATION TREE
        # ═══════════════════════════════════════════════════════════
        "correlation_variables": {
            "id": "correlation_variables",
            "text": "How many variables are you correlating?",
            "type": "choice",
            "options": {
                "two": "Just two variables",
                "many": "Many variables (correlation matrix)",
            },
            "next": {
                "two": "correlation_adjust",
                "many": "correlation_matrix_leaf",
            },
        },

        "correlation_adjust": {
            "id": "correlation_adjust",
            "text": "Do you need to control / adjust for other variables?",
            "type": "choice",
            "options": {
                "yes": "Yes, control for covariates (partial correlation)",
                "no": "No, simple correlation",
            },
            "next": {
                "yes": "correlation_partial_leaf",
                "no": "correlation_simple_leaf",
            },
        },

        "correlation_simple_leaf": {
            "id": "correlation_simple_leaf",
            "result": {
                "test_name": "Pearson / Spearman correlation",
                "alternative": "Spearman rank correlation (if assumptions violated)",
                "graphs": ["Scatter plot", "Scatter with trend line", "Pair plot"],
                "assumptions": [
                    "Linearity (for Pearson)",
                    "Normality (for Pearson)",
                    "No significant outliers",
                ],
                "module": "/api/analysis/correlation",
                "prefill_params": {},
            },
        },

        "correlation_matrix_leaf": {
            "id": "correlation_matrix_leaf",
            "result": {
                "test_name": "Correlation matrix + heatmap",
                "alternative": "Spearman rank correlation matrix",
                "graphs": ["Correlation heatmap", "Correlation matrix table"],
                "assumptions": [
                    "Pairwise linearity (for Pearson)",
                    "Sufficient sample size per pair",
                ],
                "module": "/api/analysis/correlation",
                "prefill_params": {},
            },
        },

        "correlation_partial_leaf": {
            "id": "correlation_partial_leaf",
            "result": {
                "test_name": "Partial correlation",
                "alternative": "Spearman partial correlation",
                "graphs": ["Partial correlation plot", "Scatter of residuals"],
                "assumptions": [
                    "Linearity of relationships",
                    "Normality of residuals",
                    "No multicollinearity among covariates",
                ],
                "module": "/api/analysis/partial-correlation",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # REGRESSION TREE
        # ═══════════════════════════════════════════════════════════
        "regression_outcome_type": {
            "id": "regression_outcome_type",
            "text": "What type is your outcome (dependent) variable?",
            "type": "choice",
            "options": {
                "continuous": "Continuous (e.g. income, test score)",
                "binary": "Binary / dichotomous (e.g. pass/fail, sick/healthy)",
                "count": "Count (e.g. number of visits, accidents)",
                "time_to_event": "Time-to-event (survival data)",
            },
            "next": {
                "continuous": "regression_covariates_continuous",
                "binary": "regression_covariates_binary",
                "count": "regression_covariates_continuous",
                "time_to_event": "survival_covariates",
            },
        },

        "regression_covariates_continuous": {
            "id": "regression_covariates_continuous",
            "text": "Do you have multiple predictor (independent) variables?",
            "type": "choice",
            "options": {
                "yes": "Yes, multiple predictors",
                "no": "No, just one predictor",
            },
            "next": {
                "yes": "regression_mixed",
                "no": "regression_mixed",
            },
        },

        "regression_covariates_binary": {
            "id": "regression_covariates_binary",
            "text": "Do you have multiple predictor (independent) variables?",
            "type": "choice",
            "options": {
                "yes": "Yes, multiple predictors",
                "no": "No, just one predictor",
            },
            "next": {
                "yes": "regression_mixed",
                "no": "regression_mixed",
            },
        },

        "regression_mixed": {
            "id": "regression_mixed",
            "text": "Do you have random / grouping effects (e.g. repeated measures, subjects)?",
            "type": "choice",
            "options": {
                "yes": "Yes, there are random effects (mixed model)",
                "no": "No, fixed effects only",
            },
            "next": {
                "yes": "regression_mixed_leaf",
                "no": "regression_no_mixed",
            },
        },

        "regression_no_mixed": {
            "id": "regression_no_mixed",
            "text": "Which regression type based on outcome? (confirmation)",
            "type": "choice",
            "options": {
                "continuous": "Linear regression",
                "binary": "Logistic regression",
                "count": "Poisson / negative binomial regression",
                "time_to_event": "Cox regression",
            },
            "next": {
                "continuous": "regression_linear_leaf",
                "binary": "regression_logistic_leaf",
                "count": "regression_linear_leaf",
                "time_to_event": "regression_cox_leaf",
            },
        },

        "regression_linear_leaf": {
            "id": "regression_linear_leaf",
            "result": {
                "test_name": "Linear regression",
                "alternative": "Robust regression or quantile regression",
                "graphs": ["Scatter plot with regression line", "Residuals vs fitted", "Q-Q plot of residuals"],
                "assumptions": [
                    "Linearity",
                    "Normality of residuals",
                    "Homoscedasticity (constant variance)",
                    "Independence of observations",
                    "No multicollinearity (if multiple predictors)",
                ],
                "module": "/api/analysis/linear-regression",
                "prefill_params": {"family": "linear"},
            },
        },

        "regression_logistic_leaf": {
            "id": "regression_logistic_leaf",
            "result": {
                "test_name": "Logistic regression",
                "alternative": "Probit regression or exact logistic regression",
                "graphs": ["ROC curve", "Predicted probability plot", "Dot plot of coefficients"],
                "assumptions": [
                    "Binary outcome",
                    "Independence of observations",
                    "No severe multicollinearity",
                    "Linearity of logit (for continuous predictors)",
                ],
                "module": "/api/analysis/logistic-regression",
                "prefill_params": {"family": "logistic"},
            },
        },

        "regression_cox_leaf": {
            "id": "regression_cox_leaf",
            "result": {
                "test_name": "Cox proportional hazards regression",
                "alternative": "Parametric survival regression (Weibull, etc.)",
                "graphs": ["Forest plot", "Predicted survival curves", "Schoenfeld residuals plot"],
                "assumptions": [
                    "Proportional hazards",
                    "No influential outliers",
                    "Linearity of continuous covariates",
                ],
                "module": "/api/analysis/cox-regression",
                "prefill_params": {},
            },
        },

        "regression_mixed_leaf": {
            "id": "regression_mixed_leaf",
            "result": {
                "test_name": "Mixed model (lme4)",
                "alternative": "Generalized Estimating Equations (GEE)",
                "graphs": ["Spaghetti plot", "Residual vs fitted", "Random effects caterpillar plot"],
                "assumptions": [
                    "Normality of residuals",
                    "Homoscedasticity",
                    "Correct random effect structure",
                    "Linearity of fixed effects",
                ],
                "module": "/api/analysis/mixed-model",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # SURVIVAL TREE
        # ═══════════════════════════════════════════════════════════
        "survival_groups": {
            "id": "survival_groups",
            "text": "How many groups do you want to compare?",
            "type": "choice",
            "options": {
                "one": "One group (overall survival curve)",
                "two_plus": "Two or more groups",
            },
            "next": {
                "one": "survival_one_group_leaf",
                "two_plus": "survival_covariates",
            },
        },

        "survival_covariates": {
            "id": "survival_covariates",
            "text": "Do you have covariates to adjust for?",
            "type": "choice",
            "options": {
                "yes": "Yes (Cox regression)",
                "no": "No (Kaplan-Meier + log-rank only)",
            },
            "next": {
                "yes": "survival_cox_leaf",
                "no": "survival_km_logrank_leaf",
            },
        },

        "survival_one_group_leaf": {
            "id": "survival_one_group_leaf",
            "result": {
                "test_name": "Kaplan-Meier + median survival",
                "alternative": "Parametric survival curve (Weibull)",
                "graphs": ["Kaplan-Meier curve", "Cumulative hazard plot", "Survival table"],
                "assumptions": [
                    "Non-informative censoring",
                    "Appropriate time scale",
                    "Sufficient follow-up",
                ],
                "module": "/api/analysis/kaplan-meier",
                "prefill_params": {},
            },
        },

        "survival_km_logrank_leaf": {
            "id": "survival_km_logrank_leaf",
            "result": {
                "test_name": "Kaplan-Meier + log-rank test",
                "alternative": "Gehan-Breslow test or Cox regression",
                "graphs": ["Kaplan-Meier curves by group", "Cumulative hazard by group", "Risk table"],
                "assumptions": [
                    "Non-informative censoring",
                    "Proportional hazards (for log-rank)",
                    "Sufficient events per group",
                ],
                "module": "/api/analysis/kaplan-meier",
                "prefill_params": {},
            },
        },

        "survival_cox_leaf": {
            "id": "survival_cox_leaf",
            "result": {
                "test_name": "Cox proportional hazards regression",
                "alternative": "Parametric survival regression (Weibull, log-normal)",
                "graphs": ["Forest plot", "Adjusted survival curves", "Schoenfeld residuals"],
                "assumptions": [
                    "Proportional hazards",
                    "Non-informative censoring",
                    "Linearity of continuous covariates",
                    "No influential outliers",
                ],
                "module": "/api/analysis/cox-regression",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # DIAGNOSTIC TREE
        # ═══════════════════════════════════════════════════════════
        "diagnostic_done": {
            "id": "diagnostic_done",
            "result": {
                "test_name": "Diagnostic test evaluation (2×2 table)",
                "alternative": "ROC curve analysis",
                "graphs": ["ROC curve", "Sensitivity / specificity plot", "Confusion matrix heatmap"],
                "assumptions": [
                    "Gold standard reference available",
                    "Binary test and reference",
                    "Independent sample",
                ],
                "module": "/api/analysis/diagnostic",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # STRUCTURE (FACTOR / CLUSTER) TREE
        # ═══════════════════════════════════════════════════════════
        "structure_choice": {
            "id": "structure_choice",
            "text": "What best describes your goal?",
            "type": "choice",
            "options": {
                "reduce": "Reduce many variables to fewer latent factors (factor analysis)",
                "group_cases": "Group similar cases / observations (cluster analysis)",
                "reliability": "Assess internal consistency (Cronbach's alpha)",
            },
            "next": {
                "reduce": "factor_done",
                "group_cases": "cluster_done",
                "reliability": "reliability_done",
            },
        },

        "factor_done": {
            "id": "factor_done",
            "result": {
                "test_name": "Exploratory factor analysis",
                "alternative": "Principal Component Analysis (PCA)",
                "graphs": ["Scree plot", "Factor loading heatmap", "Variance explained bar chart"],
                "assumptions": [
                    "Adequate sample size (N ≥ 5 × items)",
                    "Correlations among items (Bartlett's test of sphericity)",
                    "Sampling adequacy (KMO ≥ 0.6)",
                ],
                "module": "/api/analysis/factor",
                "prefill_params": {},
            },
        },

        "cluster_done": {
            "id": "cluster_done",
            "result": {
                "test_name": "Cluster analysis",
                "alternative": "Hierarchical clustering (if k-means unsuitable)",
                "graphs": ["Dendrogram", "Cluster scatter plot", "Elbow plot"],
                "assumptions": [
                    "Numeric variables scaled/standardised",
                    "No severe outliers (influential on centroids)",
                ],
                "module": "/api/analysis/cluster",
                "prefill_params": {},
            },
        },

        "reliability_done": {
            "id": "reliability_done",
            "result": {
                "test_name": "Reliability analysis (Cronbach's alpha)",
                "alternative": "McDonald's omega or split-half reliability",
                "graphs": ["Item-total correlation plot", "Alpha-if-deleted bar chart"],
                "assumptions": [
                    "Continuous or ordinal items (Likert-type)",
                    "Unidimensional scale expected",
                    "Sufficient sample size",
                ],
                "module": "/api/analysis/reliability",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # DESCRIPTIVES LEAF (shortcut)
        # ═══════════════════════════════════════════════════════════
        "descriptives_done": {
            "id": "descriptives_done",
            "result": {
                "test_name": "Descriptive statistics and frequencies",
                "alternative": "Explore (normality diagnostics) if needed",
                "graphs": ["Histogram", "Box plot", "Bar chart (frequencies)"],
                "assumptions": [
                    "Data type appropriate for each statistic",
                    "No extreme outliers (for mean-based stats)",
                ],
                "module": "/api/analysis/descriptive",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # POWER ANALYSIS LEAF
        # ═══════════════════════════════════════════════════════════
        "power_done": {
            "id": "power_done",
            "result": {
                "test_name": "Power / sample-size analysis",
                "alternative": "Simulation-based power (for complex designs)",
                "graphs": ["Power curve (power vs sample size)", "Effect size vs power"],
                "assumptions": [
                    "Effect size estimate (from prior work or pilot)",
                    "Significance level (α, typically 0.05)",
                    "Desired power (typically 0.80)",
                ],
                "module": "/api/analysis/power",
                "prefill_params": {},
            },
        },

        # ═══════════════════════════════════════════════════════════
        # GRAPH LEAF
        # ═══════════════════════════════════════════════════════════
        "graph_done": {
            "id": "graph_done",
            "result": {
                "test_name": "Graph / chart creation",
                "alternative": "Explore the data first (descriptive stats)",
                "graphs": [
                    "Histogram (distribution)",
                    "Box plot (outliers & spread)",
                    "Scatter plot (relationship)",
                    "Bar chart (frequencies)",
                    "Line chart (trends)",
                ],
                "assumptions": [],
                "module": "/api/analysis/explore",
                "prefill_params": {},
            },
        },
    }

    # ── Tree navigation ────────────────────────────────────────────

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Look up a question definition by ID.  Returns None if unknown."""
        return self.QUESTIONS.get(question_id)

    def get_next_question(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Given the current wizard *state*, return the next step.

        *state* must have the shape::

            {
                "current_node": <str>,
                "answers": {<question_id>: <answer_key>, ...},
            }

        Returns either a *question* dict (more choices needed) or a
        *result* dict (leaf node reached with full recommendation).
        """
        current_node = state.get("current_node", "what_analysis")

        # If we have an answer for the current node, follow the branch
        answers = state.get("answers", {})
        if current_node in answers:
            chosen = answers[current_node]
            node_def = self.get_question(current_node)
            if node_def is None:
                return {"error": f"Unknown node: {current_node}"}

            # Follow the 'next' mapping
            next_map = node_def.get("next", {})
            next_node = next_map.get(chosen)
            if next_node is None:
                return {"error": f"No branch for answer '{chosen}' from '{current_node}'"}
            return self._resolve(next_node)

        # No answer yet — return the question for the current node
        node_def = self.get_question(current_node)
        if node_def is None:
            return {"error": f"Unknown node: {current_node}"}

        # If the node is a leaf (has a 'result'), return it directly
        if "result" in node_def:
            return self._format_result(node_def["result"])

        return {
            "question": node_def["id"],
            "text": node_def["text"],
            "type": node_def["type"],
            "options": node_def.get("options", {}),
            "next_node": current_node,
        }

    # ── Internal helpers ───────────────────────────────────────────

    def _resolve(self, node_id: str) -> Dict[str, Any]:
        """Return question or result dict for *node_id*."""
        node_def = self.get_question(node_id)
        if node_def is None:
            return {"error": f"Unknown node: {node_id}"}

        if "result" in node_def:
            return self._format_result(node_def["result"])

        return {
            "question": node_def["id"],
            "text": node_def["text"],
            "type": node_def["type"],
            "options": node_def.get("options", {}),
            "next_node": node_id,
        }

    @staticmethod
    def _format_result(result_node: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a leaf result into the standard response shape."""
        return {
            "result": True,
            "test_name": result_node["test_name"],
            "alternative": result_node.get("alternative", ""),
            "graphs": result_node.get("graphs", []),
            "assumptions": result_node.get("assumptions", []),
            "module": result_node.get("module", ""),
            "prefill_params": result_node.get("prefill_params", {}),
            "explanation": _build_explanation(result_node),
        }

    def get_recommendation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Return the full recommendation from a completed wizard state.

        This expects *state* to have reached a leaf node.  Returns the
        same shape as the leaf result, plus a *prefill_params* dict
        suitable for sending to the analysis endpoint.
        """
        answers = state.get("answers", {})
        current_node = state.get("current_node", "what_analysis")

        # Walk the answers to find the leaf
        node_def = self.get_question(current_node)
        if node_def is None:
            return {"error": f"Unknown starting node: {current_node}"}

        while "result" not in node_def:
            if current_node not in answers:
                return {"error": f"Missing answer for question '{current_node}'"}
            chosen = answers[current_node]
            next_map = node_def.get("next", {})
            next_node = next_map.get(chosen)
            if next_node is None:
                return {"error": f"No branch for answer '{chosen}' from '{current_node}'"}
            current_node = next_node
            node_def = self.get_question(current_node)
            if node_def is None:
                return {"error": f"Unknown node: {current_node}"}

        result: Dict[str, Any] = {
            "test_name": node_def["result"]["test_name"],
            "alternative": node_def["result"].get("alternative", ""),
            "graphs": list(node_def["result"].get("graphs", [])),
            "assumptions": list(node_def["result"].get("assumptions", [])),
            "module": node_def["result"].get("module", ""),
            "explanation": _build_explanation(node_def["result"]),
            "prefill_params": dict(node_def["result"].get("prefill_params", {})),
        }
        return result


# ═══════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════

def _build_explanation(result: Dict[str, Any]) -> str:
    """Generate a plain-English explanation for the recommended test."""
    test_name = result.get("test_name", "Statistical test")
    alt = result.get("alternative", "")
    graphs = result.get("graphs", [])

    parts: List[str] = [f"**Recommended: {test_name}**"]
    if alt:
        parts.append(f"If assumptions are violated, consider **{alt}** instead.")

    if graphs:
        glist = ", ".join(graphs)
        parts.append(f"Suggested visualisations: {glist}.")

    assumptions = result.get("assumptions", [])
    if assumptions:
        parts.append("Key assumptions to check:")
        for a in assumptions:
            parts.append(f"  • {a}")

    parts.append(
        "Use the analysis form to configure your variables and run the test."
    )
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# WizardEngine
# ═══════════════════════════════════════════════════════════════════════

class WizardEngine:
    """Orchestrator between IntentClassifier and DecisionTree.

    On the first call, *process_input* runs the intent classifier to
    suggest a starting tree path.  On subsequent calls, it uses the
    decision tree for structured navigation.

    Usage::

        engine = WizardEngine()
        state = {"current_node": "what_analysis", "answers": {}}

        # First interaction
        result = engine.process_input("I want to compare two groups")
        state = result["state"]

        # Subsequent interactions
        result = engine.process_input("paired", state)
        state = result["state"]
    """

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.decision_tree = DecisionTree()

    def process_input(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process *user_input* and return the next step.

        Parameters
        ----------
        user_input: str
            Free text, or a structured answer key.
        state: dict
            Current wizard state (``current_node`` + ``answers``).

        Returns
        -------
        dict
            ``{response, state, recommendation}`` where *response* is
            the next question or final result, and *recommendation* is
            the full recommendation dict if the tree reached a leaf.
        """
        # ── Normalise state ────────────────────────────────────────
        current_node = state.get("current_node", "what_analysis")
        answers: Dict[str, str] = dict(state.get("answers", {}))

        # ── On the very first call, try intent classification ──────
        is_first_call = (current_node == "what_analysis" and not answers)
        if is_first_call:
            family = self.intent_classifier.classify(user_input)
            if family is not None:
                # Map the detected family to a starting answer
                mapped = self._map_family_to_answer(family)
                if mapped is not None:
                    answers["what_analysis"] = mapped
                    # Resolve to next node
                    root_def = self.decision_tree.get_question("what_analysis")
                    if root_def and "next" in root_def:
                        next_map = root_def["next"]
                        current_node = next_map.get(mapped, current_node)

        # If classification didn't produce a match, treat input as
        # an answer for the *current* question.
        if not is_first_call or "what_analysis" not in answers:
            node_def = self.decision_tree.get_question(current_node)
            if node_def and node_def.get("type") == "choice":
                # Try to match user_input to an option key or label
                matched_key = self._match_option(
                    user_input, node_def.get("options", {})
                )
                if matched_key is not None:
                    answers[current_node] = matched_key
                elif is_first_call:
                    # No match & first call — return the root question
                    root_q = self.decision_tree.get_next_question(
                        {"current_node": "what_analysis", "answers": {}}
                    )
                    new_state = {"current_node": "what_analysis", "answers": {}}
                    return {
                        "response": root_q,
                        "state": new_state,
                        "recommendation": None,
                    }

        # ── Advance the tree ───────────────────────────────────────
        next_state = {"current_node": current_node, "answers": answers}
        response = self.decision_tree.get_next_question(next_state)

        # Update state with the new current_node (if advanced)
        if "next_node" in response:
            current_node = response["next_node"]
        if "result" in response and response.get("result") is True:
            # Leaf reached — store final recommendation
            full_rec = self.decision_tree.get_recommendation(
                {"current_node": current_node, "answers": answers}
            )
            new_state = {"current_node": current_node, "answers": answers, "done": True}
            return {
                "response": response,
                "state": new_state,
                "recommendation": full_rec,
            }

        new_state = {"current_node": current_node, "answers": answers}
        return {
            "response": response,
            "state": new_state,
            "recommendation": None,
        }

    # ── Internal helpers ───────────────────────────────────────────

    @staticmethod
    def _map_family_to_answer(family: str) -> Optional[str]:
        """Map a detected analysis family to a root question answer key."""
        mapping: Dict[str, str] = {
            "descriptives": "describe_data",
            "ttest": "compare_groups",
            "nonparametric": "compare_groups",
            "anova": "compare_groups",
            "correlation": "relate_variables",
            "regression": "predict",
            "survival": "survival",
            "diagnostic": "diagnose",
            "factor": "explore_structure",
            "cluster": "explore_structure",
            "power": "power",
            "graph": "graph",
        }
        return mapping.get(family)

    @staticmethod
    def _match_option(user_input: str, options: Dict[str, str]) -> Optional[str]:
        """Try to match *user_input* against option keys or labels."""
        if not user_input or not options:
            return None

        norm_input = user_input.strip().lower()

        # Exact match on key
        if norm_input in options:
            return norm_input

        # Exact match on label
        label_map = {v.lower(): k for k, v in options.items()}
        if norm_input in label_map:
            return label_map[norm_input]

        # Partial match on label
        for label_lower, key in label_map.items():
            if norm_input in label_lower or label_lower in norm_input:
                return key

        # Partial match on key
        for key in options:
            if norm_input in key or key in norm_input:
                return key

        return None

    def get_recommendation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Return the full recommendation from a completed wizard state.

        Delegates to DecisionTree.get_recommendation.
        """
        return self.decision_tree.get_recommendation(state)
