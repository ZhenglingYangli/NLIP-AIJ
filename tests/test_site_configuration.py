"""The small-test launcher must honor the actual site's Python selection."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'jobs'))
import goSolver
from internal import experiment


class SiteInterpreter(unittest.TestCase):
    def test_site_environment_is_used_without_planning(self):
        with tempfile.TemporaryDirectory(prefix='nlip site ') as temporary:
            jobs = Path(temporary) / 'jobs'
            jobs.mkdir()
            config = {'code_root': '../codes', 'python': '../.venv-solvers/bin/python',
                      'benchmark_root': '../benchmarks', 'manifest_root': '../manifests',
                      'solver_paths': {}, 'families': {}}
            (jobs / 'config.json').write_text(json.dumps(config))
            config['python'] = '../.venv/bin/python'
            (jobs / 'config.cluster.json').write_text(json.dumps(config))
            output = io.StringIO()
            with patch.object(experiment, 'ROOT', jobs), \
                 patch.object(sys, 'argv', ['goSolver.py', '--print-python']), \
                 patch.object(goSolver, 'make_jobs', side_effect=AssertionError('must not plan')), \
                 contextlib.redirect_stdout(output):
                goSolver.main()
            self.assertEqual(output.getvalue().strip(),
                             str(Path(temporary) / '.venv/bin/python'))

    def test_explicit_configuration_overrides_site_default(self):
        config_path = ROOT / 'jobs/config.json'
        expected = goSolver.load_config(config_path)['python']
        output = io.StringIO()
        with patch.object(sys, 'argv', ['goSolver.py', '--config', str(config_path), '--print-python']), \
             patch.object(goSolver, 'make_jobs', side_effect=AssertionError('must not plan')), \
             contextlib.redirect_stdout(output):
            goSolver.main()
        self.assertEqual(output.getvalue().strip(), expected)


    def test_explicit_missing_solver_does_not_fall_back(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('configure_cluster', ROOT / 'jobs/tools/configure_cluster.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.dict(os.environ, {'NLIP_MAXHS': '/missing/new-maxhs'}):
            with self.assertRaises(SystemExit):
                module.select('NLIP_MAXHS', ['/missing/new-maxhs', sys.executable], True)

    def test_reconfigure_uses_explicit_new_eval_helper(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('configure_cluster', ROOT / 'jobs/tools/configure_cluster.py')
        configure_cluster = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(configure_cluster)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / 'new-nuwls'
            helper.write_text('#!/bin/sh\nexit 0\n')
            helper.chmod(0o755)
            config = {'benchmark_root': str(root), 'solver_paths': {},
                      'families': {'mipo': {'input_root': str(root)}},
                      'external_solver_args': {'EVALMAXRES':
                          ['--noSimplify', '--path_anytime_solver', '/old/nuwls']}}
            (root / 'config.cluster.json').write_text(json.dumps(config))
            def resolve(label, candidates, executable=False):
                if label == 'NLIP_EVALMAXRES_HELPER':
                    return str(helper)
                return str(root)
            with patch.object(configure_cluster, 'ROOT', root), \
                 patch.object(configure_cluster, 'select', side_effect=resolve), \
                 patch.object(configure_cluster, 'load_config', side_effect=lambda p: json.loads(p.read_text())), \
                 patch.object(configure_cluster, 'make_jobs', return_value=[]), \
                 patch.dict(os.environ, {'NLIP_EVALMAXRES_HELPER': str(helper)}, clear=True), \
                 contextlib.redirect_stdout(io.StringIO()):
                configure_cluster.main()
            updated = json.loads((root / 'config.cluster.json').read_text())
            self.assertEqual(updated['external_solver_args']['EVALMAXRES'],
                             ['--noSimplify', '--path_anytime_solver', str(helper)])


if __name__ == '__main__':
    unittest.main()
