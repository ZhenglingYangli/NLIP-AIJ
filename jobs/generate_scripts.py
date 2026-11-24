"""Generate Slurm jobs and submit.sh, following the original generate_scripts.py layout."""
import argparse
import json
from math import ceil
from pathlib import Path
import shlex
import os
import subprocess
from internal.experiment import ROOT, configuration_tasks, default_config, load_config, make_jobs
from internal.runner import git_identity

PARALLEL_NUM = 60
PARTITION = 'bigmem-amd'
CONCURRENT_JOBS = 1

PARTITION_LIMITS = {
    'normal': (28, 125, 360, 4),
    'bigmem': (28, 500, 360, 4),
    'bigmem-amd': (64, 1000, 240, 2),
    'manycore-amd': (256, 1520, 240, 2),
}

def write_submission(plan, output, wall_hours):
    exports = f'--export=ALL,AIJ_RUNNER_DIR={ROOT},AIJ_CAMPAIGN={output}'
    wall_time = '00:05:00' if plan['profile'] == 'smoke' else f'{wall_hours // 24}-{wall_hours % 24:02d}:00:00'
    command = [
        'sbatch', '--parsable', f'--partition={plan["partition"]}',
        f'--array=0-{plan["configuration_jobs"] - 1}%{plan["concurrent_jobs"]}',
        f'--cpus-per-task={plan["workers"]}', f'--mem={plan["memory_gib"]}G',
        '--signal=B:TERM@60',
        f'--time={wall_time}',
        f'--output={output}/slurm-%A_%a.log', exports,
        str(ROOT / 'internal/run_slurm.sh'),
    ]
    if plan['profile'] == 'formal':
        command.insert(1, '--exclusive')
    analysis = [
        '--parsable', f'--output={output}/analysis-%j.log', exports,
        str(ROOT.parent / 'analysis/run_campaign_analysis.sh'),
    ]
    check = [str(ROOT / 'goSolver.py'),
             '--campaign', str(output), '--check-code']
    script = f'''#!/usr/bin/env bash
set -euo pipefail
if [[ -f {shlex.quote(str(output / 'array_job_id.txt'))} ]]; then
    echo "Campaign already submitted. Inspect its saved job ID before resubmitting." >&2
    exit 1
fi
export AIJ_PYTHON={shlex.quote(plan['config_snapshot']['python'])}
export AIJ_GIT={shlex.quote(plan['config_snapshot']['git'])}
"$AIJ_PYTHON" -c "import matplotlib"
"$AIJ_PYTHON" {shlex.join(check)}
array_id=$({shlex.join(command)})
array_id=${{array_id%%;*}}
printf "%s\\n" "$array_id" > {shlex.quote(str(output / 'array_job_id.txt'))}
printf "Configuration array: %s\\n" "$array_id"
analysis_id=$(sbatch --dependency="afterany:$array_id" {shlex.join(analysis)})
analysis_id=${{analysis_id%%;*}}
printf "%s\\n" "$analysis_id" > {shlex.quote(str(output / 'analysis_job_id.txt'))}
printf "Analysis job: %s\\n" "$analysis_id"
'''
    (output / 'submit.sh').write_text(script)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config')
    ap.add_argument('--profile',choices=['formal','smoke'],default='formal')
    ap.add_argument('--matrix',choices=['main','decomposition'],default='main')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--workers',type=int,help='default 60 for formal runs, 1 for small tests')
    ap.add_argument('--partition',choices=list(PARTITION_LIMITS),default=PARTITION)
    ap.add_argument('--concurrent-jobs',type=int,default=CONCURRENT_JOBS)
    ap.add_argument('--memory-gib',type=int,help='default 970 GiB for 60 formal workers; sized from worker budgets')
    a=ap.parse_args()
    if a.workers is None:
        a.workers = PARALLEL_NUM if a.profile == 'formal' else 1
    if a.config is None:
        a.config=str(default_config())
    if a.output is None:
        name=a.matrix if a.profile=='formal' else 'smoke-'+a.matrix
        a.output=ROOT.parent/'results'/name
    config=load_config(a.config)
    subprocess.run([config['python'], str(ROOT / 'tools/check_environment.py')], check=True)
    if a.memory_gib is None:
        a.memory_gib=ceil((a.workers*config['profiles'][a.profile]['memory_gib']+.5)/10)*10
    cores_max,memory_max,time_max,concurrent_max=PARTITION_LIMITS[a.partition]
    if not 1<=a.workers<=cores_max or not 1<=a.concurrent_jobs<=concurrent_max:
        raise ValueError(f'{a.partition}: workers must be 1..{cores_max}; concurrent jobs must be 1..{concurrent_max}')
    if a.memory_gib < a.workers*config['profiles'][a.profile]['memory_gib']+.5 or a.memory_gib>memory_max:
        raise ValueError(f'memory must cover worker budgets plus runner reserve and be <={memory_max} GiB on {a.partition}')
    tasks=configuration_tasks(config,a.profile,a.matrix)
    # Resolve every listed input once on the login node before writing a plan.
    jobs = make_jobs(config,a.profile,a.matrix,list(config['families']))
    if len(jobs) != sum(len(t['job_ids']) for t in tasks):
        raise ValueError('expanded inputs do not match the configuration plan')
    for backend in {j['method']['solver'] for j in jobs} & {'MAXHS','WMAXCDCL','UWRMAXSAT','EVALMAXRES','CADICAL'}:
        path = Path(config['solver_paths'].get(backend, ''))
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f'{backend}: configure an executable solver path before generating jobs')
        info = config.get('solver_metadata',{}).get(backend,{})
        if a.profile == 'formal' and (not info.get('release') or not info.get('mode')):
            raise ValueError(f'{backend}: record release and mode in solver_metadata')
    limits=config['profiles'][a.profile]
    # Size the job from the largest configuration and the outer per-run cap.
    worst=max(ceil(len(t['job_ids'])/a.workers)*limits['outer_seconds'] for t in tasks)
    wall_hours=ceil(worst/3600)+2
    if wall_hours>time_max:
        raise ValueError(f'configuration exceeds the {time_max}-hour job limit on {a.partition}; increase workers')
    plan={'config':str(Path(a.config).resolve()),'profile':a.profile,'matrix':a.matrix,
          'partition':a.partition,'workers':a.workers,'concurrent_jobs':a.concurrent_jobs,'memory_gib':a.memory_gib,
          'configuration_jobs':len(tasks),'instance_runs':sum(len(t['job_ids']) for t in tasks),'tasks':tasks}
    plan['code_version']=git_identity(config['code_root'], config['git'])
    plan['config_snapshot']=config
    plan['limits']=limits
    plan['runner_version']=git_identity(str(ROOT), config['git'])
    plan['manifests']={f:(Path(config['manifest_root'])/d['manifest']).read_text().splitlines()
                       for f,d in config['families'].items()}
    output=a.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    planpath=output/'campaign.json'
    if planpath.exists() and json.loads(planpath.read_text())!=plan:
        raise ValueError('existing campaign has different settings; keep its plan unchanged')
    planpath.write_text(json.dumps(plan,indent=2)+'\n')
    write_submission(plan, output, wall_hours)
    print(json.dumps({k:plan[k] for k in ['profile','matrix','partition','workers','concurrent_jobs','memory_gib','configuration_jobs','instance_runs']},indent=2))
    print('Prepared only. Submit with: bash '+shlex.quote(str(output/'submit.sh')))

if __name__=='__main__': main()
