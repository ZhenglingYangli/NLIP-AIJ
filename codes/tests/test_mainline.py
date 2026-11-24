"""Check the adopted CLI preset and preserve the generic entry's semantics."""
import contextlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import config_from_arguments, main, parse_arguments
from nlipsat import MAINLINE_SOLVER, mainline_config


class MainlineEntry(unittest.TestCase):
    def test_generic_defaults_are_preserved(self):
        args = parse_arguments(['example.json'])
        cfg = config_from_arguments(args)
        self.assertEqual((args.encoding, args.solver), ('OH', 'RC2'))
        self.assertFalse(cfg.use_decomposition)
        self.assertFalse(cfg.use_lrn)

    def test_preset_and_public_factory_agree(self):
        args = parse_arguments(['example.json', '--preset', 'mainline'])
        self.assertEqual(config_from_arguments(args), mainline_config())
        self.assertEqual(args.solver, MAINLINE_SOLVER)
        self.assertEqual(args.encoding, 'BIN')
        cfg = mainline_config()
        self.assertTrue(cfg.use_decomposition and cfg.decomp_exact and cfg.decomp_shared)
        self.assertEqual((cfg.decomp_threshold, cfg.decomp_strategy), (3, 'sequential'))
        self.assertFalse(cfg.use_lrn)
        cfg.use_lrn = True
        self.assertFalse(mainline_config().use_lrn)

    def test_preset_allows_operational_options(self):
        args = parse_arguments(['example.json', '--preset', 'mainline',
                                '--timeout', '90', '--verify', '-o', 'out.wcnf'])
        self.assertEqual(args.timeout, 90)
        self.assertTrue(args.verify)
        self.assertEqual(args.output, 'out.wcnf')
        self.assertEqual(config_from_arguments(args), mainline_config())

    def test_preset_rejects_method_changes(self):
        for options in (['-e', 'OH'], ['-s', 'MAXHS'], ['--decomp-threshold', '4'],
                        ['--decomp-strategy', 'binary_tree'], ['--decomp-relaxed'],
                        ['--no-decomp-shared'], ['--no-weight-gcd'], ['--no-preprocess']):
            with self.subTest(options=options):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    parse_arguments(['example.json', '--preset', 'mainline', *options])
                self.assertEqual(error.exception.code, 2)

    def test_cli_solves_cubic_min_and_max_against_enumeration(self):
        problem = {
            'variables': {'x': {'lb': 0, 'ub': 2}, 'y': {'lb': 0, 'ub': 2}},
            'constraints': [],
            'objective': {'sense': 'min', 'terms': [
                {'c': 1, 'vars': {'x': 3}},
                {'c': -3, 'vars': {'x': 1, 'y': 1}},
                {'c': 1, 'vars': {'y': 2}},
            ]},
        }
        values = [x ** 3 - 3 * x * y + y ** 2 for x in range(3) for y in range(3)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cubic.json'
            for sense, expected in [('min', min(values)), ('max', max(values))]:
                with self.subTest(sense=sense):
                    problem['objective']['sense'] = sense
                    path.write_text(json.dumps(problem), encoding='utf-8')
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        status = main([str(path), '--preset', 'mainline'])
                    self.assertEqual(status, 0, output.getvalue())
                    self.assertIn('Encoding BIN+DECOMP Solver RC2 Status OPTIMAL', output.getvalue())
                    self.assertEqual(int(re.search(r'OPTExact (-?\d+)\s*$', output.getvalue()).group(1)),
                                     expected)


if __name__ == '__main__':
    unittest.main()
