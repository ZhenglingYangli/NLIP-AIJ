"""Automatic acceptance of bundled tests and a fixed formal-input pilot."""
import argparse
from collections import defaultdict
from fractions import Fraction
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from internal.experiment import ROOT, default_config, load_config, make_jobs


def check_results(output, jobs):
    output = Path(output)
    failures = []
    expected = {j['id']: j for j in jobs}
    actual = {p.parent.name for p in (output / 'jobs').glob('*/result.json')}
    for name in sorted(actual - expected.keys()):
        failures.append({'job': name, 'reason': 'unexpected result', 'log': str(output / 'jobs' / name)})
    if len(expected) != len(jobs):
        failures.append({'job': 'plan', 'reason': 'duplicate planned configuration', 'log': str(output)})
    objectives = defaultdict(list)
    for name, job in expected.items():
        folder = output / 'jobs' / name
        reasons = []
        try:
            result = json.loads((folder / 'result.json').read_text())
            wanted = job.get('smoke_expected', {'status': 'SAT' if job['task'] == 'decision' else 'OPTIMAL'})
            if result.get('job_id') != name or result.get('method') != job['method']:
                reasons.append('result configuration differs from plan')
            if result.get('input') != job['input']:
                reasons.append('result input differs from plan')
            if result.get('verified') is not True:
                reasons.append('original-problem verification did not pass')
            for key, value in wanted.items():
                if result.get(key) != value:
                    reasons.append(f'{key}: expected {value}, got {result.get(key)}')
            if result.get('termination') or result.get('error'):
                reasons.append(str(result.get('termination') or result.get('error')))
            payload = json.loads((folder / 'job.json').read_text())
            if result.get('cpu') != payload.get('cpu') or result.get('cpu') is None:
                reasons.append('missing/inconsistent CPU assignment')
            log = (folder / 'stdout.log').read_text()
            if 'AIJ_CPU ' + json.dumps([result.get('cpu')]) not in log:
                reasons.append('worker did not confirm its actual CPU affinity')
            elapsed = result.get('solve_wall_seconds')
            if elapsed is None or not 0 <= elapsed <= result.get('solve_budget_seconds', -1):
                reasons.append('completion exceeds solve budget or timing is missing')
            if job['task'] == 'optimization' and result.get('status') == 'OPTIMAL':
                objectives[(job['family'], job['input'])].append((name, Fraction(result['objective_exact'])))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reasons.append(str(exc))
        if reasons:
            failures.append({'job': name, 'reason': '; '.join(reasons), 'log': str(folder / 'stdout.log')})
    for key, values in objectives.items():
        if len({value for _, value in values}) > 1:
            failures.append({'job': key[1], 'reason': 'conflicting optimal objectives: ' +
                             ', '.join(f'{name}={value}' for name, value in values), 'log': str(output / 'jobs')})
    report = {'passed': not failures, 'expected': len(jobs), 'found': len(actual), 'failures': failures}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'test-result.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['TEST PASSED' if report['passed'] else 'TEST FAILED']
    lines.extend(f"{f['job']}: {f['reason']}\n  Log: {f['log']}" for f in failures)
    (output / 'test-result.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines), flush=True)
    return report['passed']


def pilot(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(default_config()))
    ap.add_argument('--local', action='store_true', help='execute on this host instead of submitting to Slurm')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--required-cores', type=int, default=0)
    ap.add_argument('--memory-gib', type=float, default=16)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args(argv)
    output = a.output.resolve() if a.output else Path(tempfile.mkdtemp(prefix='pilot-', dir=_results_dir()))
    output.mkdir(parents=True, exist_ok=True)
    print('Pilot output:', output, flush=True)
    config = load_config(a.config)
    if not a.local:
        cores = int(os.environ.get('NLIP_WORKERS', '60'))
        command = [config['python'], str(ROOT / 'goSolver.py'), 'pilot', '--local',
                   '--config', str(Path(a.config).resolve()), '--output', str(output),
                   '--workers', str(a.workers), '--required-cores', str(cores),
                   '--memory-gib', str(a.memory_gib), '--seconds', str(a.seconds)]
        script = output / 'pilot.sh'
        script.write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec ' + shlex.join(command) + '\n')
        submitted = subprocess.run(['sbatch', '--parsable', '--wait', '--exclusive', '--nodes=1', '--ntasks=1',
            '--hint=nomultithread', '--partition=' + os.environ.get('NLIP_PARTITION', 'bigmem-amd'),
            '--cpus-per-task=' + str(cores), '--mem=' + os.environ.get('NLIP_JOB_MEMORY_GIB', '970') + 'G',
            '--time=01:30:00', '--output=' + str(output / 'slurm.log'), str(script)], text=True, capture_output=True)
        (output / 'submission.txt').write_text(submitted.stdout + submitted.stderr)
        report = output / 'test-result.json'
        if submitted.returncode or not report.exists():
            print('TEST FAILED\n' + submitted.stdout + submitted.stderr + '\nLog: ' + str(output / 'slurm.log'))
            return 1
        print((output / 'test-result.txt').read_text())
        return 0 if json.loads(report.read_text())['passed'] else 1
    from internal.runner import available_cpus, run_jobs
    try:
        cpus = available_cpus()
        print('Available physical cores:', len(cpus), flush=True)
        if len(cpus) < max(a.workers, a.required_cores):
            raise ValueError(f'need {max(a.workers, a.required_cores)} distinct cores; got {len(cpus)}')
        if a.seconds <= 0 or a.memory_gib <= 0:
            raise ValueError('pilot time and memory must be positive')
        config['profiles']['pilot'] = dict(solve_seconds=a.seconds, verify_seconds=10,
            outer_seconds=a.seconds + 20, memory_gib=a.memory_gib, poll_seconds=.05)
        jobs = make_jobs(config, 'pilot', 'main', list(config['families']))
        jobs += make_jobs(config, 'pilot', 'decomposition', ['mipo', 'smt'])
        run_jobs(config, jobs, profile='pilot', matrix='main+decomposition', workers=a.workers, output=output)
        return 0
    except Exception as exc:
        print('TEST FAILED\n' + str(exc) + '\nLog: ' + str(output), flush=True)
        if not (output / 'test-result.json').exists():
            (output / 'test-result.json').write_text(json.dumps({'passed': False, 'error': str(exc)}, indent=2))
            (output / 'test-result.txt').write_text('TEST FAILED\n' + str(exc) + '\n')
        return 1


def _results_dir():
    folder = ROOT.parent / 'results'
    folder.mkdir(exist_ok=True)
    return folder
