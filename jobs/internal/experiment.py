"""Shared site configuration, method matrix and experiment planning."""
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'codes'))
from solver.config import MAINLINE_OPTIONS


def default_config():
    site_config = ROOT / 'config.cluster.json'
    return site_config if site_config.exists() else ROOT / 'config.json'


def methods(task, matrix, family=None):
    if task == 'decision':
        baselines = [{'id': 'z3', 'solver': 'Z3'}, {'id': 'cvc5', 'solver': 'CVC5'}]
        backends = ['CADICAL']
    else:
        baselines = [{'id': s.lower(), 'solver': s}
                     for s in ['SCIP-NATIVE', 'Z3', 'CP-SAT', 'GUROBI']]
        backends = ['MAXHS', 'WMAXCDCL', 'UWRMAXSAT', 'EVALMAXRES']
    if matrix == 'baselines':
        return baselines
    if matrix == 'decomposition':
        if family not in ('mipo', 'smt'):
            return []
        backend = 'CADICAL' if task == 'decision' else 'WMAXCDCL'
        return [{'id': 'bin-d-unshared-' + backend.lower(), 'encoding': 'BIN', 'solver': backend,
                 'options': dict(MAINLINE_OPTIONS, decomp_shared=False)}]
    variants = [{'id': f'{enc.lower()}-{solver.lower()}', 'encoding': enc, 'solver': solver, 'options': {'use_lrn': False}}
                for enc in ['OH', 'UNA', 'BIN'] for solver in backends]
    if family in ('mipo', 'smt'):
        variants += [{'id': 'bin-d-' + s.lower(), 'encoding': 'BIN', 'solver': s,
                      'options': dict(MAINLINE_OPTIONS)}
                     for s in backends]
    return variants + baselines


def resolve(value):
    return str((ROOT / os.path.expandvars(value)).resolve())


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    for key in ['code_root', 'benchmark_root', 'manifest_root', 'python']:
        value = (config[key] or sys.executable) if key == 'python' else config[key]
        config[key] = (os.path.abspath(ROOT / os.path.expandvars(value))
                       if key == 'python' else resolve(value))
    config['git'] = os.environ.get('AIJ_GIT') or config.get('git') or shutil.which('git') or 'git'
    config['solver_paths'] = {k: resolve(v) for k, v in config['solver_paths'].items()}
    for desc in config['families'].values():
        if 'input_root' in desc:
            desc['input_root'] = resolve(desc['input_root'])
    return config


def manifest_names(config, family):
    path = Path(config['manifest_root']) / config['families'][family]['manifest']
    names = [line.strip() for line in path.read_text().splitlines()]
    return [name for name in names if name and not name.startswith('#')]


def job_ids(family, method_id, count):
    return [f'{family}-{number:04d}-{method_id}' for number in range(1, count + 1)]


def make_jobs(config, profile, matrix, families):
    jobs = []
    for family in families:
        desc = config['families'][family]
        if profile == 'smoke':
            files = [ROOT / 'smoke' / desc['smoke_file']]
        else:
            directory = Path(desc['input_root']) if 'input_root' in desc else Path(config['benchmark_root']) / desc['directory']
            names = manifest_names(config, family)
            index = {}
            for path in directory.rglob('*' + desc['extension']):
                index.setdefault(path.name, []).append(path)
            files = []
            for name in names:
                direct = directory / name
                matches = [direct] if direct.is_file() else index.get(name, [])
                if len(matches) != 1:
                    raise ValueError(f'{family}/{name}: expected one input, found {len(matches)}; search directory: {directory}')
                files.append(matches[0])
        selected_methods = methods(desc['task'], matrix, family)
        identifiers = {method['id']: job_ids(family, method['id'], len(files)) for method in selected_methods}
        for index, path in enumerate(files):
            for method in selected_methods:
                job = {'id': identifiers[method['id']][index], 'family': family,
                       'task': desc['task'], 'input': str(path.resolve()), 'method': method,
                       'code_root': config['code_root'], 'solver_paths': config['solver_paths'],
                       'solve_seconds': config['profiles'][profile]['solve_seconds'],
                       'solver_metadata': config.get('solver_metadata', {}),
                       'external_solver_args': config.get('external_solver_args', {})}
                if 'k' in desc:
                    job['k'] = desc['k']
                if profile == 'smoke':
                    job['smoke_expected'] = desc['smoke_expected']
                jobs.append(job)
    return jobs


def configuration_tasks(config, profile, matrix):
    tasks = []
    for family, desc in config['families'].items():
        count = 1 if profile == 'smoke' else len(manifest_names(config, family))
        for method in methods(desc['task'], matrix, family):
            tasks.append({'key': family + '-' + method['id'], 'family': family, 'method': method,
                          'job_ids': job_ids(family, method['id'], count)})
    ids = [job_id for task in tasks for job_id in task['job_ids']]
    if len(ids) != len(set(ids)):
        raise ValueError('overlapping configuration tasks')
    tasks.sort(key=lambda task: len(task['job_ids']), reverse=True)
    return tasks
