"""
Group comparison service for DevStat.

Provides functions for t-tests, Mann-Whitney U, Wilcoxon signed-rank,
one-way ANOVA, Kruskal-Wallis, and chi-square tests, each returning a
structured dict with test statistics, effect sizes, and interpretation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from app.services import error


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _cohens_d(series_a: pd.Series, series_b: pd.Series) -> float:
    """Cohen's *d* for independent groups (pooled standard deviation)."""
    n1, n2 = len(series_a), len(series_b)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1 = series_a.var(ddof=1)
    s2 = series_b.var(ddof=1)
    pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return float((series_a.mean() - series_b.mean()) / pooled)


def _cohens_dz(pre: pd.Series, post: pd.Series) -> float:
    """Cohen's *d\\ :sub:`z`* for paired designs (standardised mean difference)."""
    diff = pre - post
    n = len(diff.dropna())
    if n < 2:
        return 0.0
    std_diff = diff.std(ddof=1)
    if std_diff == 0:
        return 0.0
    return float(diff.mean() / std_diff)


def _rank_biserial(series_a: pd.Series, series_b: pd.Series) -> float:
    """Rank-biserial correlation for Mann-Whitney U.

    Formula: r = 1 - (2 * U) / (n1 * n2)
    """
    n1, n2 = len(series_a), len(series_b)
    if n1 == 0 or n2 == 0:
        return 0.0
    u_stat, _ = sp_stats.mannwhitneyu(series_a, series_b, alternative="two-sided")
    r = 1.0 - (2.0 * u_stat) / (n1 * n2)
    return float(r)


def _matched_pairs_rank_biserial(pre: pd.Series, post: pd.Series) -> float:
    """Matched-pairs rank-biserial correlation for Wilcoxon signed-rank.

    r = 1 - (4 * W) / (n * (n + 1))   where W is the smaller of T+ and T-,
    but we compute from the signed-rank statistic directly.
    """
    diff = (pre - post).dropna()
    n = len(diff)
    if n < 2:
        return 0.0
    # Compute signed ranks.
    abs_diff = diff.abs()
    ranks = abs_diff.rank(method="average")
    # Remove zero-difference pairs before rank calculation (scipy convention).
    # We use the signed-rank sum directly.
    _, p = sp_stats.wilcoxon(pre, post, correction=False)
    # Approximate rank-biserial from Z if we can, else fallback.
    t_plus = ranks[diff > 0].sum()
    t_minus = ranks[diff < 0].sum()
    w = min(t_plus, t_minus)
    total = n * (n + 1) / 2
    r = 1.0 - (2.0 * w) / total
    return float(r)


def _eta_squared(ss_between: float, ss_total: float) -> float:
    """Eta-squared = SS_between / SS_total."""
    if ss_total == 0:
        return 0.0
    return float(ss_between / ss_total)


def _epsilon_squared(h_stat: float, n: int, k: int) -> float:
    """Epsilon-squared for Kruskal-Wallis.

    ε² = (H - k + 1) / (n - k)
    Simplified: ε² = H / ((n² - 1) / (n + 1) * something)
    Common formula: ε² = H / (n - 1) * (n / (n - 1)) ... 
    Using standard: ε² = H / (n + 1) ... no.
    
    Standard formula (Tomczak & Tomczak, 2014):
    ε² = H / ((n² - 1) / (n + 1)) = H / (n - 1)
    Actually the simpler: ε² = H / (n * (n + 1) / (n + 1))... 
    
    Using: ε² = H / ( (n² - 1) / (n + 1) * k/(k-1) ) is overcomplicated.
    Simple: ε² = (H - k + 1) / (n - k) for small samples, or:
    ε² = H / ( (n² - 1) / (n + 1) ) ... 
    
    Let's use the standard formula from literature:
    ε² = H / ((N² - 1) / (N + 1)) where N = n
    Simplified: ε² = H / (N - 1)
    
    Actually the most common formula: ε² = H / ( (N² - 1) / (N + 1) ) = H / (N - 1)
    
    Wait — that gives H/(N-1). Let me verify with a reference:
    Tomczak & Tomczak (2014): ε² = H / ((N² - 1) / (N + 1))
    = H * (N + 1) / (N² - 1) = H * (N + 1) / ((N - 1)(N + 1)) = H / (N - 1)
    
    So ε² = H / (N - 1)
    """
    if n <= 1:
        return 0.0
    return float(h_stat / (n - 1))


def _mean_ci(series: pd.Series) -> Dict[str, float]:
    """Compute mean, SD, and 95% CI for a series."""
    clean = series.dropna()
    n = len(clean)
    if n == 0:
        return {"mean": 0.0, "sd": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    mean = float(clean.mean())
    sd = float(clean.std(ddof=1)) if n > 1 else 0.0
    sem = sd / np.sqrt(n) if n > 0 else 0.0
    if n > 1 and sem > 0:
        ci = sem * sp_stats.t.ppf(0.975, df=n - 1)
        ci_lower = mean - ci
        ci_upper = mean + ci
    else:
        ci_lower = mean
        ci_upper = mean
    return {"mean": round(mean, 4), "sd": round(sd, 4), "ci_lower": round(ci_lower, 4), "ci_upper": round(ci_upper, 4)}


# ---------------------------------------------------------------------------
# T-Test
# ---------------------------------------------------------------------------


def ttest(
    df: pd.DataFrame,
    dependent: List[str],
    group: Optional[str] = None,
    paired: bool = False,
) -> Dict[str, Any]:
    """Perform an independent-samples or paired-samples t-test.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : list of str
        Column name(s) for the dependent variable.

        *Paired*: exactly two column names (pre, post).
        *Independent*: exactly one column name when *group* is given.
    group : str, optional
        Grouping column name for independent t-test.
    paired : bool
        If ``True``, perform a paired t-test (requires two *dependent* columns).

    Returns
    -------
    dict
        Test results including group descriptives, statistic, p-value,
        Cohen's *d*, and interpretation fields.
    """
    # --- Paired t-test ---
    if paired:
        if len(dependent) != 2:
            return error("Paired t-test requires exactly two dependent columns (pre, post).")
        pre_col, post_col = dependent[0], dependent[1]
        common = df[[pre_col, post_col]].dropna()
        pre = common[pre_col]
        post = common[post_col]
        n = len(pre)

        if n < 2:
            return error("Not enough observations after removing missing values.")

        stat, p_value = sp_stats.ttest_rel(pre, post)
        dz = _cohens_dz(pre, post)

        pre_desc = _mean_ci(pre)
        post_desc = _mean_ci(post)
        diff = pre - post
        diff_desc = _mean_ci(diff)

        return {
            "test_name": "Paired t-test",
            "statistic": round(float(stat), 4),
            "df": int(n - 1),
            "p_value": float(p_value),
            "effect_size": round(dz, 4),
            "effect_size_name": "Cohen's dz",
            "effect_size_interpretation": _interpret_cohens_d(dz),
            "ci": {
                "method": "mean difference 95% CI",
                "lower": round(diff_desc["ci_lower"], 4),
                "upper": round(diff_desc["ci_upper"], 4),
            },
            "descriptives": {
                "pre": pre_desc,
                "post": post_desc,
                "mean_difference": round(diff_desc["mean"], 4),
            },
            "n": n,
            "interpretation": None,  # filled by interpreter layer
        }

    # --- Independent t-test ---
    if group is None:
        return error("Independent t-test requires a 'group' column.")

    if len(dependent) != 1:
        return {
            "error": "Independent t-test requires exactly one dependent column "
                     "when used with a group column."
        }

    dep = dependent[0]
    data = df[[dep, group]].dropna()
    groups = data[group].unique()
    if len(groups) != 2:
        return error(f"Independent t-test requires exactly two groups; found {len(groups)}.")

    grp_a_label, grp_b_label = str(groups[0]), str(groups[1])
    grp_a = data.loc[data[group] == groups[0], dep]
    grp_b = data.loc[data[group] == groups[1], dep]

    n_a, n_b = len(grp_a), len(grp_b)
    if n_a < 2 or n_b < 2:
        return error("Both groups must have at least 2 non-missing observations.")

    # Levene's test for equality of variances.
    levene_stat, levene_p = sp_stats.levene(grp_a, grp_b)
    equal_var = levene_p > 0.05

    # Welch t-test if variances unequal, Student's if equal.
    stat, p_value = sp_stats.ttest_ind(grp_a, grp_b, equal_var=equal_var)
    dof = _welch_df(grp_a, grp_b) if not equal_var else (n_a + n_b - 2)

    d = _cohens_d(grp_a, grp_b)

    a_desc = _mean_ci(grp_a)
    b_desc = _mean_ci(grp_b)

    return {
        "test_name": "Independent t-test",
        "statistic": round(float(stat), 4),
        "df": round(dof, 2) if not equal_var else int(dof),
        "p_value": float(p_value),
        "effect_size": round(d, 4),
        "effect_size_name": "Cohen's d",
        "effect_size_interpretation": _interpret_cohens_d(abs(d)),
        "levene": {
            "statistic": round(float(levene_stat), 4),
            "p_value": float(levene_p),
            "equal_variances_assumed": bool(equal_var),
        },
        "ci": {
            "method": "mean difference 95% CI",
            "lower": round(a_desc["ci_lower"] - b_desc["ci_upper"], 4),
            "upper": round(a_desc["ci_upper"] - b_desc["ci_lower"], 4),
        },
        "descriptives": {
            str(groups[0]): a_desc,
            str(groups[1]): b_desc,
        },
        "n": {"total": n_a + n_b, "group_a": n_a, "group_b": n_b},
        "interpretation": None,
    }


def _welch_df(series_a: pd.Series, series_b: pd.Series) -> float:
    """Welch-Satterthwaite degrees of freedom."""
    n1, n2 = len(series_a), len(series_b)
    v1 = series_a.var(ddof=1)
    v2 = series_b.var(ddof=1)
    num = (v1 / n1 + v2 / n2) ** 2
    denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    if denom == 0:
        return float(n1 + n2 - 2)
    return float(num / denom)


def _interpret_cohens_d(d: float) -> str:
    """Return a verbal label for Cohen's *d* magnitude."""
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    if ad < 0.5:
        return "small"
    if ad < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Mann-Whitney U
# ---------------------------------------------------------------------------


def mannwhitney(
    df: pd.DataFrame,
    dependent: str,
    group: str,
) -> Dict[str, Any]:
    """Perform a Mann-Whitney U test.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Dependent variable column name.
    group : str
        Grouping column name (must have exactly two groups).

    Returns
    -------
    dict
        Test results including U statistic, p-value, rank-biserial correlation,
        and group medians.
    """
    data = df[[dependent, group]].dropna()
    groups = data[group].unique()
    if len(groups) != 2:
        return error(f"Mann-Whitney U requires exactly two groups; found {len(groups)}.")

    grp_a_label, grp_b_label = str(groups[0]), str(groups[1])
    grp_a = data.loc[data[group] == groups[0], dependent]
    grp_b = data.loc[data[group] == groups[1], dependent]

    n_a, n_b = len(grp_a), len(grp_b)

    u_stat, p_value = sp_stats.mannwhitneyu(grp_a, grp_b, alternative="two-sided")
    rb = _rank_biserial(grp_a, grp_b)

    return {
        "test_name": "Mann-Whitney U",
        "statistic": float(u_stat),
        "statistic_name": "U",
        "p_value": float(p_value),
        "effect_size": round(rb, 4),
        "effect_size_name": "Rank-biserial correlation (r)",
        "effect_size_interpretation": _interpret_rank_biserial(abs(rb)),
        "descriptives": {
            str(groups[0]): {
                "n": n_a,
                "median": round(float(grp_a.median()), 4),
                "iqr": round(float(grp_a.quantile(0.75) - grp_a.quantile(0.25)), 4),
                "mean_rank": round(float(grp_a.rank().mean()), 2),
            },
            str(groups[1]): {
                "n": n_b,
                "median": round(float(grp_b.median()), 4),
                "iqr": round(float(grp_b.quantile(0.75) - grp_b.quantile(0.25)), 4),
                "mean_rank": round(float(grp_b.rank().mean()), 2),
            },
        },
        "n": {"total": n_a + n_b, "group_a": n_a, "group_b": n_b},
        "interpretation": None,
    }


def _interpret_rank_biserial(r: float) -> str:
    ad = abs(r)
    if ad < 0.1:
        return "negligible"
    if ad < 0.3:
        return "small"
    if ad < 0.5:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Wilcoxon Signed-Rank
# ---------------------------------------------------------------------------


def wilcoxon(
    df: pd.DataFrame,
    pre: str,
    post: str,
) -> Dict[str, Any]:
    """Perform a Wilcoxon signed-rank test for paired data.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    pre : str
        Pre-intervention (or time 1) column.
    post : str
        Post-intervention (or time 2) column.

    Returns
    -------
    dict
        Test results including W statistic, p-value, and effect size.
    """
    common = df[[pre, post]].dropna()
    pre_series = common[pre]
    post_series = common[post]
    n = len(pre_series)

    if n < 2:
        return error("Not enough paired observations after removing missing values.")

    # Compute with continuity correction.
    stat, p_value = sp_stats.wilcoxon(pre_series, post_series, correction=True)
    rb = _matched_pairs_rank_biserial(pre_series, post_series)

    # Z approximation.
    w = float(stat)
    z = (w - n * (n + 1) / 4) / np.sqrt(n * (n + 1) * (2 * n + 1) / 24)

    pre_desc = _mean_ci(pre_series)
    post_desc = _mean_ci(post_series)

    return {
        "test_name": "Wilcoxon Signed-Rank",
        "statistic": float(stat),
        "statistic_name": "W",
        "p_value": float(p_value),
        "z_value": round(float(z), 4),
        "effect_size": round(rb, 4),
        "effect_size_name": "Matched-pairs rank-biserial (r)",
        "effect_size_interpretation": _interpret_rank_biserial(abs(rb)),
        "descriptives": {
            "pre": {
                "n": n,
                "median": round(float(pre_series.median()), 4),
                "mean": round(float(pre_series.mean()), 4),
                "sd": round(float(pre_series.std(ddof=1)), 4) if n > 1 else 0.0,
            },
            "post": {
                "n": n,
                "median": round(float(post_series.median()), 4),
                "mean": round(float(post_series.mean()), 4),
                "sd": round(float(post_series.std(ddof=1)), 4) if n > 1 else 0.0,
            },
        },
        "n": n,
        "interpretation": None,
    }


# ---------------------------------------------------------------------------
# One-Way ANOVA
# ---------------------------------------------------------------------------


def anova_oneway(
    df: pd.DataFrame,
    dependent: str,
    group: str,
) -> Dict[str, Any]:
    """Perform a one-way ANOVA with Tukey HSD post-hoc tests.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Dependent variable column name.
    group : str
        Grouping column name.

    Returns
    -------
    dict
        ANOVA table, eta-squared, Tukey HSD pairwise comparisons, group descriptives.
    """
    data = df[[dependent, group]].dropna()
    groups = data[group].unique()
    group_vals = [data.loc[data[group] == g, dependent].dropna() for g in groups]
    group_labels = [str(g) for g in groups]

    # Basic checks.
    group_n = [len(gv) for gv in group_vals]
    if any(n < 2 for n in group_n):
        return error("All groups must have at least 2 observations.")
    if len(groups) < 2:
        return error("At least 2 groups are required for ANOVA.")

    # One-way ANOVA.
    f_stat, p_value = sp_stats.f_oneway(*group_vals)

    # Degrees of freedom.
    k = len(groups)
    n_total = sum(group_n)
    df_between = k - 1
    df_within = n_total - k

    # Sum of squares for eta-squared.
    grand_mean = data[dependent].mean()
    ss_between = sum(
        n * (gv.mean() - grand_mean) ** 2 for n, gv in zip(group_n, group_vals)
    )
    ss_within = sum(((gv - gv.mean()) ** 2).sum() for gv in group_vals)
    ss_total = ss_between + ss_within
    eta_sq = _eta_squared(ss_between, ss_total)

    # Group descriptives.
    descriptives = {}
    for i, label in enumerate(group_labels):
        gv = group_vals[i]
        desc = _mean_ci(gv)
        desc["n"] = len(gv)
        descriptives[label] = desc

    # Tukey HSD post-hoc via pingouin.
    pairwise: List[Dict[str, Any]] = []
    try:
        import pingouin as pg

        pg_result = pg.pairwise_tukey(
            data=data, dv=dependent, between=group, effsize="hedges"
        )
        for _, row in pg_result.iterrows():
            diff_val = float(row["diff"]) if "diff" in pg_result.columns else float(row.get("mean", 0))
            p_val = float(row["p_tukey"])
            hedges_val = round(float(row["hedges"]), 4) if "hedges" in row and pd.notna(row["hedges"]) else None
            pairwise.append(
                {
                    "group_a": str(row["A"]),
                    "group_b": str(row["B"]),
                    "mean_difference": round(diff_val, 4),
                    "p_value": p_val,
                    "significant": bool(p_val < 0.05),
                    "hedges_g": hedges_val,
                }
            )
    except ImportError:
        pairwise = None

    return {
        "test_name": "One-Way ANOVA",
        "statistic": round(float(f_stat), 4),
        "statistic_name": "F",
        "df": {"between": df_between, "within": df_within},
        "p_value": float(p_value),
        "effect_size": round(eta_sq, 4),
        "effect_size_name": "Eta-squared (η²)",
        "effect_size_interpretation": _interpret_eta_squared(eta_sq),
        "ss": {
            "between": round(float(ss_between), 4),
            "within": round(float(ss_within), 4),
            "total": round(float(ss_total), 4),
        },
        "ms": {
            "between": round(float(ss_between / df_between), 4) if df_between > 0 else 0.0,
            "within": round(float(ss_within / df_within), 4) if df_within > 0 else 0.0,
        },
        "descriptives": descriptives,
        "post_hoc": {
            "method": "Tukey HSD",
            "comparisons": pairwise,
        },
        "n": n_total,
        "k": k,
        "interpretation": None,
    }


def _interpret_eta_squared(eta2: float) -> str:
    """Verbal label for eta-squared."""
    if eta2 < 0.01:
        return "negligible"
    if eta2 < 0.06:
        return "small"
    if eta2 < 0.14:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Kruskal-Wallis
# ---------------------------------------------------------------------------


def kruskal_wallis(
    df: pd.DataFrame,
    dependent: str,
    group: str,
) -> Dict[str, Any]:
    """Perform a Kruskal-Wallis H test with Dunn post-hoc comparisons.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Dependent variable column name.
    group : str
        Grouping column name.

    Returns
    -------
    dict
        Test results including H statistic, epsilon-squared, Dunn post-hoc.
    """
    data = df[[dependent, group]].dropna()
    groups = data[group].unique()
    group_vals = [data.loc[data[group] == g, dependent].dropna() for g in groups]
    group_labels = [str(g) for g in groups]

    group_n = [len(gv) for gv in group_vals]
    if any(n < 2 for n in group_n):
        return error("All groups must have at least 2 observations.")
    if len(groups) < 2:
        return error("At least 2 groups are required for Kruskal-Wallis.")

    h_stat, p_value = sp_stats.kruskal(*group_vals)
    k = len(groups)
    n_total = sum(group_n)
    eps_sq = _epsilon_squared(h_stat, n_total, k)

    # Dunn post-hoc via pingouin.
    pairwise: List[Dict[str, Any]] = []
    try:
        import pingouin as pg

        pg_result = pg.pairwise_tests(
            data=data,
            dv=dependent,
            between=group,
            padjust="holm",
            effsize="CLES",
        )
        for _, row in pg_result.iterrows():
            pairwise.append(
                {
                    "group_a": str(row["A"]),
                    "group_b": str(row["B"]),
                    "u_stat": round(float(row["U"]), 4) if "U" in row else None,
                    "p_value": float(row.get("p_unc", 1.0)),
                    "p_adjusted": float(row.get("p_corr", row.get("p_unc", 1.0))),
                    "significant": bool(row.get("p_corr", row.get("p_unc", 1.0)) < 0.05),
                    "effect_size": round(float(row.get("CLES", 0)), 4) if "CLES" in row else None,
                    "effect_size_name": "CLES",
                }
            )
    except ImportError:
        # Fallback: simple pairwise Mann-Whitney with Bonferroni.
        from itertools import combinations
        n_comparisons = k * (k - 1) / 2
        for (i, j) in combinations(range(k), 2):
            u, up = sp_stats.mannwhitneyu(group_vals[i], group_vals[j], alternative="two-sided")
            pairwise.append(
                {
                    "group_a": group_labels[i],
                    "group_b": group_labels[j],
                    "u_stat": float(u),
                    "p_value": float(up),
                    "p_adjusted": min(float(up * n_comparisons), 1.0),
                    "significant": bool(up * n_comparisons < 0.05),
                }
            )

    descriptives = {}
    for i, label in enumerate(group_labels):
        gv = group_vals[i]
        descriptives[label] = {
            "n": len(gv),
            "median": round(float(gv.median()), 4),
            "iqr": round(float(gv.quantile(0.75) - gv.quantile(0.25)), 4),
            "mean_rank": round(float(gv.rank().mean()), 2),
        }

    return {
        "test_name": "Kruskal-Wallis H",
        "statistic": round(float(h_stat), 4),
        "statistic_name": "H",
        "df": int(k - 1),
        "p_value": float(p_value),
        "effect_size": round(eps_sq, 4),
        "effect_size_name": "Epsilon-squared (ε²)",
        "effect_size_interpretation": _interpret_epsilon_squared(eps_sq),
        "descriptives": descriptives,
        "post_hoc": {
            "method": "Dunn (Holm-corrected)",
            "comparisons": pairwise,
        },
        "n": n_total,
        "k": k,
        "interpretation": None,
    }


def _interpret_epsilon_squared(eps2: float) -> str:
    """Verbal label for epsilon-squared."""
    if eps2 < 0.01:
        return "negligible"
    if eps2 < 0.04:
        return "small"
    if eps2 < 0.16:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Chi-Square Test of Independence
# ---------------------------------------------------------------------------


def chisquare(
    df: pd.DataFrame,
    row: str,
    col: str,
) -> Dict[str, Any]:
    """Perform a chi-square test of independence with Cramer's V.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    row : str
        Row variable column name.
    col : str
        Column variable column name.

    Returns
    -------
    dict
        Test results including chi-square, Cramer's V, Fisher's exact (2×2),
        and contingency table.
    """
    from .descriptive import crosstab as _crosstab

    ct = _crosstab(df, row, col)
    if "error" in ct:
        return ct

    # Extract needed values.
    chi2_stat = ct["chi2"]
    chi2_dof = ct["df"]
    chi2_p = ct["p_value"]
    cramers_v = ct["cramers_v"]
    n_total = ct["n"]

    # Fisher's exact for 2x2.
    fisher = ct.get("fisher_exact")

    return {
        "test_name": "Chi-Square Test of Independence",
        "statistic": chi2_stat,
        "statistic_name": "χ²",
        "df": chi2_dof,
        "p_value": chi2_p,
        "effect_size": cramers_v,
        "effect_size_name": "Cramer's V",
        "effect_size_interpretation": _interpret_cramers_v(cramers_v),
        "n": n_total,
        "min_expected": ct["min_expected"],
        "contingency_table": ct["table"],
        "expected": ct["expected"],
        "percentages": ct["percentages"],
        "fisher_exact": fisher,
        "interpretation": None,
    }


def _interpret_cramers_v(v: float) -> str:
    """Verbal label for Cramer's V."""
    ad = abs(v)
    if ad < 0.1:
        return "negligible"
    if ad < 0.3:
        return "small"
    if ad < 0.5:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Two-Way (Factorial) ANOVA
# ---------------------------------------------------------------------------


def anova_twoway(
    df: pd.DataFrame,
    dependent: str,
    factor1: str,
    factor2: str,
) -> Dict[str, Any]:
    """Perform a two-way (factorial) ANOVA with interaction.

    Uses ``statsmodels`` for Type II sums of squares.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    dependent : str
        Dependent variable column name.
    factor1 : str
        First factor column name.
    factor2 : str
        Second factor column name.

    Returns
    -------
    dict
        With keys ``anova_table``, ``descriptives``, ``effect_sizes``,
        ``n``, ``factors``, and ``interpretation``.
    """
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm

    # Validate columns.
    for col in [dependent, factor1, factor2]:
        if col not in df.columns:
            return error(f"Column '{col}' not found in DataFrame.")

    df_clean = df[[dependent, factor1, factor2]].dropna()
    n = len(df_clean)

    if n < 6:
        return error("Insufficient data (need at least 6 complete cases).")

    # Ensure factors are categorical.
    df_model = df_clean.copy()
    df_model[factor1] = df_model[factor1].astype("category")
    df_model[factor2] = df_model[factor2].astype("category")

    # Fit two-way ANOVA model.
    formula = f"Q('{dependent}') ~ C(Q('{factor1}')) * C(Q('{factor2}'))"
    try:
        model = smf.ols(formula, data=df_model).fit()
    except Exception as e:
        return error(f"Two-way ANOVA failed to fit: {e}")

    # ANOVA table (Type II).
    try:
        anova = anova_lm(model, typ=2)
    except Exception as e:
        return error(f"Failed to compute ANOVA table: {e}")

    anova_table = []
    for row_name in anova.index:
        row = anova.loc[row_name]
        anova_table.append({
            "source": str(row_name),
            "df": float(row["df"]) if "df" in row else None,
            "sum_sq": round(float(row["sum_sq"]), 4) if "sum_sq" in row else None,
            "mean_sq": round(float(row["mean_sq"]), 4) if "mean_sq" in row else None,
            "f": round(float(row["F"]), 4) if "F" in row else None,
            "p_value": round(float(row["PR(>F)"]), 4) if "PR(>F)" in row else None,
        })

    # Group descriptives: marginal + cell means.
    # Overall.
    overall_desc = _mean_ci(df_model[dependent])

    # Marginal means for factor1.
    f1_marginal = {}
    for level in df_model[factor1].cat.categories:
        series = df_model.loc[df_model[factor1] == level, dependent]
        desc = _mean_ci(series)
        desc["n"] = len(series)
        f1_marginal[str(level)] = desc

    # Marginal means for factor2.
    f2_marginal = {}
    for level in df_model[factor2].cat.categories:
        series = df_model.loc[df_model[factor2] == level, dependent]
        desc = _mean_ci(series)
        desc["n"] = len(series)
        f2_marginal[str(level)] = desc

    desc_marginal = {
        factor1: f1_marginal,
        factor2: f2_marginal,
    }

    # Cell means.
    cell_means = {}
    for f1_level in df_model[factor1].cat.categories:
        cell_means[str(f1_level)] = {}
        for f2_level in df_model[factor2].cat.categories:
            series = df_model.loc[
                (df_model[factor1] == f1_level) & (df_model[factor2] == f2_level),
                dependent,
            ]
            desc = _mean_ci(series)
            desc["n"] = len(series)
            cell_means[str(f1_level)][str(f2_level)] = desc

    descriptives = {
        "overall": overall_desc,
        "marginal": desc_marginal,
        "cell": cell_means,
    }

    # Effect sizes (partial eta-squared).
    ss_total = sum(row["sum_sq"] for row in anova_table if row["sum_sq"] is not None)
    ss_residual = next((row["sum_sq"] for row in anova_table if "Residual" in str(row["source"])), 0)
    effect_sizes = {}
    for row in anova_table:
        source = row["source"]
        if "Residual" in str(source):
            continue
        ss_effect = row.get("sum_sq", 0) or 0
        denom = ss_effect + ss_residual
        if denom > 0:
            partial_eta2 = round(float(ss_effect / denom), 4)
        else:
            partial_eta2 = 0.0
        effect_sizes[source] = {
            "partial_eta_squared": partial_eta2,
            "interpretation": _interpret_eta_squared(partial_eta2),
        }

    # Interpretation.
    interpretation = _interpret_anova_twoway(anova_table, effect_sizes, dependent, factor1, factor2)

    return {
        "test_name": "Two-Way ANOVA",
        "anova_table": anova_table,
        "descriptives": descriptives,
        "effect_sizes": effect_sizes,
        "n": n,
        "factors": {
            "factor1": factor1,
            "factor2": factor2,
            "factor1_levels": [str(c) for c in df_model[factor1].cat.categories],
            "factor2_levels": [str(c) for c in df_model[factor2].cat.categories],
        },
        "dependent": dependent,
        "interpretation": interpretation,
    }


def _interpret_anova_twoway(
    anova_table: List[Dict],
    effect_sizes: Dict,
    dependent: str,
    factor1: str,
    factor2: str,
) -> str:
    """Generate plain-English interpretation for two-way ANOVA."""
    parts = [
        f"A two-way factorial ANOVA was conducted to examine the effects of "
        f"'{factor1}' and '{factor2}' on '{dependent}'. "
    ]

    # Main effects and interaction.
    sig_sources = []
    for row in anova_table:
        source = row["source"]
        if "Residual" in str(source):
            continue
        p = row.get("p_value", 1)
        f_val = row.get("f", 0)
        df = row.get("df", 0)
        es = effect_sizes.get(source, {}).get("partial_eta_squared", 0)
        es_int = effect_sizes.get(source, {}).get("interpretation", "")
        sig = "significant" if p and p < 0.05 else "not significant"
        parts.append(
            f"{source}: F({int(df)}) = {f_val}, p = {p:.4f} ({sig}, "
            f"partial η² = {es}, {es_int}). "
        )
        if p and p < 0.05:
            sig_sources.append(source)

    if not sig_sources:
        parts.append("No significant effects were found.")
    else:
        parts.append(f"Significant effects found: {', '.join(sig_sources)}. ")

    return "".join(parts)
