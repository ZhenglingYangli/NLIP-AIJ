"""Execute one configuration from a prepared campaign."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from internal.experiment import ROOT, load_config, methods, make_jobs
from internal.runner import git_identity, run_jobs

def main():
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

if __name__=='__main__': main()
