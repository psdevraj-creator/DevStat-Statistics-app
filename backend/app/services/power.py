from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats as _st
from statsmodels.stats.power import TTestIndPower, TTestPower, FTestPower, GofChisquarePower


def _scalar(v):
    """Coerce a statsmodels result (scalar or 1-element numpy array) to float."""
    try:
        return float(np.asarray(v).reshape(-1)[0])
    except Exception:
        return float(v)


def power_analysis(test: str, effect_size: float | None = None,
                   n: int | None = None, power: float | None = None,
                   alpha: float = 0.05, k: int | None = None,
                   ratio: float = 1.0) -> dict[str, Any]:
    """Compute power, sample size, or effect size for common tests.

    Parameters
    ----------
    test : str
        One of 'ttest', 'ttest_paired', 'anova', 'chisquare'.
    effect_size : float, optional
        Cohen's d (t-test), f (ANOVA), or w (chi-square).
    n : int, optional
        Total sample size (t-test, chi-square) or per-group mean N (ANOVA).
    power : float, optional
        Desired statistical power (0-1).
    alpha : float
        Significance level (default 0.05).
    k : int, optional
        Number of groups (ANOVA) or degrees of freedom (chi-square).
    ratio : float
        Allocation ratio n2/n1 for independent t-test (default 1.0).

    Returns
    -------
    dict with computed parameter and interpretation.
    """
    vals = {'effect_size': effect_size, 'n': n, 'power': power}
    given = [k for k in ('effect_size', 'n', 'power') if vals[k] is not None]
    missing = [k for k in ('effect_size', 'n', 'power') if vals[k] is None]
    if not given:
        return {'error': 'Specify at least one of: effect_size, n, or power'}
    # The value being solved for is the MISSING one (e.g. n from effect+power).
    param = missing[0] if missing else 'effect_size'

    if test == 'ttest':
        solver = TTestIndPower()
        if n is None and power is not None:
            computed = solver.solve_power(effect_size=effect_size, alpha=alpha, power=power, ratio=ratio, nobs1=None)
        elif power is None and n is not None:
            computed = solver.power(effect_size=effect_size, nobs1=n, alpha=alpha, ratio=ratio)
        else:
            computed = solver.solve_power(nobs1=n, alpha=alpha, power=power, ratio=ratio, effect_size=None)
        computed = _scalar(computed)
        interpretation = _interpret_power(test, computed, param, effect_size, n, power, alpha)

    elif test == 'ttest_paired':
        solver = TTestPower()
        if n is None and power is not None:
            computed = solver.solve_power(effect_size=effect_size, alpha=alpha, power=power, nobs=None)
        elif power is None and n is not None:
            computed = solver.power(effect_size=effect_size, nobs=n, alpha=alpha)
        else:
            computed = solver.solve_power(nobs=n, alpha=alpha, power=power, effect_size=None)
        computed = _scalar(computed)
        interpretation = _interpret_power(test, computed, param, effect_size, n, power, alpha)

    elif test == 'anova':
        if not k:
            return {'error': 'Number of groups (k) is required for ANOVA power'}
        solver = FTestPower()
        if param == 'power':
            computed = solver.power(effect_size=effect_size, df_num=k - 1, df_denom=n - k, alpha=alpha)
        elif param == 'n':
            computed = solver.solve_power(effect_size=effect_size, power=power, alpha=alpha, df_num=k - 1, df_denom=None)
        else:
            computed = solver.solve_power(power=power, alpha=alpha, df_num=k - 1, df_denom=None)
        computed = _scalar(computed)
        interpretation = _interpret_power(test, computed, param, effect_size, n, power, alpha, k)

    elif test == 'chisquare':
        if not k:
            return {'error': 'Degrees of freedom (k) is required for chi-square power'}
        solver = GofChisquarePower()
        if param == 'power':
            computed = solver.power(effect_size=effect_size, nobs=n, alpha=alpha, df=k)
        elif param == 'n':
            computed = solver.solve_power(effect_size=effect_size, power=power, alpha=alpha, df=k)
        else:
            computed = solver.solve_power(power=power, alpha=alpha, df=k)
        computed = _scalar(computed)
        interpretation = _interpret_power(test, computed, param, effect_size, n, power, alpha, k)

    elif test in ('correlation', 'r'):
        # Pearson correlation power via Fisher-z approximation.
        import math
        r = effect_size or 0.0
        z_a = _st.norm.ppf(1 - alpha / 2)
        z_b = _st.norm.ppf(power) if power is not None else _st.norm.ppf(0.8)
        atanh_r = math.atanh(abs(r)) if abs(r) < 1 else 0.0
        if param == 'n':
            computed = ((z_a + z_b) / atanh_r) ** 2 + 3 if atanh_r > 0 else float('nan')
        elif param == 'power':
            computed = _st.norm.cdf(atanh_r * math.sqrt(max(n - 3, 1)) - z_a)
        else:  # effect_size
            computed = math.tanh((z_a + z_b) / math.sqrt(max(n - 3, 1)))
        computed = _scalar(computed)
        interpretation = _interpret_power(test, computed, param, effect_size, n, power, alpha)

    else:
        return {'error': f"Unknown test type: {test}. Use 'ttest', 'ttest_paired', 'anova', or 'chisquare'."}

    result: dict[str, Any] = {
        'test': test,
        'parameter_type': param,
        'alpha': alpha,
        interpretation['label']: round(computed, 4),
        'interpretation': interpretation['text'],
    }
    if effect_size is not None:
        result['effect_size'] = effect_size
    if n is not None:
        result['n'] = n
    if power is not None:
        result['power'] = power
    if k is not None:
        result['k'] = k
    if ratio != 1.0:
        result['ratio'] = ratio

    return result


def _interpret_power(test: str, computed: float, param: str,
                     effect_size: float | None, n: int | None,
                     power: float | None, alpha: float,
                     k: int | None = None) -> dict[str, str]:
    test_labels = {'ttest': 'Independent t-test', 'ttest_paired': 'Paired t-test',
                   'anova': 'ANOVA', 'chisquare': 'Chi-square',
                   'correlation': 'Correlation', 'r': 'Correlation'}
    label = test_labels.get(test, test)
    param_label = {'effect_size': 'Effect size d', 'n': 'Sample size', 'power': 'Power'}

    if param == 'power':
        adequate = computed >= 0.8
        qual = 'adequate' if adequate else 'inadequate'
        return {
            'label': 'power',
            'text': f"For a {label} with α={alpha}, effect size d={effect_size}, N={n}: "
                    f"power = {computed:.3f} ({qual}). "
                    f"Recommended power is ≥0.80."
        }
    elif param == 'n':
        needed = int(math.ceil(computed))
        return {
            'label': 'n',
            'text': f"To detect effect size d={effect_size} with power={power} at α={alpha} "
                    f"for a {label}: need {needed} total observations."
        }
    else:
        q = 'large' if computed >= 0.8 else ('medium' if computed >= 0.5 else 'small')
        return {
            'label': 'effect_size',
            'text': f"With N={n} and power={power} at α={alpha} for a {label}: "
                    f"detectable effect size d = {computed:.3f} ({q})."
        }
