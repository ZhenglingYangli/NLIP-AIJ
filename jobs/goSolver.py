#!/usr/bin/env python3
"""Run NLIP instances with shared time, memory and verification controls."""
import argparse
from collections import Counter
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from internal.experiment import default_config, load_config, make_jobs


def run_campaign():
    """Execute or check one configuration from a prepared Slurm campaign."""
    from internal.experiment import ROOT, methods
    from internal.runner import git_identity, run_jobs
    ap=argparse.ArgumentParser()
    ap.add_argument('--campaign',required=True,type=Path)
    ap.add_argument('--index',type=int)
    ap.add_argument('--check-code',action='store_true',help='check the prepared version on the login node before submitting')
    a=ap.parse_args(); folder=a.campaign.resolve()
    plan=json.loads((folder/'campaign.json').read_text())
    config=load_config(plan['config'])
    if 'config_snapshot' in plan and config!=plan['config_snapshot']:
        raise ValueError('site configuration changed after preparing campaign')
    if a.check_code:
        if git_identity(config['code_root'], config['git'])!=plan['code_version'] or git_identity(str(ROOT), config['git'])!=plan['runner_version']:
            raise ValueError('execution code changed after preparing campaign')
        if plan['profile']=='formal' and (plan['code_version']['dirty'] or plan['runner_version']['dirty']):
            raise ValueError('commit the solver and runner code before preparing a formal campaign')
        return
    if a.index is None or not 0<=a.index<len(plan['tasks']): raise ValueError('invalid configuration index')
    task=plan['tasks'][a.index]; desc=config['families'][task['family']]
    current=next(m for m in methods(desc['task'],plan['matrix'],task['family']) if m['id']==task['method']['id'])
    if current!=task['method']: raise ValueError('method changed after preparing campaign')
    names=(Path(config['manifest_root'])/desc['manifest']).read_text().splitlines()
    if names!=plan['manifests'][task['family']]: raise ValueError('manifest changed after preparing campaign')
    jobs = [job for job in make_jobs(config, plan['profile'], plan['matrix'], [task['family']])
            if job['method']['id'] == current['id']]
    if [job['id'] for job in jobs] != task['job_ids']:
        raise ValueError('instance list changed after preparation')
    output=folder/'runs'/task['key']
    run_jobs(config, jobs, profile=plan['profile'], matrix=plan['matrix'],
             workers=plan['workers'], output=output, resume=(output/'run.json').exists(),
             code_version=plan['code_version'], runner_version=plan['runner_version'])


def main():
    if '--campaign' in sys.argv[1:]:
        return run_campaign()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', nargs='?', choices=['test', 'run'], help='test a bundled instance or run one formal configuration')
    ap.add_argument('family', nargs='?', choices=['qplib', 'diverse', 'mipo', 'smt', 'all'])
    ap.add_argument('method', nargs='?', help='method id, e.g. bin-wmaxcdcl or bin-cadical')
    ap.add_argument('--config')
    ap.add_argument('--print-python', action='store_true', help='print the configured interpreter without planning or solving')
    ap.add_argument('--profile', choices=['smoke', 'formal'], default='smoke')
    ap.add_argument('--matrix', choices=['main', 'decomposition', 'baselines'], default='main')
    ap.add_argument('--families', nargs='+', choices=['qplib', 'diverse', 'mipo', 'smt'], default=['qplib', 'diverse', 'mipo', 'smt'])
    ap.add_argument('--workers', type=int)
    ap.add_argument('--methods', nargs='+', help='run only these exact method ids')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--plan-output', type=Path, help='save the expanded job list without running it')
    ap.add_argument('--execute', action='store_true', help='execute instead of printing the plan')
    ap.add_argument('--resume', action='store_true', help='continue jobs that have no completed result')
    args = ap.parse_args()
    if args.action:
        if args.action == 'run' and (args.family in (None, 'all') or not args.method):
            ap.error('run requires a family and method, e.g. run qplib bin-wmaxcdcl')
        args.profile = 'smoke' if args.action == 'test' else 'formal'
        if args.family == 'all':
            if args.method:
                ap.error('test all runs the complete matrix; omit the method')
            args.families = ['qplib', 'diverse', 'mipo', 'smt']
            args.methods = None
        else:
            args.families = [args.family or 'qplib']
            args.methods = [args.method or ('bin-cadical' if args.family == 'smt' else 'bin-wmaxcdcl')]
        args.execute = True
    if args.workers is None:
        args.workers = 7 if args.action == 'run' else 1
    if args.config is None:
        args.config = str(default_config())
    config = load_config(args.config)
    if args.print_python:
        print(config['python'])
        return
    jobs = make_jobs(config, args.profile, args.matrix, args.families)
    if args.methods:
        missing = set(args.methods) - {j['method']['id'] for j in jobs}
        if missing:
            raise ValueError('unknown method ids: ' + str(sorted(missing)))
        jobs = [j for j in jobs if j['method']['id'] in args.methods]
    limits = config['profiles'][args.profile]
    counts = dict(Counter(job['family'] for job in jobs))
    plan = {'profile': args.profile, 'matrix': args.matrix, 'jobs': len(jobs),
                      'by_family': counts, 'solve_core_hours_upper_bound': len(jobs) * limits['solve_seconds'] / 3600,
            'limits': limits}
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.plan_output:
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.plan_output.write_text(json.dumps(dict(plan, job_list=jobs), ensure_ascii=False, indent=2))
    if not args.execute:
        return
    from internal.runner import run_jobs
    run_jobs(config, jobs, profile=args.profile, matrix=args.matrix,
             workers=args.workers, output=args.output, resume=args.resume)


if __name__ == '__main__':
    main()
