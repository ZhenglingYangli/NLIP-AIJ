from pathlib import Path
import sys
_PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(_PROJECT/'jobs'),str(_PROJECT/'analysis'),str(_PROJECT/'codes')]
"""Configuration splitting must cover the frozen matrix exactly once."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1] / 'jobs'
sys.path.insert(0,str(ROOT))
from internal.experiment import configuration_tasks, job_ids, load_config, make_jobs, manifest_names, default_config
from internal.runner import resume_compatible
from summarize import summarize

class Campaign(unittest.TestCase):
    def test_manifest_filtering_and_job_numbering_agree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'inputs.txt').write_text('# inputs\n\n first.json \n  # note\n second.json\n')
            for name in ('first.json', 'second.json'):
                (root / name).write_text('{}')
            config = {'manifest_root': str(root), 'benchmark_root': str(root),
                      'code_root': str(root), 'solver_paths': {},
                      'profiles': {'formal': {'solve_seconds': 3600}},
                      'families': {'qplib': {'task': 'optimization', 'manifest': 'inputs.txt',
                                            'directory': '.', 'extension': '.json'}}}
            self.assertEqual(manifest_names(config, 'qplib'), ['first.json', 'second.json'])
            tasks = configuration_tasks(config, 'formal', 'main')
            jobs = make_jobs(config, 'formal', 'main', ['qplib'])
            self.assertEqual(len(jobs), 32)
            self.assertEqual({job['id'] for job in jobs},
                             {job_id for task in tasks for job_id in task['job_ids']})
            expected = ['qplib-0001-bin-wmaxcdcl', 'qplib-0002-bin-wmaxcdcl']
            self.assertEqual(job_ids('qplib', 'bin-wmaxcdcl', 2), expected)
            self.assertEqual([job['id'] for job in jobs if job['method']['id'] == 'bin-wmaxcdcl'], expected)

    def test_resume_on_equivalent_node(self):
        first={'host':'node1','cpus':[0,1],'cpu_model':['same CPU'],'platform':'Linux',
               'workers':2,'versions':{'solver':'1'},'jobs':['a','b']}
        second={**first,'host':'node2','cpus':[4,5]}
        self.assertTrue(resume_compatible(first,second))
        self.assertFalse(resume_compatible(first,{**second,'cpu_model':['different CPU']}))
        self.assertFalse(resume_compatible(first,{**second,'workers':3}))
        self.assertFalse(resume_compatible(first,{**second,'jobs':['a','c']}))

    def test_partition_matches_full_matrix(self):
        c=load_config(os.environ.get('AIJ_TEST_CONFIG', default_config()))
        main=configuration_tasks(c,'formal','main')
        ids=[j for t in main for j in t['job_ids']]
        expected=make_jobs(c,'formal','main',list(c['families']))
        self.assertEqual(len(main),58)
        self.assertEqual(len(ids),22220)
        self.assertEqual(len(set(ids)),len(ids))
        self.assertEqual(set(ids),{j['id'] for j in expected})
        extra=configuration_tasks(c,'formal','decomposition')
        other={j for t in extra for j in t['job_ids']}
        self.assertEqual(len(extra),2)
        self.assertEqual(len(other),1020)
        self.assertFalse(other.intersection(ids))
        self.assertTrue(all(not t['method']['options']['use_lrn'] for t in main+extra if 'encoding' in t['method']))

    def test_summary_preserves_missing_results(self):
        c=load_config(os.environ.get('AIJ_TEST_CONFIG', default_config()))
        tasks=configuration_tasks(c,'smoke','main')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'campaign.json').write_text(json.dumps({'tasks':tasks}))
            task=tasks[0]; job_id=task['job_ids'][0]
            out=root/'runs'/task['key']/'jobs'/job_id
            out.mkdir(parents=True)
            (out/'result.json').write_text(json.dumps({'job_id':job_id,'method':task['method'],'status':'OPTIMAL','verified':True}))
            result=summarize(root)
            self.assertEqual(result['planned'],58)
            self.assertEqual(result['statuses'],{'OPTIMAL':1,'PENDING':57})

    def test_single_and_campaign_tables_agree(self):
        # Both entry paths must preserve failed and missing runs and exact values.
        method = {'id': 'bin-wmaxcdcl', 'encoding': 'BIN', 'solver': 'WMAXCDCL'}
        jobs = [{'id': f'qplib-{i}-bin-wmaxcdcl', 'family': 'qplib',
                 'task': 'optimization', 'method': method} for i in range(3)]
        with tempfile.TemporaryDirectory() as temporary:
            single = Path(temporary) / 'single'
            campaign = Path(temporary) / 'campaign'
            single.mkdir(); campaign.mkdir()
            (single / 'run.json').write_text(json.dumps({'plan': {'jobs': jobs}}))
            task = {'key': 'qplib-bin-wmaxcdcl', 'family': 'qplib', 'method': method,
                    'job_ids': [job['id'] for job in jobs]}
            (campaign / 'campaign.json').write_text(json.dumps({'tasks': [task]}))
            for job, status in zip(jobs, ['OPTIMAL', 'TIMEOUT']):
                result = {'job_id': job['id'], 'method': method, 'status': status,
                          'verified': status == 'OPTIMAL', 'objective_exact': '1/3' if status == 'OPTIMAL' else None,
                          'solve_wall_seconds': 2, 'formula': {'variables': 3, 'hard': 4}}
                for base in [single, campaign / 'runs' / task['key']]:
                    path = base / 'jobs' / job['id']
                    path.mkdir(parents=True)
                    (path / 'result.json').write_text(json.dumps(result))
            one = summarize(single)
            many = summarize(campaign)
            expected = {'OPTIMAL': 1, 'TIMEOUT': 1, 'PENDING': 1}
            self.assertEqual(one['statuses'], expected)
            self.assertEqual(many['statuses'], expected)
            self.assertEqual(one['planned'], many['planned'])
            self.assertEqual((single / 'results.csv').read_bytes(), (campaign / 'results.csv').read_bytes())
            path = campaign / 'runs' / task['key'] / 'jobs' / jobs[0]['id'] / 'result.json'
            bad = json.loads(path.read_text()); bad['method'] = {'id': 'wrong'}
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'different configuration'):
                summarize(campaign)

if __name__=='__main__': unittest.main(verbosity=2)
