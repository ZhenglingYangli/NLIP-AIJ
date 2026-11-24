"""Regression checks for the remaining CPMpy PR #1127 feedback."""
import itertools
import os
import signal
import sys
import subprocess
import tempfile
from pathlib import Path
from test_correctness import ROOT, problem, term
from tools.smt2_parser import parse_smt2_file
import time
import unittest
from unittest.mock import patch
import test_correctness
from pysat.formula import WCNF
from nlipsat import EncodingConfig, solve
from solver.solve import _preprocess_wcnf, solve_rc2, EncodingTimeoutError
from tools.preprocessing import _bound_tightening


class CPMpyFeedback(unittest.TestCase):
    def test_bound_propagation_checks_deadline_inside_loop(self):
        variables = {str(i): {'lb': 0, 'ub': 10} for i in range(50)}
        terms = [{'c': 1, 'vars': {v: 1}} for v in variables]
        ticks = itertools.chain([0] * 8, itertools.repeat(2))
        with patch('tools.preprocessing.time.time', side_effect=lambda: next(ticks)):
            with self.assertRaises(EncodingTimeoutError):
                _bound_tightening([{'terms': terms, 'rel': '<=', 'rhs': 20}], variables, deadline=1)

    def test_wcnf_simplification_checks_deadline_inside_loop(self):
        w = WCNF()
        w.extend([[i, i+1] for i in range(1, 100)])
        ticks = itertools.chain([0] * 110, itertools.repeat(2))
        with patch('solver.solve.time.time', side_effect=lambda: next(ticks)):
            with self.assertRaises(EncodingTimeoutError):
                _preprocess_wcnf(w, EncodingConfig(encoding_deadline=1))

    def test_rc2_bounded_sat_unsat_and_timeout(self):
        w = WCNF(); w.append([1]); w.append([-1], weight=3)
        self.assertEqual(solve_rc2(w, timeout=5), (3, [1]))
        w.append([])
        self.assertEqual(solve_rc2(w, timeout=5), (-1, []))
        # Pigeonhole UNSAT requires native SAT search, unlike a startup-only test.
        w = WCNF(); n = 20
        for i in range(n):
            w.append([i*(n-1)+j+1 for j in range(n-1)])
        for j in range(n-1):
            for i in range(n):
                for k in range(i):
                    w.append([-(i*(n-1)+j+1), -(k*(n-1)+j+1)])
        import subprocess
        original = subprocess.Popen
        children = []
        def record(*args, **kwargs):
            child = original(*args, **kwargs); children.append(child); return child
        started = time.monotonic()
        with patch('solver.solve.subprocess.Popen', side_effect=record):
            self.assertEqual(solve_rc2(w, timeout=0.25), (-1, None))
        self.assertLess(time.monotonic()-started, 3)
        self.assertTrue(children)
        self.assertTrue(all(child.poll() is not None for child in children))

    def test_shift_expansion_checks_deadline(self):
        from tools.preprocessing import _expand_term_by_shifts
        ticks = itertools.chain([0] * 8, itertools.repeat(2))
        with patch('tools.preprocessing.time.time', side_effect=lambda: next(ticks)):
            with self.assertRaises(EncodingTimeoutError):
                _expand_term_by_shifts({'c': 1, 'vars': {'x': 50}}, {'x': 1}, deadline=1)

    def test_domain_generation_checks_deadline(self):
        from encoders.encoder_driver import add_domain_constraints
        from pysat.formula import IDPool
        p = test_correctness.problem({'x': (0, 100)}, [])
        for enc in ['OH', 'UNA', 'BIN']:
            ticks = itertools.chain([0] * 3, itertools.repeat(2))
            with self.subTest(encoding=enc), patch('encoders.onehot.time.time', side_effect=lambda: next(ticks)):
                with self.assertRaises(EncodingTimeoutError):
                    add_domain_constraints(p, enc, {'x': 1}, IDPool(), WCNF(), EncodingConfig(encoding_deadline=1))

    def test_binary_objective_fast_path_checks_deadline(self):
        from encoders.encoder_driver import encode_objective
        from pysat.formula import IDPool
        p = test_correctness.problem({'x': (0, 1)}, [test_correctness.term(1, x=1)] * 50)
        ticks = itertools.chain([0] * 8, itertools.repeat(2))
        with patch('encoders.onehot.time.time', side_effect=lambda: next(ticks)):
            with self.assertRaises(EncodingTimeoutError):
                encode_objective(p, 'BIN', {'x': 1}, IDPool(), EncodingConfig(encoding_deadline=1))

    def test_rc2_serialization_consumes_timeout_budget(self):
        w = WCNF(); w.append([1])
        with patch('solver.solve.time.monotonic', side_effect=[0, 2]), patch('solver.solve.subprocess.run') as run:
            self.assertEqual(solve_rc2(w, timeout=1), (-1, None))
            run.assert_not_called()

    def test_external_unknown_is_not_a_timeout(self):
        import subprocess
        import tempfile
        from solver.solve import solve_external
        w = WCNF(); w.append([1, 2])
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.CompletedProcess([], 0, 's UNKNOWN\n', '')
            with patch('solver.solve.subprocess.run', return_value=result):
                self.assertEqual(solve_external(w, directory, 'maxhs', timeout=5)[2], 'UNKNOWN')
            with patch('solver.solve.subprocess.run', side_effect=subprocess.TimeoutExpired('maxhs', 5)):
                self.assertEqual(solve_external(w, directory, 'maxhs', timeout=5)[2], 'TIMEOUT')

    def test_external_serialization_and_fractional_budget(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from solver.solve import solve_external
        w = WCNF(); w.append([1])
        with tempfile.TemporaryDirectory() as directory:
            with patch('solver.solve.time.monotonic', side_effect=[0, 2]), patch('solver.solve.subprocess.run') as run:
                self.assertEqual(solve_external(w, directory, 'maxhs', timeout=1)[2], 'TIMEOUT')
                run.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])
            with patch('solver.solve.time.monotonic', side_effect=[0, 0.05]), patch('solver.solve.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 's UNKNOWN\n', '')) as run:
                solve_external(w, directory, 'maxhs', timeout=0.2)
                self.assertAlmostEqual(run.call_args.kwargs['timeout'], 0.15)
                self.assertFalse(any(arg.startswith('-cpu-lim=') for arg in run.call_args.args[0]))

    def test_public_api_distinguishes_timeout_from_unsat(self):
        p = test_correctness.problem({'x': (0, 2)}, [test_correctness.term(1, x=1)])
        result = solve(p, config=EncodingConfig(rc2_timeout=0.000001))
        self.assertEqual(result['solver_status'], 'TIMEOUT')
        self.assertIsNone(result['assignment'])
        self.assertIsNone(result['objective_value'])
        result = solve(p, config=EncodingConfig(rc2_timeout=5))
        self.assertEqual(result['solver_status'], 'OPTIMAL')
        self.assertTrue(result['verified'])


    def test_rc2_released_on_solver_exception(self):
        from pysat.formula import WCNF
        with patch('solver.solve.RC2') as constructor:
            instance = constructor.return_value
            instance.compute.side_effect = RuntimeError('test interruption')
            with self.assertRaises(RuntimeError):
                solve_rc2(WCNF())
            instance.delete.assert_called_once()


    def test_cli_timeout_reaps_external_solver(self):
        with tempfile.TemporaryDirectory() as d:
            executable, pid_file = Path(d) / 'maxhs', Path(d) / 'pid'
            executable.write_text(f'#!{sys.executable}\nimport os,time\nfrom pathlib import Path\nPath(os.environ["TEST_SOLVER_PID"]).write_text(str(os.getpid()))\ntime.sleep(30)\n')
            executable.chmod(0o700)
            env = {**os.environ, 'NLIP_MAXHS': str(executable), 'TEST_SOLVER_PID': str(pid_file)}
            pid = None
            try:
                r = subprocess.run([sys.executable, str(ROOT / 'main.py'),
                                    str(ROOT / 'examples/example4.json'), '-s', 'MAXHS', '--timeout', '1'],
                                   env=env, capture_output=True, text=True, timeout=5)
                self.assertIn('Status TIMEOUT', r.stdout)
                pid = int(pid_file.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                if pid is None and pid_file.exists():
                    pid = int(pid_file.read_text())
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


    def test_runtime_timeout_is_not_a_mathematical_error(self):
        from pysat.formula import WCNF
        from tools.verify import verify_solution
        with patch('solver.solve.RC2') as constructor:
            constructor.return_value.compute.side_effect = TimeoutError('runtime deadline')
            with self.assertRaises(TimeoutError):
                solve_rc2(WCNF())
            constructor.return_value.delete.assert_called_once()
        p = problem({'x': (0, 1)}, [term(1, x=1)])
        result = solve(p)
        with patch('tools.verify.verify_values', side_effect=TimeoutError('runtime deadline')):
            with self.assertRaises(TimeoutError):
                verify_solution(p, result, 'BIN')
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'timeout.smt2'
            f.write_text('(assert true)')
            with patch('z3.parse_smt2_file', side_effect=TimeoutError('runtime deadline')):
                with self.assertRaises(TimeoutError):
                    parse_smt2_file(str(f))


if __name__ == '__main__':
    unittest.main()
