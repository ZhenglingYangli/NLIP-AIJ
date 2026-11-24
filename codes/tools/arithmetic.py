"""Exact arithmetic shared by direct-model experiment backends."""
from fractions import Fraction
from math import lcm






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


def number(x):
    return Fraction(str(x))


def integer_polynomial(terms):
    merged = {}
    for term in terms:
        key = tuple(sorted((n, int(k)) for n, k in term.get('vars', {}).items() if k))
        if any(k < 0 for _, k in key):
            raise ValueError('negative exponent outside polynomial scope')
        merged[key] = merged.get(key, Fraction(0)) + number(term.get('c', 1))
    merged = {key: c for key, c in merged.items() if c}
    scale = lcm(*(v.denominator for v in merged.values())) if merged else 1
    return {key: int(c * scale) for key, c in merged.items()}, scale


def exact_double_integer(value):
    if abs(value) > 2**53:
        raise ValueError('UNSUPPORTED_NUMERIC_RANGE: integer coefficient or bound exceeds 2^53')
    return int(value)


def integer_polynomial_interval(poly, bounds):
    """Evaluate normalized integer monomials using the shared interval rules."""
    return polynomial_interval(((c, dict(key)) for key, c in poly.items()), bounds)
