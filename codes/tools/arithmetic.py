"""Exact arithmetic shared by the compiler and experimental bound queries."""
from fractions import Fraction
from operator import index


def bound_clauses(bits, bound):
    """Encode an unsigned little-endian literal vector <= an integer bound.

    Literals may be negated. No auxiliary variables are introduced; an empty
    vector denotes zero, so a negative bound produces the empty clause.
    """
    bound = index(bound)
    if bound < 0:
        return [[]]
    if bound >= (1 << len(bits)) - 1:
        return []
    return [[-bits[i]] + [-bits[j] for j in range(i + 1, len(bits))
                          if (bound >> j) & 1]
            for i in range(len(bits)) if not (bound >> i) & 1]


def cost_recovery(formula):
    """Return exact alpha, beta for original_objective = alpha * MaxSAT_cost + beta."""
    meta = (formula._preprocess_meta or {}).get('objective', {})
    scale = Fraction(formula._weight_gcd) * Fraction(meta.get('scale_gcd', 1),
                                                     meta.get('scale_lcm', 1))
    alpha = -scale
    beta = (sum(formula.wght) - getattr(formula, '_neg_soft_total', 0)) * scale
    beta += meta.get('constant_shift', 0)
    if meta.get('sense_flip', False):
        alpha, beta = -alpha, -beta
    return alpha, beta


def polynomial_interval(terms, bounds):
    """Enclose a polynomial on an integer box using exact term intervals.

    ``terms`` contains (coefficient, variable-to-power mapping) pairs. Integer
    coefficients stay integer; rational coefficients retain exact Fractions.
    ``bounds`` contains the inclusive integer bounds of each source variable.
    Powers are nonnegative integers, as required by the polynomial interfaces.
    """
    lower = upper = 0
    for coefficient, powers in terms:
        lo = hi = 1
        for name, power in powers.items():
            a, b = bounds[name]
            endpoints = [a**power, b**power]
            if power and power % 2 == 0 and a <= 0 <= b:
                endpoints.append(0)
            products = [lo * min(endpoints), lo * max(endpoints),
                        hi * min(endpoints), hi * max(endpoints)]
            lo, hi = min(products), max(products)
        lower += min(coefficient * lo, coefficient * hi)
        upper += max(coefficient * lo, coefficient * hi)
    return lower, upper
