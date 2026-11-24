"""Export four analysis files, with optional Git submission of only those files."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import time

FILES = ('all_results.csv', 'status-counts.json', 'run-info.json', 'slurm-accounting.psv')


def command(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def recorded_jobs(source):
    ids = []
    for name in ('array_job_id.txt', 'analysis_job_id.txt'):
        p = source / name
        if not p.is_file() or not p.read_text().strip().isdigit():
            raise ValueError('missing/invalid submitted job ID: ' + str(p))
        ids.append(p.read_text().strip())
    return ids


def wait_for_jobs(ids):
    print('Waiting for recorded jobs:', ', '.join(ids), flush=True)
    while True:
        queued = command(['squeue', '--noheader', '--me', '--format=%i'])
        if not any(line.strip().split('_')[0].split('.')[0] in ids for line in queued.splitlines()):
            return
        time.sleep(15)


def accounting(source, plan):
    ids = recorded_jobs(source)
    data = command(['sacct', '--array', '--noheader', '--parsable2', '--jobs=' + ','.join(ids),
                    '--format=JobID%64,State%32,ExitCode,Elapsed,NodeList,MaxRSS,AllocCPUS'])
    records = {line.split('|')[0]: line.split('|') for line in data.splitlines() if line}
    expected = {ids[0] + '_' + str(i) for i in range(len(plan['tasks']))} | {ids[1]}
    missing = expected - records.keys()
    if missing:
        raise ValueError('missing Slurm accounting: ' + ', '.join(sorted(missing)))
    active = [key for key in expected if records[key][1].split()[0].rstrip('+') in
              {'RUNNING', 'PENDING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED', 'REQUEUED', 'RESIZING'}]
    if active:
        raise ValueError('jobs have not finished: ' + ', '.join(active))
    return 'JobID|State|ExitCode|Elapsed|NodeList|MaxRSS|AllocCPUS\n' + data + '\n'


def validate_rows(rows, plan):
    expected = {}
    for task in plan['tasks']:
        for identifier in task['job_ids']:
            if identifier in expected:
                raise ValueError('duplicate planned job: ' + identifier)
            expected[identifier] = task
    if len(rows) != len(expected) or {r['job_id'] for r in rows} != set(expected):
        raise ValueError('result matrix contains missing, duplicate or unexpected records')
    optima = defaultdict(set)
    for row in rows:
        task = expected[row['job_id']]
        if row['family'] != task['family'] or row['method'] != task['method']['id'] or row['solver'] != task['method']['solver']:
            raise ValueError('wrong configuration: ' + row['job_id'])
        if row['status'] in ('', 'PENDING', 'INTERRUPTED'):
            raise ValueError('unfinished result: ' + row['job_id'])
        if row['status'] in ('OPTIMAL', 'SAT', 'FEASIBLE') and row['verified'].lower() != 'true':
            raise ValueError('successful/feasible result lacks original-problem verification: ' + row['job_id'])
        if row['status'] == 'OPTIMAL':
            instance = row['job_id'][:-(len(row['method']) + 1)]
            optima[instance].add(Fraction(row['objective_exact']))
    conflicts = [key for key, values in optima.items() if len(values) > 1]
    if conflicts:
        raise ValueError('conflicting optimal objectives: ' + ', '.join(conflicts))
    return dict(Counter(r['status'] for r in rows))


def export(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    plan = json.loads((source / 'campaign.json').read_text())
    with (source / 'results.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    counts = validate_rows(rows, plan)
    summary = json.loads((source / 'summary.json').read_text())
    if counts != summary['statuses'] or summary['planned'] != len(rows):
        raise ValueError('summary and result table disagree')
    slurm = accounting(source, plan)
    environments = {}
    for task in plan['tasks']:
        record = json.loads((source / 'runs' / task['key'] / 'run.json').read_text())
        environments[task['key']] = {'created_utc': record['created_utc'],
            'plan': {k: v for k, v in record['plan'].items() if k != 'jobs'}}
    if target.exists():
        raise ValueError('export directory already exists: ' + str(target))
    target.mkdir(parents=True)
    shutil.copyfile(source / 'results.csv', target / 'all_results.csv')
    (target / 'status-counts.json').write_text(json.dumps(counts, indent=2) + '\n')
    (target / 'run-info.json').write_text(json.dumps({'exported_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(source), 'campaign': plan, 'environments': environments}, indent=2) + '\n')
    (target / 'slurm-accounting.psv').write_text(slurm)
    print('EXPORT PASSED:', target, flush=True)
    return target


def push(target):
    repo = Path(command(['git', '-C', str(target), 'rev-parse', '--show-toplevel']))
    files = [str((target / name).relative_to(repo)) for name in FILES]
    for name in FILES:
        if not (target / name).is_file():
            raise ValueError('missing export file: ' + name)
    branch = command(['git', 'branch', '--show-current'], cwd=repo)
    if not branch:
        raise ValueError('checkout a branch before pushing results')
    subprocess.run(['git', 'add', '--', *files], cwd=repo, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *files], cwd=repo).returncode
    if changed:
        subprocess.run(['git', 'commit', '--only', '-m', 'Add NLIP experiment results: ' + target.name,
                        '--', *files], cwd=repo, check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + branch], cwd=repo, check=True)
    print('PUSH PASSED', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign', type=Path, required=True)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--summarize', action='store_true', help='wait for recorded jobs and recompute the result table')
    ap.add_argument('--push', action='store_true', help='commit and push only the four exported files')
    a = ap.parse_args()
    source = a.campaign.resolve()
    target = a.output.resolve() if a.output else Path(__file__).resolve().parents[1] / 'experiment-results' / ('run-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    try:
        if a.summarize:
            wait_for_jobs(recorded_jobs(source))
            from summarize import summarize
            summarize(source)
        export(source, target)
        if a.push:
            push(target)
    except Exception as exc:
        print('EXPORT/PUSH FAILED:', exc, flush=True)
        print('Export directory:', target, flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
