"""
Plain-English interpretation service for DevStat.

Turns structured statistical outputs into human-readable, APA-style
interpretation strings suitable for medical / clinical reporting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# P-value helper
# ---------------------------------------------------------------------------


def interpret_p_value(p: float) -> str:
    """Return a verbal description of a *p*-value.

    Parameters
    ----------
    p : float
        The *p*-value.

    Returns
    -------
    str
        ``"highly significant (p < 0.001)"``,
        ``"very significant (p < 0.01)"``,
        ``"statistically significant (p < 0.05)"``, or
        ``"not statistically significant (p ≥ 0.05)"``.
    """
    if p < 0.001:
        return "highly significant (p < 0.001)"
    if p < 0.01:
        return "very significant (p < 0.01)"
    if p < 0.05:
        return "statistically significant (p < 0.05)"
    return "not statistically significant (p ≥ 0.05)"


def _p_str(p: float) -> str:
    """Format a *p*-value for inline display."""
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.3f}"


# ---------------------------------------------------------------------------
# Effect-size interpretation
# ---------------------------------------------------------------------------


def interpret_effect_size(name: str, value: float) -> str:
    """Return a verbal label for common effect size measures.

    Supports: Cohen's *d*, Cohen's *d\\ :sub:`z`*, eta-squared (η²),
    epsilon-squared (ε²), Cramer's *V*, rank-biserial *r*,
    Pearson's *r*, and odds ratio.

    Parameters
    ----------
    name : str
        Name of the effect size measure (case-insensitive).
    value : float
        The effect size value.

    Returns
    -------
    str
        Human-readable label, e.g. ``"large effect"``.
    """
    name_lower = name.lower().strip()
    av = abs(value)

    # Cohen's d / dz / Hedges' g
    if any(x in name_lower for x in ("cohen", "hedges", "dz", "d")):
        if "dz" in name_lower or "dz" in name:
            return _cohens_dz_label(av)
        return _cohens_d_label(av)

    # Eta-squared
    if "eta" in name_lower or "η" in name_lower:
        return _eta_sq_label(av)

    # Epsilon-squared
    if "epsilon" in name_lower or "ε" in name_lower:
        return _epsilon_sq_label(av)

    # Cramer's V
    if "cramer" in name_lower or "v" == name_lower.strip():
        return _cramers_v_label(av)

    # Rank-biserial / r
    if "rank" in name_lower or "biserial" in name_lower or "r" == name_lower.strip():
        return _r_label(av)

    # Pearson's r
    if "pearson" in name_lower or "correlation" in name_lower:
        return _r_label(av)

    # Odds ratio
    if "odds" in name_lower or "or" == name_lower.strip():
        return _odds_ratio_label(av)

    return f"unspecified effect size ({value:.2f})"


# Internal effect-size magnitude helpers.
def _cohens_d_label(d: float) -> str:
    if d < 0.2:
        return "negligible effect"
    if d < 0.5:
        return "small effect"
    if d < 0.8:
        return "medium effect"
    return "large effect"


def _cohens_dz_label(dz: float) -> str:
    if dz < 0.2:
        return "negligible effect"
    if dz < 0.5:
        return "small effect"
    if dz < 0.8:
        return "medium effect"
    return "large effect"


def _eta_sq_label(eta2: float) -> str:
    if eta2 < 0.01:
        return "negligible effect"
    if eta2 < 0.06:
        return "small effect"
    if eta2 < 0.14:
        return "medium effect"
    return "large effect"


def _epsilon_sq_label(eps2: float) -> str:
    if eps2 < 0.01:
        return "negligible effect"
    if eps2 < 0.04:
        return "small effect"
    if eps2 < 0.16:
        return "medium effect"
    return "large effect"


def _cramers_v_label(v: float) -> str:
    if v < 0.1:
        return "negligible association"
    if v < 0.3:
        return "weak association"
    if v < 0.5:
        return "moderate association"
    return "strong association"


def _r_label(r: float) -> str:
    if r < 0.1:
        return "negligible correlation"
    if r < 0.3:
        return "weak correlation"
    if r < 0.5:
        return "moderate correlation"
    return "strong correlation"


def _odds_ratio_label(or_val: float) -> str:
    if or_val < 1.5:
        return "negligible association"
    if or_val < 3.5:
        return "weak association"
    if or_val < 9.0:
        return "moderate association"
    return "strong association"


# ---------------------------------------------------------------------------
# T-Test interpretation
# ---------------------------------------------------------------------------


def interpret_ttest(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a t-test result.

    Parameters
    ----------
    result : dict
        Output from :func:`compare.ttest`.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    if "error" in result:
        return f"Could not perform t-test: {result['error']}"

    test_name = result.get("test_name", "t-test")
    is_paired = "Paired" in test_name
    stat = result.get("statistic", 0)
    df = result.get("df", 0)
    p = result.get("p_value", 1.0)
    d = result.get("effect_size", 0)
    es_name = result.get("effect_size_name", "Cohen's d")
    es_label = result.get("effect_size_interpretation", "unknown")
    sig_label = interpret_p_value(p)

    if is_paired:
        desc = result.get("descriptives", {})
        pre = desc.get("pre", {})
        post = desc.get("post", {})
        md = desc.get("mean_difference", 0)

        return (
            f"A paired-samples t-test was conducted to compare "
            f"pre-intervention (M = {pre.get('mean', 'N/A')}, "
            f"SD = {pre.get('sd', 'N/A')}) and "
            f"post-intervention (M = {post.get('mean', 'N/A')}, "
            f"SD = {post.get('sd', 'N/A')}) scores. "
            f"The mean difference was {md:.2f}. "
            f"The result was {sig_label} "
            f"(t({df}) = {stat}, {_p_str(p)}). "
            f"The effect size was {es_name} = {d:.2f}, indicating "
            f"a {es_label}."
        )

    # Independent t-test.
    desc = result.get("descriptives", {})
    groups = list(desc.keys()) if desc else ["Group 1", "Group 2"]
    group_labels = groups[:2]
    g1, g2 = group_labels[0], group_labels[1] if len(group_labels) > 1 else "Group 2"
    g1_desc = desc.get(g1, {})
    g2_desc = desc.get(g2, {})

    n_info = result.get("n", {})
    n1 = n_info.get("group_a", n_info.get(g1, g1_desc.get("n", "N/A")))
    n2 = n_info.get("group_b", n_info.get(g2, g2_desc.get("n", "N/A")))

    # Format df flexibly (int or float).
    df_str = str(int(df)) if isinstance(df, float) and df == int(df) else str(df)

    return (
        f"An independent-samples t-test was conducted to compare "
        f"{g1} (M = {g1_desc.get('mean', 'N/A')}, "
        f"SD = {g1_desc.get('sd', 'N/A')}, n = {n1}) and "
        f"{g2} (M = {g2_desc.get('mean', 'N/A')}, "
        f"SD = {g2_desc.get('sd', 'N/A')}, n = {n2}). "
        f"The result was {sig_label} "
        f"(t({df_str}) = {stat}, {_p_str(p)}). "
        f"The effect size was {es_name} = {d:.2f}, indicating "
        f"a {es_label}."
    )


# ---------------------------------------------------------------------------
# ANOVA interpretation
# ---------------------------------------------------------------------------


def interpret_anova(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a one-way ANOVA result.

    Parameters
    ----------
    result : dict
        Output from :func:`compare.anova_oneway`.

    Returns
    -------
    str
        APA-style interpretation paragraph with post-hoc details.
    """
    if "error" in result:
        return f"Could not perform ANOVA: {result['error']}"

    f_stat = result.get("statistic", 0)
    df = result.get("df", {})
    p = result.get("p_value", 1.0)
    eta2 = result.get("effect_size", 0)
    es_label = result.get("effect_size_interpretation", "unknown")
    desc = result.get("descriptives", {})
    post_hoc = result.get("post_hoc", {})
    sig_label = interpret_p_value(p)

    # Build descriptives text.
    group_ms: List[str] = []
    for label, stats in desc.items():
        group_ms.append(
            f"{label} (M = {stats.get('mean', 'N/A')}, "
            f"SD = {stats.get('sd', 'N/A')}, n = {stats.get('n', 'N/A')})"
        )
    groups_text = ", ".join(group_ms)

    df_between = df.get("between", "?")
    df_within = df.get("within", "?")

    result_text = (
        f"A one-way between-subjects ANOVA was conducted to compare "
        f"the means of {len(group_ms)} groups: {groups_text}. "
        f"The analysis revealed {sig_label} "
        f"(F({df_between}, {df_within}) = {f_stat}, {_p_str(p)}). "
        f"The effect size was η² = {eta2:.3f}, indicating "
        f"a {es_label}."
    )

    # Post-hoc results.
    comparisons = post_hoc.get("comparisons")
    if comparisons:
        sig_pairs = [c for c in comparisons if c.get("significant")]
        if sig_pairs:
            pair_texts: List[str] = []
            for c in sig_pairs:
                pair_texts.append(
                    f"{c['group_a']} vs {c['group_b']} "
                    f"(p = {c.get('p_value', 0):.3f})"
                )
            result_text += (
                f" Post-hoc comparisons using Tukey HSD identified "
                f"{len(sig_pairs)} significant pairwise difference(s): "
                f"{'; '.join(pair_texts)}."
            )
        else:
            result_text += (
                " Post-hoc Tukey HSD comparisons did not identify "
                "any significant pairwise differences."
            )

    return result_text


# ---------------------------------------------------------------------------
# Chi-Square interpretation
# ---------------------------------------------------------------------------


def interpret_chisquare(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a chi-square test.

    Parameters
    ----------
    result : dict
        Output from :func:`compare.chisquare`.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    if "error" in result:
        return f"Could not perform chi-square test: {result['error']}"

    chisq = result.get("statistic", 0)
    df = result.get("df", 0)
    p = result.get("p_value", 1.0)
    v = result.get("effect_size", 0)
    es_label = result.get("effect_size_interpretation", "unknown")
    n = result.get("n", 0)
    min_exp = result.get("min_expected", None)
    sig_label = interpret_p_value(p)

    row_var = result.get("row", "the row variable")
    col_var = result.get("col", "the column variable")
    fisher = result.get("fisher_exact")

    result_text = (
        f"A chi-square test of independence was conducted to examine "
        f"the relationship between {row_var} and {col_var}. "
        f"The result was {sig_label} "
        f"(χ²({df}, N = {n}) = {chisq}, {_p_str(p)}). "
        f"The association strength was Cramer's V = {v:.3f}, "
        f"indicating a {es_label}."
    )

    # Note on expected frequencies.
    if min_exp is not None:
        if min_exp < 1:
            result_text += (
                f" Caution: the minimum expected frequency was {min_exp:.2f}, "
                f"which is below the recommended threshold of 1."
            )
        elif min_exp < 5:
            result_text += (
                f" Note: {min_exp:.1f} of expected frequencies were below 5."
            )

    # Fisher's exact note.
    if fisher:
        fp = fisher.get("p_value", 1.0)
        or_val = fisher.get("odds_ratio", None)
        fish_sig = interpret_p_value(fp)
        if or_val is not None:
            result_text += (
                f" Fisher's exact test (used for the 2×2 table) confirmed "
                f"{fish_sig} (odds ratio = {or_val:.2f}, {_p_str(fp)})."
            )
        else:
            result_text += (
                f" Fisher's exact test confirmed {fish_sig} ({_p_str(fp)})."
            )

    return result_text


# ---------------------------------------------------------------------------
# Correlation interpretation
# ---------------------------------------------------------------------------


def interpret_correlation(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a correlation result.

    Accepts a dict with keys: ``test_name``, ``r`` (or ``statistic``),
    ``n``, ``p_value``, ``effect_size_interpretation``.

    Parameters
    ----------
    result : dict
        Correlation test result.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    r = result.get("r") or result.get("statistic", 0)
    n = result.get("n", "N/A")
    p = result.get("p_value", 1.0)
    es_label = result.get(
        "effect_size_interpretation",
        interpret_effect_size("Pearson's r", r),
    )
    method = result.get("method", "Pearson")
    var1 = result.get("var1", "variable 1")
    var2 = result.get("var2", "variable 2")
    sig_label = interpret_p_value(p)

    ci = result.get("ci")
    ci_text = ""
    if ci and "lower" in ci and "upper" in ci:
        ci_text = f" 95% CI [{ci['lower']:.3f}, {ci['upper']:.3f}]."

    return (
        f"A {method} correlation was computed to assess the linear "
        f"relationship between {var1} and {var2}. "
        f"There was {sig_label} correlation "
        f"(r({n - 2 if isinstance(n, int) and n > 2 else n}) = {r:.3f}"
        f"{ci_text}, {_p_str(p)}). "
        f"The effect size indicates {es_label}."
    )


# ---------------------------------------------------------------------------
# Regression interpretation
# ---------------------------------------------------------------------------


def interpret_regression(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a regression result.

    Accepts a dict with typical OLS output keys:
    ``test_name``, ``r_squared``, ``adj_r_squared``, ``f_statistic``,
    ``f_p_value``, ``n``, ``k`` (predictors), ``coefficients`` (list of dicts
    with ``name``, ``b``, ``beta``, ``p_value``, ``ci_lower``, ``ci_upper``),
    or alternatively ``predictors`` / ``variables`` for the model terms.

    Parameters
    ----------
    result : dict
        Regression result.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    if "error" in result:
        return f"Could not interpret regression: {result['error']}"

    r2 = result.get("r_squared", result.get("r2", 0))
    adj_r2 = result.get("adj_r_squared", result.get("adj_r2", 0))
    f_stat = result.get("f_statistic", result.get("statistic", 0))
    f_p = result.get("f_p_value", result.get("p_value", 1.0))
    n = result.get("n", result.get("N", "N/A"))
    k = result.get("k", 0)
    dv = result.get("dependent", result.get("dv", "the outcome"))

    # Overall model.
    sig_label = interpret_p_value(f_p)
    if isinstance(n, int) and k > 0:
        df1, df2 = k, n - k - 1
    else:
        df1, df2 = "?", "?"

    text = (
        f"A multiple linear regression was conducted to predict {dv} "
        f"using {k} predictor(s). "
        f"The overall model was {sig_label} "
        f"(F({df1}, {df2}) = {f_stat:.2f}, {_p_str(f_p)}), "
        f"accounting for R² = {r2:.3f} (adjusted R² = {adj_r2:.3f}) "
        f"of the variance in {dv}."
    )

    # Individual predictors.
    coefs: List[Dict[str, Any]] = (
        result.get("coefficients")
        or result.get("predictors")
        or result.get("variables")
        or []
    )
    if coefs:
        pred_texts: List[str] = []
        for pred in coefs:
            name = pred.get("name", pred.get("variable", "predictor"))
            b = pred.get("b", pred.get("coef", 0))
            beta = pred.get("beta", pred.get("standardized_coef", None))
            pp = pred.get("p_value", 1.0)
            p_sig = "significant" if pp < 0.05 else "not significant"
            ci_l = pred.get("ci_lower", None)
            ci_u = pred.get("ci_upper", None)
            ci_part = (
                f", 95% CI [{ci_l:.3f}, {ci_u:.3f}]"
                if ci_l is not None and ci_u is not None
                else ""
            )
            beta_part = f", β = {beta:.3f}" if beta is not None else ""
            pred_texts.append(
                f"{name} (B = {b:.3f}{beta_part}{ci_part}, "
                f"{p_sig}, {_p_str(pp)})"
            )
        text += f" Predictors: {'; '.join(pred_texts)}."

    return text


# ---------------------------------------------------------------------------
# Survival analysis interpretation
# ---------------------------------------------------------------------------


def interpret_survival(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a survival analysis result.

    Accepts a dict with keys:
    ``test_name``, ``statistic`` (log-rank χ² or similar),
    ``p_value``, ``hr`` (hazard ratio), ``hr_ci_lower``, ``hr_ci_upper``,
    ``median_survival`` (dict of group → months/days),
    ``n_events``, ``n_censored``.

    Parameters
    ----------
    result : dict
        Survival analysis result.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    if "error" in result:
        return f"Could not interpret survival analysis: {result['error']}"

    stat = result.get("statistic", 0)
    p = result.get("p_value", 1.0)
    hr = result.get("hr", result.get("hazard_ratio", None))
    hr_ci_l = result.get("hr_ci_lower", None)
    hr_ci_u = result.get("hr_ci_upper", None)
    sig_label = interpret_p_value(p)
    n_events = result.get("n_events", "N/A")
    n_censored = result.get("n_censored", "N/A")

    text = (
        f"A {result.get('test_name', 'Kaplan-Meier')} survival analysis "
        f"was performed."
    )

    if stat and p is not None:
        text += (
            f" The log-rank test was {sig_label} "
            f"(χ² = {stat:.2f}, {_p_str(p)})."
        )

    if hr is not None:
        ci_str = (
            f" 95% CI [{hr_ci_l:.2f}, {hr_ci_u:.2f}]"
            if hr_ci_l is not None and hr_ci_u is not None
            else ""
        )
        text += (
            f" The hazard ratio was HR = {hr:.2f}{ci_str}, "
            f"indicating that the treatment/exposure group had "
            f"{'a higher' if hr > 1 else 'a lower'} risk of the event "
            f"compared to the reference group."
        )

    # Median survival times.
    med_surv = result.get("median_survival", {})
    if med_surv:
        surv_texts = [f"{g}: {v} units" for g, v in med_surv.items()]
        text += f" Median survival times: {', '.join(surv_texts)}."

    text += f" Events observed: {n_events}, censored: {n_censored}."

    return text


# ---------------------------------------------------------------------------
# Diagnostic test interpretation
# ---------------------------------------------------------------------------


def interpret_diagnostic(result: Dict[str, Any]) -> str:
    """Generate a plain-English interpretation of a diagnostic test evaluation.

    Accepts a dict with keys:
    ``test_name``, ``sensitivity``, ``specificity``, ``ppv``, ``npv``,
    ``accuracy``, ``auc`` (ROC AUC), ``prevalence``, ``positive_lr``,
    ``negative_lr``, ``n``, ``tp``, ``fp``, ``fn``, ``tn``.

    Parameters
    ----------
    result : dict
        Diagnostic test evaluation result.

    Returns
    -------
    str
        APA-style interpretation paragraph.
    """
    if "error" in result:
        return f"Could not interpret diagnostic test: {result['error']}"

    sens = result.get("sensitivity")
    spec = result.get("specificity")
    ppv = result.get("ppv")
    npv = result.get("npv")
    acc = result.get("accuracy")
    auc = result.get("auc")
    prev = result.get("prevalence")
    pos_lr = result.get("positive_lr", result.get("lr_plus"))
    neg_lr = result.get("negative_lr", result.get("lr_minus"))
    n = result.get("n", "N/A")

    parts: List[str] = []
    if sens is not None:
        _label = "excellent" if sens >= 0.9 else "good" if sens >= 0.8 else "moderate" if sens >= 0.7 else "poor"
        parts.append(f"sensitivity of {sens:.1%} ({_label})")
    if spec is not None:
        _label = "excellent" if spec >= 0.9 else "good" if spec >= 0.8 else "moderate" if spec >= 0.7 else "poor"
        parts.append(f"specificity of {spec:.1%} ({_label})")
    if ppv is not None:
        parts.append(f"positive predictive value of {ppv:.1%}")
    if npv is not None:
        parts.append(f"negative predictive value of {npv:.1%}")
    if acc is not None:
        parts.append(f"overall accuracy of {acc:.1%}")
    if auc is not None:
        _label = "outstanding" if auc >= 0.9 else "excellent" if auc >= 0.8 else "acceptable" if auc >= 0.7 else "poor"
        parts.append(f"ROC AUC of {auc:.3f} ({_label} discriminatory ability)")
    if pos_lr is not None:
        parts.append(f"positive likelihood ratio of {pos_lr:.2f}")
    if neg_lr is not None:
        parts.append(f"negative likelihood ratio of {neg_lr:.2f}")
    if prev is not None:
        parts.append(f"(prevalence: {prev:.1%})")

    if not parts:
        return "No diagnostic performance metrics were available."

    return (
        f"A diagnostic test evaluation (n = {n}) reported the following "
        f"performance metrics: {'; '.join(parts)}."
    )
