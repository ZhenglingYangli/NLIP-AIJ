"""Resolve known cluster paths and check all selected inputs before submission."""
import json
import os
import shutil
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from internal.experiment import ROOT, load_config, make_jobs


def select(label, candidates, executable=False):
    explicit = os.environ.get(label)
    if explicit:
        candidates = [explicit]
    for value in candidates:
        if value and (os.access(value, os.X_OK) and Path(value).is_file() if executable else Path(value).is_dir()):
            return str(Path(value).resolve())
    raise SystemExit(label + ' not found; checked: ' + ', '.join(str(p) for p in candidates if p))


def main():
    destination = ROOT / 'config.cluster.json'
    source = destination if destination.exists() else ROOT / 'config.json'
    config = json.loads(source.read_text())
    software = Path(os.environ.get('NLIP_SOFTWARE', ROOT.parent / 'solvers/matrics-20261124'))
    # Keep the selected virtual-environment path: resolving its symlink would
    # replace .venv/bin/python with the system interpreter outside that venv.
    config['python'] = os.path.abspath(os.environ.get('AIJ_PYTHON') or sys.executable)
    config['git'] = select('Git executable', [os.environ.get('AIJ_GIT'), shutil.which('git')], True)
    config['benchmark_root'] = select('NLIP_BENCHMARK_ROOT', [os.environ.get('NLIP_BENCHMARK_ROOT'),
        ROOT / config['benchmark_root']])
    for key, name in [('MAXHS', 'maxhs'), ('WMAXCDCL', 'wmaxcdcl_static'), ('UWRMAXSAT', 'uwrmaxsat'), ('EVALMAXRES', 'EvalMaxSAT'), ('CADICAL', 'cadical')]:
        config['solver_paths'][key] = select('NLIP_' + key, [os.environ.get('NLIP_' + key),
            ROOT / config['solver_paths'][key] if config['solver_paths'].get(key) else None,
            software / 'bin' / name], True)
    arguments = config.setdefault('external_solver_args', {})
    arguments.setdefault('MAXHS', ['-optimizer=scip', '-optimizer-threads=1', '-no-lp-harden-reduced'])
    if not any(option.startswith('-optimizer-threads=') for option in arguments['MAXHS']):
        arguments['MAXHS'].append('-optimizer-threads=1')
    arguments.setdefault('UWRMAXSAT', ['-no-bin', '-no-sat', '-no-par', '-maxpre-time=60',
                                    '-scip-cpu=900', '-scip-cpu-add=400', '-m', '-bm'])
    if 'EVALMAXRES' not in arguments:
        helper = select('NLIP_EVALMAXRES_HELPER', [os.environ.get('NLIP_EVALMAXRES_HELPER'),
            Path(config['solver_paths']['EVALMAXRES']).parent / 'nuwls',
            software / 'bin/nuwls'], True)
        arguments['EVALMAXRES'] = ['--noSaveCores', '--noSimplify', '--path_anytime_solver', helper]
    # An explicit replacement helper must also update an existing site config.
    if os.environ.get('NLIP_EVALMAXRES_HELPER') and 'EVALMAXRES' in arguments:
        helper = select('NLIP_EVALMAXRES_HELPER', [os.environ['NLIP_EVALMAXRES_HELPER']], True)
        options = arguments['EVALMAXRES']
        flag = '--path_anytime_solver'
        if flag in options:
            index = options.index(flag)
            options[index:index + 2] = [flag, helper]
        else:
            options.extend([flag, helper])
    defaults = json.loads((ROOT / 'config.json').read_text())['solver_metadata']
    metadata = config.setdefault('solver_metadata', {})
    for backend, info in defaults.items():
        metadata.setdefault(backend, info)
    if os.environ.get('NLIP_DIVERSE_ROOT'):
        config['families']['diverse']['input_root'] = os.environ['NLIP_DIVERSE_ROOT']
    if os.environ.get('NLIP_MIPO_ROOT'):
        config['families']['mipo']['input_root'] = os.environ['NLIP_MIPO_ROOT']
    # Only the resolved site config is local; committed source stays clean.
    destination.write_text(json.dumps(config, indent=2) + '\n')
    resolved = load_config(destination)
    jobs = make_jobs(resolved, 'formal', 'main', list(resolved['families']))
    print(json.dumps({'config': str(destination), 'python': resolved['python'], 'benchmark_root': resolved['benchmark_root'],
        'solver_paths': resolved['solver_paths'], 'mipo_root': resolved['families']['mipo']['input_root'],
        'runs': len(jobs), 'by_family': dict(Counter(j['family'] for j in jobs))}, indent=2))


if __name__ == '__main__':
    main()
