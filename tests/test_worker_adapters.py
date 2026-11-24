"""Check explicit phase callbacks and the worker's original-problem witnesses."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'codes')]
HAS_PYSAT = importlib.util.find_spec('pysat') is not None
HAS_Z3 = importlib.util.find_spec('z3') is not None
HAS_PSUTIL = importlib.util.find_spec('psutil') is not None


def linear_problem():
    return {'variables': {'x': {'lb': 0, 'ub': 2}}, 'constraints': [],
            'objective': {'sense': 'max', 'terms': [{'c': 1, 'vars': {'x': 1}}]}}


@unittest.skipUnless(HAS_PYSAT, 'requires the project PySAT runtime')
class CoreCallbacks(unittest.TestCase):
    def test_callbacks_preserve_result_with_and_without_timings(self):
        from solver.config import EncodingConfig
        from solver.solve import build_and_solve
        for timings in (False, True):
            with self.subTest(timings=timings), contextlib.redirect_stdout(io.StringIO()):
                reference = build_and_solve(linear_problem(), 'BIN', EncodingConfig(),
                                            collect_timings=timings)
                events = []

                def built(wcnf, values):
                    self.assertGreater(wcnf.nv, 0)
                    self.assertEqual(bool(values), timings)
                    events.append('built')

                result = build_and_solve(linear_problem(), 'BIN', EncodingConfig(),
                                         collect_timings=timings, on_built=built,
                                         on_verify=lambda: events.append('verify'))
                self.assertEqual(events, ['built', 'verify'])
                for key in ('solver_status', 'objective_value_exact', 'verified', 'assignment'):
                    self.assertEqual(result[key], reference[key])
                self.assertEqual(result['objective_value_exact'], '2')
                self.assertEqual(result['verification']['var_values'], {'x': 2})

    def test_unsat_does_not_start_verification(self):
        from solver.config import EncodingConfig
        from solver.solve import build_and_solve
        problem = linear_problem()
        problem['constraints'] = [{'terms': [{'c': 1, 'vars': {'x': 1}}], 'rel': '>=', 'rhs': 3}]
        events = []
        with contextlib.redirect_stdout(io.StringIO()):
            result = build_and_solve(problem, 'BIN', EncodingConfig(),
                                     on_built=lambda *_: events.append('built'),
                                     on_verify=lambda: events.append('verify'))
        self.assertEqual(result['solver_status'], 'UNSAT')
        self.assertEqual(events, ['built'])


@unittest.skipUnless(HAS_Z3, 'requires the project Z3 runtime')
class Z3Callbacks(unittest.TestCase):
    def setUp(self):
        from baselines import run_z3
        self.baseline = run_z3
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'bounded.smt2'
        self.path.write_text('(set-logic QF_LIA)\n(declare-fun x () Int)\n(assert (= x 2))\n',
                             encoding='utf-8')

    def test_qplib_uses_explicit_verify_callback_without_extra_output(self):
        events = []
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.baseline.solve_qplib(
                linear_problem(), 10, progress=lambda phase, **_: events.append(phase),
                on_verify=lambda: events.append('verify'))
            reference = self.baseline.solve_qplib(linear_problem(), 10)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(events[-1], 'verify')
        self.assertIn('solve', events[:-1])
        for key in ('status', 'objective', 'verified', 'witness'):
            self.assertEqual(result[key], reference[key])
        self.assertTrue(result['verified'])
        self.assertEqual(result['witness'], {'x': 2})

    def test_smt_fallback_accumulates_reads_and_returns_verified_witness(self):
        import z3
        first = z3.Solver()
        events = []
        with patch.object(first, 'check', return_value=z3.unknown), \
                patch.object(self.baseline, 'SolverFor', return_value=first):
            result = self.baseline.solve_smt2(
                str(self.path), 10,
                progress=lambda phase, **values: events.append((phase, values)),
                on_verify=lambda: events.append(('verify', {})))
        self.assertEqual(result['status'], 'SAT')
        self.assertTrue(result['verified'])
        self.assertIn('(define-fun x', result['witness']['model_sexpr'])
        self.assertEqual([phase for phase, _ in events], ['parse', 'solve', 'parse', 'solve', 'verify'])
        reads = [values['read_seconds'] for phase, values in events if phase == 'solve']
        self.assertGreaterEqual(reads[1], reads[0])
        self.assertGreaterEqual(result['time_verify'], 0)

    def test_unsat_has_no_witness_or_verification_phase(self):
        self.path.write_text('(set-logic QF_LIA)\n(assert false)\n', encoding='utf-8')
        events = []
        result = self.baseline.solve_smt2(str(self.path), 10,
                                           on_verify=lambda: events.append('verify'))
        self.assertEqual(result['status'], 'UNSAT')
        self.assertFalse(result.get('verified', False))
        self.assertNotIn('witness', result)
        self.assertEqual(events, [])

    def test_smt_verification_has_its_own_timing_and_starts_before_model_access(self):
        import z3
        solver = z3.Solver()
        original_model = solver.model
        clock = [100.0]
        verifying = []

        class TimedModel:
            def __init__(self, model):
                self.model = model

            def eval(self, *args, **kwargs):
                clock[0] += 5.0
                return self.model.eval(*args, **kwargs)

            def sexpr(self):
                clock[0] += 1.0
                return self.model.sexpr()

        def model():
            self.assertEqual(verifying, [True])
            return TimedModel(original_model())

        with patch.object(self.baseline, 'SolverFor', return_value=solver), \
                patch.object(solver, 'model', side_effect=model), \
                patch.object(self.baseline.time, 'perf_counter', side_effect=lambda: clock[0]):
            result = self.baseline.solve_smt2(str(self.path), 10,
                                               on_verify=lambda: verifying.append(True))
        self.assertTrue(result['verified'], result)
        self.assertEqual(result['time'], 0.0)
        self.assertEqual(result['time_verify'], 6.0)

    def test_smt_rejects_model_that_fails_original_assertions(self):
        import z3
        solver = z3.Solver()

        class InvalidModel:
            def eval(self, *args, **kwargs):
                return z3.BoolVal(False)

        with patch.object(self.baseline, 'SolverFor', return_value=solver), \
                patch.object(solver, 'model', return_value=InvalidModel()):
            result = self.baseline.solve_smt2(str(self.path), 10)
        self.assertFalse(result.get('verified', False))
        self.assertNotIn('witness', result)
        self.assertIn('original SMT witness verification failed', result['error_msg'])


@unittest.skipUnless(HAS_PYSAT and HAS_Z3 and HAS_PSUTIL and sys.platform == 'linux',
                     'requires the Linux project worker runtime')
class WorkerIntegration(unittest.TestCase):
    def test_existing_optimization_and_smt_routes_keep_phase_and_witness(self):
        import psutil
        cases = [('RC2', 'optimization'), ('Z3', 'optimization'),
                 ('Z3', 'decision'), ('CADICAL', 'decision')]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            polynomial = directory / 'problem.json'
            polynomial.write_text(json.dumps(linear_problem()), encoding='utf-8')
            smt = directory / 'bounded.smt2'
            smt.write_text('(set-logic QF_LIA)\n(declare-fun x () Int)\n'
                           '(assert (>= x 0))\n(assert (<= x 2))\n(assert (= x 2))\n',
                           encoding='utf-8')
            for solver, task in cases:
                with self.subTest(solver=solver, task=task):
                    method = {'solver': solver}
                    if solver in ('RC2', 'CADICAL'):
                        method.update(encoding='BIN', options={'use_lrn': False})
                    job = {'cpu': psutil.Process().cpu_affinity()[0],
                           'code_root': str(ROOT / 'codes'), 'method': method,
                           'task': task, 'family': 'smt' if task == 'decision' else 'qplib',
                           'input': str(smt if task == 'decision' else polynomial),
                           'solver_paths': {}, 'solve_seconds': 10}
                    job_file = directory / 'job.json'
                    job_file.write_text(json.dumps(job), encoding='utf-8')
                    run = subprocess.run([sys.executable, str(ROOT / 'jobs/internal/worker.py'),
                                          str(job_file)], text=True, capture_output=True, timeout=30)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                    lines = run.stdout.splitlines()
                    phases = [i for i, line in enumerate(lines) if line.startswith('AIJ_PHASE ')]
                    results = [(i, json.loads(line[len('AIJ_RESULT '):]))
                               for i, line in enumerate(lines) if line.startswith('AIJ_RESULT ')]
                    self.assertEqual(len(phases), 1, run.stdout)
                    self.assertEqual(len(results), 1, run.stdout)
                    result_index, result = results[0]
                    self.assertLess(phases[0], result_index)
                    self.assertTrue(result['verified'], result)
                    self.assertEqual(result['status'], 'SAT' if task == 'decision' else 'OPTIMAL')
                    self.assertTrue(result['witness'])
                    if task == 'optimization':
                        self.assertEqual(result['objective_exact'], '2')


if __name__ == '__main__':
    unittest.main()
