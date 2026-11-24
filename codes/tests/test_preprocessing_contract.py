"""Original-domain checks for arithmetic and formula simplification."""
import copy
from fractions import Fraction
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'codes'))
from pysat.formula import WCNF
from solver.solve import _preprocess_wcnf
from tools.preprocessing import _bound_tightening, _probe_binary_variables


class PreprocessingContract(unittest.TestCase):
    def test_sequential_sum_updates(self):
        variables = {'x': {'lb': 0, 'ub': 10}, 'y': {'lb': 2, 'ub': 10},
                     'z': {'lb': 3, 'ub': 10}}
        constraint = {'terms': [{'c': 1, 'vars': {v: 1}} for v in variables],
                      'rel': '=', 'rhs': 10}
        _bound_tightening([constraint], variables, max_rounds=1)
        self.assertEqual([variables[v]['ub'] for v in variables], [5, 7, 8])

    def test_signed_fractional_bounds_keep_every_feasible_point(self):
        domains = {'x': {'lb': -3, 'ub': 4}, 'y': {'lb': -2, 'ub': 5}}
        comparisons = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
                       '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
                       '=': lambda a, b: a == b}
        for a, b, rhs, rel in itertools.product(
                [Fraction(-3, 2), Fraction(2, 3)], [Fraction(-2), Fraction(5, 2)],
                [Fraction(-1, 3), Fraction(0), Fraction(7, 2)], comparisons):
            variables = copy.deepcopy(domains)
            _bound_tightening([{'terms': [{'c': a, 'vars': {'x': 1}},
                                          {'c': b, 'vars': {'y': 1}}],
                                'rel': rel, 'rhs': rhs}], variables)
            for x, y in itertools.product(range(-3, 5), range(-2, 6)):
                if comparisons[rel](a*x+b*y, rhs):
                    self.assertTrue(variables['x']['lb'] <= x <= variables['x']['ub'])
                    self.assertTrue(variables['y']['lb'] <= y <= variables['y']['ub'])

    def test_nonlinear_constraints_are_not_partially_propagated(self):
        variables = {'x': {'lb': 0, 'ub': 2}, 'y': {'lb': 0, 'ub': 2}}
        original = copy.deepcopy(variables)
        constraint = {'terms': [{'c': 1, 'vars': {'x': 1}},
                                 {'c': 1, 'vars': {'y': 1}},
                                 {'c': -1, 'vars': {'x': 1, 'y': 1}}],
                      'rel': '<=', 'rhs': 0}
        _bound_tightening([constraint], variables)
        self.assertEqual(variables, original)

    def test_shared_product_fixing_preserves_original_optimum(self):
        variables = {'x': {'lb': 0, 'ub': 1}, 'y': {'lb': 0, 'ub': 1},
                     'z': {'lb': 0, 'ub': 4}}
        for cx, cy, cxy in itertools.product([-5, 0, 5], repeat=3):
            terms = [{'c': cx, 'vars': {'x': 1}}, {'c': cy, 'vars': {'y': 1}},
                     {'c': cxy, 'vars': {'x': 2, 'y': 1, 'z': 3}}]
            fixed = _probe_binary_variables(terms, variables, [])
            all_values, retained = [], []
            for x, y, z in itertools.product(range(2), range(2), range(5)):
                values = dict(x=x, y=y, z=z)
                objective = cx*x+cy*y+cxy*x*x*y*z**3
                all_values.append(objective)
                if all(values[n] == v for n, v in fixed.items()):
                    retained.append(objective)
            self.assertEqual(max(all_values), max(retained))
        constraints = [{'terms': [{'c': 1, 'vars': {'x': 1}}], 'rel': '<=', 'rhs': 1}]
        self.assertNotIn('x', _probe_binary_variables([{'c': 5, 'vars': {'x': 1}}], variables, constraints))

    def test_formula_simplification_preserves_models_and_soft_cost(self):
        cases = [
            [[1, 2], [1, 2, 3], [1, -2], [1, -2, 3], [-1, 3]],
            [[1], [2], [-1, -2]],
            [[], [1, 2]],
            [[1, -1], [2, 3], [2, 3], [-2, 3]],
        ]
        for hard in cases:
            formula = WCNF()
            formula.extend(hard)
            formula.append([1], weight=3)
            formula.append([-2, 3], weight=5)
            original = copy.deepcopy(formula)
            _preprocess_wcnf(formula)
            self.assertEqual((formula.soft, formula.wght), (original.soft, original.wght))
            for bits in itertools.product([False, True], repeat=3):
                def satisfied(clauses):
                    return all(any(bits[abs(l)-1] == (l > 0) for l in c) for c in clauses)
                self.assertEqual(satisfied(original.hard), satisfied(formula.hard))


if __name__ == '__main__':
    unittest.main()
