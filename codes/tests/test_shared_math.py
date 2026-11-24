"""Independent checks of the arithmetic used by multiple solver entry points."""
from fractions import Fraction
import itertools
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'codes'))
from tools.arithmetic import bound_clauses, polynomial_interval


class SharedArithmetic(unittest.TestCase):
    def test_unsigned_comparator_including_complemented_literals(self):
        # Bound search uses complemented bits to express lower bounds; zero
        # objectives and out-of-range queries are also actual consumers.
        for width in range(5):
            for complement in (False, True):
                bits = [(i + 1) * (-1 if complement else 1) for i in range(width)]
                for bound in range(-1, (1 << width) + 1):
                    clauses = bound_clauses(bits, bound)
                    for value in range(1 << width):
                        signed = {bits[i] if (value >> i) & 1 else -bits[i]
                                  for i in range(width)}
                        satisfied = all(any(lit in signed for lit in clause) for clause in clauses)
                        self.assertEqual(satisfied, value <= bound,
                                         (width, complement, bound, value))

    def test_integer_and_rational_polynomial_boxes(self):
        bounds = {'x': (-2, 3), 'y': (-3, -1)}
        cases = [
            [],
            [(1, {'x': 2})],
            [(-3, {'x': 2})],
            [(2, {'x': 0})],
            [(3, {'x': 3, 'y': 2})],
            [(Fraction(2, 3), {'x': 2, 'y': 1}),
             (Fraction(-5, 7), {'x': 1}), (Fraction(11, 13), {})],
        ]
        for terms in cases:
            lower, upper = polynomial_interval(terms, bounds)
            values = []
            for x, y in itertools.product(range(-2, 4), range(-3, 0)):
                assignment = {'x': x, 'y': y}
                value = sum(c * assignment.get('x', 0)**powers.get('x', 0)
                            * assignment.get('y', 0)**powers.get('y', 0)
                            for c, powers in terms)
                values.append(value)
                self.assertLessEqual(lower, value)
                self.assertLessEqual(value, upper)
            if len(terms) <= 1:
                self.assertEqual((lower, upper), (min(values), max(values)))


if __name__ == '__main__':
    unittest.main()
