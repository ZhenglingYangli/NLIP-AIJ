"""Check both DIMACS consumers against the original Boolean formula."""
import contextlib
import io
import itertools
from math import prod
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.cnf_parser import parse_cnf_file
from tools.diversesat_parser import parse_diversesat


def polynomial(terms, values):
    return sum(t['c'] * prod(values[n] ** p for n, p in t['vars'].items())
               for t in terms)


def feasible(problem, values):
    return all(polynomial(c['terms'], values) >= c['rhs'] for c in problem['constraints'])


def original_formula(bits):
    x1, x2, x3 = bits
    return (x1 or not x2) and (x2 or x3) and not x1


class DimacsConsumers(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'formula.cnf'
        self.path.write_text('c Three clauses, including a wrapped clause.\n'
                             'p cnf 3 3\n1 -2\n0 2 3 0\n-1 0\n', encoding='utf-8')

    def test_cnf_feasible_assignments(self):
        problem = parse_cnf_file(str(self.path))
        self.assertEqual(set(problem['variables']), {'x1', 'x2', 'x3'})
        for bits in itertools.product([0, 1], repeat=3):
            values = dict(zip(['x1', 'x2', 'x3'], bits))
            self.assertEqual(feasible(problem, values), original_formula(bits), bits)

    def test_diversesat_assignments_and_hamming_objective(self):
        with contextlib.redirect_stdout(io.StringIO()):
            problem = parse_diversesat(str(self.path), 2)
        for bits in itertools.product([0, 1], repeat=6):
            first, second = bits[:3], bits[3:]
            values = {f'x{i}_m{m}': value for m, model in [(1, first), (2, second)]
                      for i, value in enumerate(model, 1)}
            self.assertEqual(feasible(problem, values),
                             original_formula(first) and original_formula(second), bits)
            self.assertEqual(polynomial(problem['objective']['terms'], values),
                             sum(a != b for a, b in zip(first, second)), bits)


if __name__ == '__main__':
    unittest.main(verbosity=2)
