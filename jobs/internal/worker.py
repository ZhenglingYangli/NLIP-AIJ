#!/usr/bin/env python3
"""One AIJ job. The parent process enforces wall time and process-tree RSS."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback


def emit(kind, value):
    print('AIJ_' + kind + ' ' + json.dumps(value, ensure_ascii=False, default=str), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    args = ap.parse_args()
    job = json.loads(Path(args.job).read_text())
    import psutil
    psutil.Process().cpu_affinity([job['cpu']])
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    root = Path(job['code_root'])
    sys.path.insert(0, str(root / 'codes'))
    sys.path.insert(0, str(root))
    from telemetry import enable, progress, problem_features
    from nlipsat import load_problem as parse_problem
    import tools.verify as verification
    import solver.solve as engine
    from solver.config import EncodingConfig
    enable()
    def load_problem(path, **kwargs):
        progress('parse')
        start = time.monotonic()
        problem = parse_problem(path, **kwargs)
        read = time.monotonic()-start
        progress('build', read_seconds=read, problem_features=problem_features(problem))
        return problem

    def load_decision(path):
        from tools.smt2_parser import parse_smt2_file
        progress('parse')
        start = time.monotonic()
        problem = parse_smt2_file(path, objective_mode='zero')
        progress('build', read_seconds=time.monotonic()-start, problem_features=problem_features(problem))
        return problem

    def on_built(wcnf, timings):
        progress('solve', formula={'variables':wcnf.nv, 'hard':len(wcnf.hard), 'soft':len(wcnf.soft)},
                 encoding_stats=wcnf._encoding_stats, top_weight=wcnf.topw, total_soft_weight=sum(wcnf.wght),
                 solver_timings=timings)
    verify_started = None

    def begin_verify():
        nonlocal verify_started
        if verify_started is None:
            verify_started = time.monotonic()
            emit('PHASE', {'phase': 'verify', 'at': verify_started})

    method = job['method']
    started = time.monotonic()
    if method['solver'] == 'CVC5':
        from solvers.baseline.cvc5_baseline import solve, solve_smt2, Unsupported
        try:
            if job['task'] == 'decision':
                result = solve_smt2(job['input'], max(.001, job['solve_seconds'] - (time.monotonic()-started)), begin_verify)
            else:
                problem = load_problem(job['input'], k=job.get('k'))
                result = solve(problem, max(.001, job['solve_seconds'] - (time.monotonic()-started)), begin_verify)
        except Unsupported as exc:
            result = {'status': 'UNSUPPORTED', 'verified': False, 'error': str(exc)}
    elif method['solver'] in ('SCIP-MILP', 'SCIP-NATIVE'):
        if job['task'] == 'decision':
            problem = load_decision(job['input'])
        else:
            problem = load_problem(job['input'], k=job.get('k'))
        from solvers.baseline.scip_baseline import solve
        remaining = max(.001, job['solve_seconds'] - (time.monotonic() - started))
        result = solve(problem, 'milp' if method['solver']=='SCIP-MILP' else 'native',
                       remaining, job['task'], begin_verify)
    elif method['solver'] in ('CPLEX-NATIVE', 'CPLEX-MILP', 'HIGHS-MILP'):
        from solvers.baseline.optimization_baselines import solve
        problem = load_problem(job['input'], k=job.get('k'))
        result = solve(problem, method['solver'], max(.001, job['solve_seconds'] - (time.monotonic()-started)), begin_verify)
    elif method['solver'] in ('CP-SAT', 'GUROBI'):
        from solvers.baseline.integer_baselines import solve
        problem = load_problem(job['input'], k=job.get('k'))
        result = solve(problem, method['solver'],
                       max(.001, job['solve_seconds'] - (time.monotonic()-started)), begin_verify)
    elif method['solver'] == 'Z3':
        from solvers.baseline import run_z3 as baseline
        if job['task'] == 'decision':
            raw = baseline.solve_smt2(job['input'], job['solve_seconds'],
                                      progress=progress, on_verify=begin_verify)
        else:
            problem = load_problem(job['input'], k=job.get('k'))
            remaining = max(.001, job['solve_seconds'] - (time.monotonic() - started))
            raw = baseline.solve_qplib(problem, remaining, progress=progress, on_verify=begin_verify)
        objective = raw.get('objective')
        result = {'status': raw['status'], 'verified': raw.get('verified', False),
                  'objective_exact': str(objective) if objective not in (None, 'N/A') else None,
                  'witness': raw.get('witness'), 'error': raw.get('error_msg'),
                  'solver_timings': {'total': raw.get('time'), 'verify': raw.get('time_verify')}}
    else:
        if job['task'] == 'decision':
            problem = load_decision(job['input'])
        else:
            problem = load_problem(job['input'], k=job.get('k'))
        cfg = EncodingConfig(**method.get('options', {}))
        cfg.workdir = str(Path(args.job).parent)
        # A single parent wall deadline includes import, parsing and encoding.
        # Native CPU limits are deliberately not used as competing budgets.
        cfg.external_solver_timeout = 0
        cfg.external_solver_args = job.get('external_solver_args', {})
        cfg.encoding_deadline = time.time() + max(.001, job['solve_seconds'] - (time.monotonic()-started))
        for key, value in job['solver_paths'].items():
            setattr(cfg, key.lower() + '_path', value)
        if job['task'] == 'decision':
            from solver.sat import solve_cnf
            wcnf, names, timings, pool = engine.build_wcnf(problem, method['encoding'], cfg, True)
            on_built(wcnf, timings)
            if wcnf.soft:
                raise ValueError('decision job produced soft clauses')
            t = time.monotonic()
            sat, model, command = solve_cnf(wcnf.hard, method['solver'],
                                            job['solver_paths'].get(method['solver']))
            timings['solve'] = time.monotonic() - t
            report = {}
            if sat:
                begin_verify()
                valid, report = verification.verify_solution(problem, {
                    'assignment': model, 'vpool': pool, 'name2idx': names,
                    'processed_problem': wcnf._processed_problem,
                    'preprocess_meta': wcnf._preprocess_meta}, method['encoding'])
            result = {'status': ('SAT' if valid else 'INVALID') if sat else 'UNSAT',
                      'verified': bool(sat and valid), 'witness': report.get('var_values'),
                      'name_map': problem.get('_name_map'), 'objective_exact': None,
                      'verification': report, 'solver_timings': timings, 'external_command': command,
                      'encoding_stats': wcnf._encoding_stats,
                      'formula': {'variables': wcnf.nv, 'hard': len(wcnf.hard), 'soft': len(wcnf.soft)}}
        else:
            raw = engine.build_and_solve(problem, method['encoding'], cfg, solver=method['solver'],
                                        on_built=on_built, on_verify=begin_verify)
            result = {'status': raw['solver_status'], 'verified': raw.get('verified', False),
                      'objective_exact': raw.get('objective_value_exact'),
                      'witness': raw.get('verification', {}).get('var_values'),
                      'verification': raw.get('verification'), 'solver_timings': raw.get('timings'),
                      'encoding_stats': raw['encoding_stats'],
                      'external_command': raw.get('external_command'),
                      'maxsat_cost':raw['maxsat_cost'] if raw.get('maxsat_cost',-1)>=0 else None, 'top_weight':raw.get('top_weight'),
                      'total_soft_weight':raw.get('total_soft_weight'),
                      'formula': {k: raw[k] for k in ['num_variables', 'num_hard_clauses', 'num_soft_clauses']}}
    if result['status'] in ('SAT', 'OPTIMAL', 'FEASIBLE') and not result['verified']:
        result.update(status='INVALID', error='successful status without completed original-problem verification')
    expected = job.get('smoke_expected')
    if expected is not None:
        if result['status'] != expected['status'] or result.get('objective_exact') != expected.get('objective_exact'):
            result.update(status='INVALID', error='smoke result differs from the hand-computed answer')
    emit('RESULT', result)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        traceback.print_exc()
        emit('RESULT', {'status': 'ERROR', 'verified': False, 'error': f'{type(exc).__name__}: {exc}'})
        sys.exit(1)
