"""
DevStat Analysis Engine — Pure-Python implementation.

All statistical analyses run in-process via scipy, statsmodels,
lifelines, scikit-learn, and other Python packages.

Usage::

    from r.engine import AnalysisEngine

    engine = AnalysisEngine()
    result = engine.run("frequencies", {"column": "treatment_arm"})
"""

from __future__ import annotations

from typing import Any, Dict, List

import app.state as _state


class AnalysisEngine:
    """Analysis engine that runs all analyses in-process via Python packages."""

    def __init__(self):
        self._registry = _build_registry()

    def run(self, analysis_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if _state.current_data is None:
            return {"error": "No dataset is currently loaded. Upload a file first."}
        handler = self._registry.get(analysis_name)
        if handler is None:
            return {"error": f"Unknown analysis: '{analysis_name}'"}
        return handler(params)

    def available_analyses(self) -> List[str]:
        return sorted(self._registry.keys())


def _handle_ttest(p):
    """Decode router ttest params (column1/column2/test_type) into Python service params."""
    from app.services.compare import ttest
    test_type = p.get("test_type", "independent")
    if test_type == "paired":
        return ttest(
            _state.current_data,
            dependent=[p.get("column1"), p.get("column2")],
            group=None, paired=True,
        )
    elif test_type == "independent":
        return ttest(
            _state.current_data,
            dependent=[p.get("column1")],
            group=p.get("column2"), paired=False,
        )
    else:
        return ttest(
            _state.current_data,
            dependent=[p.get("column1")],
            group=None, paired=False,
        )


def _build_registry() -> Dict[str, callable]:
    from app.services.descriptive import (
        descriptive_stats, frequencies, crosstab, explore, means,
    )
    from app.services.compare import (
        ttest, mannwhitney, wilcoxon, anova_oneway, kruskal_wallis, chisquare, anova_twoway,
    )
    from app.services.regression import (
        correlation_matrix, linear_regression, logistic_regression, partial_correlation,
    )
    from app.services.survival import kaplan_meier, cox_regression
    from app.services.diagnostic import diagnostic_test, roc_analysis
    from app.services.factor_analysis import factor_analysis, reliability_analysis

    return {
        # ── Descriptive ────────────────────────────────────────────────
        "descriptive": lambda p: descriptive_stats(
            _state.current_data, p.get("columns", []), p.get("group_col"),
        ),
        "frequencies": lambda p: frequencies(_state.current_data, p["column"]),
        "crosstab": lambda p: crosstab(_state.current_data, p["row"], p["col"]),
        "explore": lambda p: explore(
            _state.current_data, p.get("column"), p.get("group_col"),
        ),
        "means": lambda p: means(
            _state.current_data, p.get("dependent"), p.get("group"), p.get("layers"),
        ),

        # ── Group comparisons ──────────────────────────────────────────
        "ttest": _handle_ttest,
        "mannwhitney": lambda p: mannwhitney(
            _state.current_data, p.get("column"), p.get("group_var"),
        ),
        "wilcoxon": lambda p: wilcoxon(
            _state.current_data, p.get("column1"), p.get("column2"),
        ),
        "anova": lambda p: anova_oneway(
            _state.current_data, p.get("dv"), p.get("between"),
        ),
        "anova_twoway": lambda p: anova_twoway(
            _state.current_data, p.get("dv"), p.get("factor1"), p.get("factor2"),
        ),
        "kruskal_wallis": lambda p: kruskal_wallis(
            _state.current_data, p.get("column"), p.get("group_var"),
        ),
        "chisquare": lambda p: chisquare(
            _state.current_data, p.get("row"), p.get("col"),
        ),

        # ── Regression ─────────────────────────────────────────────────
        "correlation": lambda p: correlation_matrix(
            _state.current_data,
            p.get("columns", []),
            p.get("method", "pearson"),
        ),
        "partial_correlation": lambda p: partial_correlation(
            _state.current_data,
            p.get("columns", []),
            p.get("control", []),
            p.get("method", "pearson"),
        ),
        "linear_regression": lambda p: linear_regression(
            _state.current_data,
            p.get("dv"),
            p.get("predictors", []),
        ),
        "logistic_regression": lambda p: logistic_regression(
            _state.current_data,
            p.get("dv"),
            p.get("predictors", []),
        ),

        # ── Survival ───────────────────────────────────────────────────
        "kaplan_meier": lambda p: _wrap_km(kaplan_meier(
            _state.current_data,
            p.get("time_col"),
            p.get("status_col"),
            p.get("event_code", 1),
            p.get("group_col"),
        )),
        "cox_regression": lambda p: cox_regression(
            _state.current_data,
            p.get("time_col"),
            p.get("status_col"),
            p.get("covariates", []),
            p.get("event_code", 1),
        ),

        # ── Diagnostic ─────────────────────────────────────────────────
        "diagnostic": lambda p: diagnostic_test(
            _state.current_data,
            p.get("test_col"),
            p.get("gold_col"),
            p.get("positive_code", 1),
        ),
        "roc_analysis": lambda p: roc_analysis(
            _state.current_data,
            p.get("test_col"),
            p.get("gold_col"),
            p.get("positive_code", 1),
        ),

        # ── Factor / Reliability ───────────────────────────────────────
        "factor_analysis": lambda p: factor_analysis(
            _state.current_data,
            p.get("columns", []),
            p.get("n_factors", 2),
            p.get("rotation", "varimax"),
        ),
        "reliability": lambda p: reliability_analysis(
            _state.current_data, p.get("columns", []),
        ),

        # ── Cluster ────────────────────────────────────────────────────
        "cluster_analysis": lambda p: _cluster_analysis(
            _state.current_data,
            p.get("columns", []),
            p.get("n_clusters", 3),
            p.get("method", "kmeans"),
        ),

        # ── Power ─────────────────────────────────────────────────────
        "power_analysis": lambda p: _power_analysis(
            p.get("test", "ttest"),
            p.get("effect_size", 0.5),
            p.get("alpha", 0.05),
            p.get("power", 0.8),
            p.get("k", 2),
        ),

        # ── Mixed model ───────────────────────────────────────────────
        "mixed_model": lambda p: _mixed_model(
            _state.current_data,
            p.get("dv"),
            p.get("fixed", []),
            p.get("random"),
            p.get("random"),
        ),
    }


# ── Output format helpers ─────────────────────────────────────────────────


def _wrap_km(result):
    """Rename km_curve → series for frontend compatibility, add chisq/p_value at top level."""
    if "error" in result:
        return result
    series = result.pop("km_curve", [])
    result["series"] = series
    lr = result.get("log_rank_test")
    if lr:
        result["chisq"] = lr.get("statistic")
        result["p_value"] = lr.get("p")
    result["chart_type"] = "km_curve"
    return result


# ── Cluster analysis ──────────────────────────────────────────────────────


def _cluster_analysis(
    df, columns: List[str], n_clusters: int = 3, method: str = "kmeans",
) -> Dict[str, Any]:
    from sklearn.cluster import KMeans, AgglomerativeClustering
    from sklearn.preprocessing import StandardScaler
    import numpy as np

    for col in columns:
        if col not in df.columns:
            return {"error": f"Column '{col}' not found."}
    data = df[columns].dropna()
    n = len(data)
    if n < n_clusters:
        return {"error": "Fewer observations than clusters requested."}
    X = data.values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    if method == "kmeans":
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    elif method == "hierarchical":
        model = AgglomerativeClustering(n_clusters=n_clusters)
    else:
        return {"error": f"Unknown clustering method: '{method}'"}
    labels = model.fit_predict(X_scaled)
    centers = scaler.inverse_transform(model.cluster_centers_) if hasattr(model, "cluster_centers_") else None
    cluster_sizes = {int(i): int((labels == i).sum()) for i in range(n_clusters)}
    inertia = float(model.inertia_) if hasattr(model, "inertia_") else None
    silhouette = None
    if n > n_clusters and n_clusters > 1:
        from sklearn.metrics import silhouette_score
        try:
            silhouette = round(float(silhouette_score(X_scaled, labels)), 4)
        except Exception:
            pass
    result = {
        "method": method,
        "n_clusters": n_clusters,
        "n_observations": n,
        "n_variables": len(columns),
        "cluster_sizes": cluster_sizes,
        "silhouette_score": silhouette,
        "inertia": round(inertia, 4) if inertia is not None else None,
        "columns": columns,
    }
    if centers is not None:
        result["cluster_centers"] = [
            {columns[j]: round(float(centers[i, j]), 4) for j in range(len(columns))}
            for i in range(n_clusters)
        ]
    result["interpretation"] = _interpret_cluster(result)
    return result


def _interpret_cluster(result: Dict[str, Any]) -> str:
    parts = [
        f"A {result['method']} cluster analysis was performed on "
        f"{result['n_observations']} observations with {result['n_variables']} variables, "
        f"producing {result['n_clusters']} clusters. "
    ]
    sizes = result.get("cluster_sizes", {})
    parts.append("Cluster sizes: " + ", ".join(f"Cluster {k}: n={v}" for k, v in sizes.items()) + ". ")
    sil = result.get("silhouette_score")
    if sil is not None:
        parts.append(
            f"The silhouette score is {sil:.3f}, "
            f"{'indicating well-separated clusters' if sil >= 0.5 else 'suggesting moderate overlap' if sil >= 0.25 else 'suggesting weak cluster structure'}. "
        )
    return "".join(parts)


# ── Power analysis ────────────────────────────────────────────────────────


def _power_analysis(
    test: str = "ttest",
    effect_size: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.8,
    n_groups: int = 2,
) -> Dict[str, Any]:
    from statsmodels.stats.power import TTestPower, TTestIndPower, FTestAnovaPower
    import numpy as np

    if test == "ttest":
        solver = TTestPower()
        n = solver.solve_power(effect_size=effect_size, alpha=alpha, power=power, alternative="two-sided")
        n_per_group = int(np.ceil(n))
        return {
            "test": "Independent t-test (two-sided)",
            "effect_size": effect_size,
            "effect_size_measure": "Cohen's d",
            "alpha": alpha,
            "power": power,
            "n_total": n_per_group,
            "n_per_group": n_per_group,
            "interpretation": f"Required total sample size: {n_per_group} ({n_per_group // 2} per group for equal groups).",
        }
    elif test == "ttest_paired":
        solver = TTestPower()
        n = solver.solve_power(effect_size=effect_size, alpha=alpha, power=power, alternative="two-sided")
        n_pairs = int(np.ceil(n))
        return {
            "test": "Paired t-test (two-sided)",
            "effect_size": effect_size,
            "effect_size_measure": "Cohen's dz",
            "alpha": alpha,
            "power": power,
            "n_pairs": n_pairs,
            "interpretation": f"Required number of pairs: {n_pairs}.",
        }
    elif test == "anova":
        solver = FTestAnovaPower()
        n_total = solver.solve_power(effect_size=effect_size, alpha=alpha, power=power, k_groups=n_groups)
        n_total = int(np.ceil(n_total))
        return {
            "test": f"One-way ANOVA ({n_groups} groups)",
            "effect_size": effect_size,
            "effect_size_measure": "Cohen's f",
            "alpha": alpha,
            "power": power,
            "n_groups": n_groups,
            "n_total": n_total,
            "n_per_group": int(np.ceil(n_total / n_groups)),
            "interpretation": f"Required total sample size: {n_total} (~{int(np.ceil(n_total / n_groups))} per group).",
        }
    return {"error": f"Unknown power test: '{test}'"}


# ── Mixed model ───────────────────────────────────────────────────────────


def _mixed_model(
    df, dependent: str, fixed: List[str], random: str, subject: str,
) -> Dict[str, Any]:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    import numpy as np

    all_cols = [dependent] + fixed + [random, subject]
    for col in all_cols:
        if col not in df.columns:
            return {"error": f"Column '{col}' not found."}
    data = df[all_cols].dropna()
    n = len(data)
    if n < 5:
        return {"error": "Insufficient data (need at least 5 complete cases)."}
    fixed_terms = " + ".join(f"Q('{v}')" for v in fixed)
    formula = f"Q('{dependent}') ~ {fixed_terms} + Q('{random}')"
    try:
        model = smf.mixedlm(formula, data, groups=data[subject]).fit()
    except Exception as e:
        return {"error": f"Mixed model failed to fit: {e}"}
    coeffs = []
    for var in model.params.index:
        coeffs.append({
            "name": var,
            "coef": round(float(model.params[var]), 4),
            "se": round(float(model.bse[var]), 4) if var in model.bse else None,
            "z": round(float(model.tvalues[var]), 4) if var in model.tvalues else None,
            "p": round(float(model.pvalues[var]), 4) if var in model.pvalues else None,
        })
    random_effect_var = float(model.cov_re.iloc[0, 0]) if model.cov_re.size > 0 else 0.0
    residual_var = float(model.scale) if hasattr(model, "scale") else 0.0
    icc = random_effect_var / (random_effect_var + residual_var) if (random_effect_var + residual_var) > 0 else 0.0
    return {
        "test_name": "Mixed Effects Model",
        "dependent": dependent,
        "fixed_effects": fixed,
        "random_effect": random,
        "subject": subject,
        "n": n,
        "n_groups": int(data[subject].nunique()),
        "coefficients": coeffs,
        "random_effect_variance": round(random_effect_var, 4),
        "residual_variance": round(residual_var, 4),
        "icc": round(icc, 4),
        "log_likelihood": round(float(model.llf), 4) if hasattr(model, "llf") else None,
        "aic": round(float(model.aic), 4) if hasattr(model, "aic") else None,
        "bic": round(float(model.bic), 4) if hasattr(model, "bic") else None,
        "interpretation": _interpret_mixed_model(coeffs, icc, dependent, fixed),
    }


def _interpret_mixed_model(
    coefficients: List[Dict], icc: float, dependent: str, fixed: List[str],
) -> str:
    parts = [
        f"A mixed effects model was fitted with '{dependent}' as the outcome "
        f"and {', '.join(fixed)} as fixed effects. "
    ]
    parts.append(f"The intraclass correlation coefficient (ICC) is {icc:.4f}, "
                 f"indicating that {icc * 100:.1f}% of the variance is attributable to between-subject differences. ")
    sig_vars = [c for c in coefficients if c.get("p", 1) < 0.05 and c["name"] != "Intercept" and "Group" not in c["name"]]
    if sig_vars:
        parts.append("Significant fixed effects: ")
        for c in sig_vars:
            parts.append(f"  {c['name']}: B = {c['coef']} (SE = {c['se']}), z = {c['z']}, p = {c['p']}. ")
    else:
        parts.append("No fixed effects reached statistical significance (p < 0.05). ")
    return "".join(parts)
