#!/usr/bin/env python3
"""Result columns and aggregation for single runs and complete campaigns."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

FIELDS = ['job_id', 'family', 'task', 'method', 'encoding', 'solver', 'status', 'verified',
          'objective_exact', 'solve_wall_seconds', 'verify_wall_seconds', 'wall_seconds',
          'solve_budget_seconds', 'peak_tree_rss_bytes', 'termination', 'host', 'cpu', 'input',
          'num_variables', 'num_hard_clauses', 'num_soft_clauses', 'encode_seconds', 'backend_seconds',
          'decomposition_requested', 'decomposition_effective', 'lrn_requested']
FEATURES = ['representation','variables','boolean_variables','boolean_fraction','domain_size_min','domain_size_max',
            'domain_size_mean','objective_terms','objective_degree','constraints','constraint_atoms',
            'nonlinear_constraint_atoms','constraint_degree','objective_sense','ast_nodes']
QUALITY = ['primal_bound_internal','dual_bound_internal','primal_bound_original','dual_bound_original',
           'absolute_gap_original','normalized_gap_original','backend_relative_gap','search_nodes']
FIELDS += ['read_seconds','maxsat_cost','top_weight','total_soft_weight','last_phase','termination_phase',
           'model_variables','model_constraints','domain_bits','product_variables','model_route',
           'objective_scale','objective_divisor','objective_constant',
           'decomposed_terms','multiplication_requests','multiplication_nodes','cache_hits',
           'generated_variables','generated_hard','generated_soft','simplified_variables','simplified_hard','simplified_soft',
           'max_weight_bits','total_weight_bits','weight_gcd']
FIELDS += ['original_'+key for key in FEATURES] + QUALITY
FIELDS += ['phase_'+key+'_seconds' for key in ['startup','parse','build','solve','verify']]
FIELDS += ['outer_budget_seconds','verify_budget_seconds','memory_budget_gib','backend_status','error','returncode']


def row_for(job, result):
    method = job['method']
    row = {key: result.get(key, '') for key in FIELDS}
    row.update(job_id=job['id'], family=job['family'], task=job.get('task', ''),
               method=method['id'], encoding=method.get('encoding', ''), solver=method['solver'],
               input=result.get('input', job.get('input', '')), status=result.get('status', 'PENDING'))
    formula = result.get('formula', {})
    for key, alternate in [('num_variables', 'variables'), ('num_hard_clauses', 'hard'), ('num_soft_clauses', 'soft')]:
        row[key] = formula.get(key, formula.get(alternate, ''))
    timings = result.get('solver_timings', {})
    row['encode_seconds'] = timings.get('build_total', timings.get('build', ''))
    row['backend_seconds'] = timings.get('solve', '')
    stats = result.get('encoding_stats', {})
    row['decomposition_requested'] = stats.get('decomposition_requested', '')
    row['decomposition_effective'] = stats.get('decomposition_effective', '')
    row['lrn_requested'] = stats.get('lrn', {}).get('requested', '')
    row['model_route'] = formula.get('route','sat-maxsat' if formula.get('hard') is not None or formula.get('num_hard_clauses') is not None else '')
    for key,source in [('model_variables','variables'),('model_constraints','constraints'),('domain_bits','domain_bits'),
                       ('product_variables','product_variables'),('objective_scale','objective_scale'),
                       ('objective_divisor','objective_divisor'),('objective_constant','objective_constant')]:
        row[key] = formula.get(source,'')
    for key in ['decomposed_terms','multiplication_requests','multiplication_nodes','cache_hits']:
        row[key] = sum(stats.get(scope,{}).get(key,0) for scope in ['objective','constraints']) if stats else ''
    for stage in ['generated','simplified']:
        for key in ['variables','hard','soft']:
            row[stage+'_'+key] = stats.get(stage,{}).get(key,'')
    for key in ['max_weight_bits','total_weight_bits']:
        row[key] = stats.get('simplified',{}).get(key,'')
    row['weight_gcd'] = stats.get('weight_gcd','')
    row.update({'original_'+k:result.get('problem_features',{}).get(k,'') for k in FEATURES})
    row.update({k:result.get('quality',{}).get(k,'') for k in QUALITY})
    for phase in ['startup','parse','build','solve','verify']:
        row['phase_'+phase+'_seconds'] = result.get('phase_seconds',{}).get(phase,'')
    return row


def _campaign_jobs(folder, plan):
    seen = set()
    for task in plan['tasks']:
        for job_id in task['job_ids']:
            if job_id in seen:
                raise ValueError('duplicate job in campaign: ' + job_id)
            seen.add(job_id)
            job = {'id': job_id, 'family': task['family'], 'method': task['method'],
                   'task': 'decision' if task['family'] == 'smt' else 'optimization'}
            yield job, folder / 'runs' / task['key'] / 'jobs' / job_id / 'result.json'


def summarize(folder):
    """Write the same result columns for one run or a complete campaign."""
    folder = Path(folder)
    campaign = (folder / 'campaign.json').exists()
    summary = {}
    if campaign:
        plan = json.loads((folder / 'campaign.json').read_text())
        entries = _campaign_jobs(folder, plan)
        summary['configuration_jobs'] = len(plan['tasks'])
    else:
        jobs = json.loads((folder / 'run.json').read_text())['plan']['jobs']
        entries = ((job, folder / 'jobs' / job['id'] / 'result.json') for job in jobs)
    statuses = Counter()
    planned = 0
    with (folder / 'results.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for job, path in entries:
            result = json.loads(path.read_text()) if path.exists() else {'status': 'PENDING'}
            if campaign and path.exists() and (result['job_id'] != job['id'] or result['method'] != job['method']):
                raise ValueError('result belongs to a different configuration')
            writer.writerow(row_for(job, result))
            statuses[result['status']] += 1
            planned += 1
    summary.update(planned=planned, statuses=dict(statuses))
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    summarize(sys.argv[1])
