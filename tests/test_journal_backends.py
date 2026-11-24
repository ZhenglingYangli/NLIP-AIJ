"""Independent small-domain oracles for the newly selected baselines."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'jobs'),str(ROOT/'codes'),str(ROOT/'codes/codes')]
from fractions import Fraction
from itertools import product
import copy
import json
import subprocess
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from solvers.baseline.integer_baselines import solve
from tools.verify import verify_values


def oracle(problem):
    names=list(problem['variables'])
    outcomes=[]
    for row in product(*(range(problem['variables'][n]['lb'],problem['variables'][n]['ub']+1) for n in names)):
        try:
            outcomes.append(verify_values(problem,dict(zip(names,row)))[0])
        except ValueError:
            pass
    if not outcomes:
        return None
    return (min if problem['objective']['sense']=='min' else max)(outcomes)


class NewBaselines(unittest.TestCase):
    def test_signed_fractional_polynomials_and_disjunctions(self):
        template={'variables':{'x':{'lb':-2,'ub':2},'y':{'lb':0,'ub':2}},
                  'objective':{'sense':'min','terms':[{'c':'1/2','vars':{'x':4}},
                     {'c':-3,'vars':{'x':1,'y':1}},{'c':'3/7','vars':{}}]},
                  'constraints':[]}
        variants=[[],[{'type':'disjunction','disjuncts':[
            [{'terms':[{'c':1,'vars':{'x':1}}],'rel':'<','rhs':0}],
            [{'terms':[{'c':1,'vars':{'x':1}},{'c':1,'vars':{'y':1}}],'rel':'>=','rhs':2}]]}],
            [{'terms':[{'c':1,'vars':{'x':2}}],'rel':'=','rhs':'1/2'}],
            [{'terms':[],'rel':'<=','rhs':-1}]]
        for backend in ('CP-SAT','GUROBI'):
            for sense in ('min','max'):
                for constraints in variants:
                    p=copy.deepcopy(template)
                    p['objective']['sense']=sense
                    p['constraints']=constraints
                    expected=oracle(p)
                    with self.subTest(backend=backend,sense=sense,constraints=constraints):
                        # Match the real runner: each backend has its own fresh
                        # process, so optional HiGHS libraries from other tests
                        # cannot override OR-Tools' bundled native libraries.
                        script = ('import sys,json; '
                                  f'sys.path[:0]={[str(ROOT/"codes"),str(ROOT/"codes/codes")]!r}; '
                                  'from solvers.baseline.integer_baselines import solve; '
                                  'p,b=json.loads(sys.stdin.read()); '
                                  'print(json.dumps(solve(p,b,60)))')
                        proc=subprocess.run([sys.executable,'-c',script],input=json.dumps([p,backend]),
                                            capture_output=True,text=True,timeout=75)
                        self.assertEqual(proc.returncode,0,proc.stderr)
                        result=json.loads(proc.stdout.splitlines()[-1])
                        self.assertEqual(result['status'],'UNSAT' if expected is None else 'OPTIMAL',result)
                        if expected is not None:
                            self.assertTrue(result['verified'])
                            self.assertEqual(Fraction(result['objective_exact']),expected)


class ExternalContracts(unittest.TestCase):
    def test_optimal_feasible_and_exit_code_conflicts(self):
        from pysat.formula import WCNF
        from solver.solve import solve_external
        w=WCNF();w.append([1]);w.append([-1],weight=2)
        cases=[('OPTIMUM FOUND',30,'OPTIMAL'),('SATISFIABLE',10,'FEASIBLE'),
               ('OPTIMUM FOUND',10,'INVALID'),('SATISFIABLE',30,'INVALID')]
        for declared,code,expected in cases:
            proc=SimpleNamespace(stdout=f'o 2\ns {declared}\nv 1 0\n',stderr='',returncode=code)
            with self.subTest(declared=declared,code=code), \
                 patch('solver.solve.subprocess.run',return_value=proc):
                result=solve_external(w,tempfile.gettempdir(),'/unused/solver',backend='UWRMAXSAT')
                self.assertEqual(result[2],expected)

    def test_actual_external_solvers_optimum_and_unsat(self):
        from pysat.formula import WCNF
        from solver.solve import solve_external
        import os
        cfg=Path(os.environ.get('AIJ_TEST_CONFIG',ROOT/'jobs/config.cluster.json'))
        if not cfg.exists():
            self.skipTest('requires the machine-specific solver configuration')
        config=json.loads(cfg.read_text())
        for backend in ('MAXHS','WMAXCDCL','UWRMAXSAT','EVALMAXRES'):
            path=config['solver_paths'].get(backend,'')
            if not Path(path).is_file():
                self.skipTest('requires actual external solver binaries')
            for unsat in (False,True):
                w=WCNF();w.append([1]);w.append([-1],weight=2)
                if unsat:w.append([-1])
                with self.subTest(backend=backend,unsat=unsat):
                    cost,assignment,status=solve_external(w,tempfile.gettempdir(),path,
                        backend=backend,solver_args=config.get('external_solver_args',{}).get(backend,[]),timeout=10)
                    self.assertEqual(status,'UNSAT' if unsat else 'OPTIMAL')
                    if not unsat:self.assertEqual(cost,2)


    def test_external_cadical_matches_boolean_enumeration(self):
        from solver.sat import solve_cnf
        import os
        cfg=Path(os.environ.get('AIJ_TEST_CONFIG',ROOT/'jobs/config.cluster.json'))
        if not cfg.exists(): self.skipTest('requires site configuration')
        path=json.loads(cfg.read_text())['solver_paths'].get('CADICAL')
        if not path or not Path(path).is_file(): self.skipTest('requires external CaDiCaL')
        cases=[[],[[]],[[1],[-1]],[[1,2],[-1,2],[1,-2]],[[5],[-7]]]
        for clauses in cases:
            variables=sorted({abs(lit) for clause in clauses for lit in clause})
            expected=any(all(any(values[abs(lit)]==(lit>0) for lit in clause) for clause in clauses)
                         for row in product((False,True),repeat=len(variables))
                         for values in [dict(zip(variables,row))])
            with self.subTest(clauses=clauses):
                sat,model,command=solve_cnf(clauses,'CADICAL',path)
                self.assertEqual(sat,expected)
                self.assertEqual(command[0],path)
                if sat:self.assertTrue(all(any(lit in model for lit in clause) for clause in clauses))

    def test_external_cadical_rejects_status_conflict_and_wrong_model(self):
        from solver.sat import solve_cnf
        for output,code in [('s SATISFIABLE\nv -1 0\n',10),
                            ('s SATISFIABLE\nv 1 0\n',20),
                            ('s UNSATISFIABLE\n',10)]:
            with self.subTest(output=output), patch('solver.sat.subprocess.run',
                    return_value=SimpleNamespace(stdout=output,stderr='',returncode=code)):
                with self.assertRaises(ValueError):solve_cnf([[1]],'CADICAL','/unused/cadical')


if __name__=='__main__':
    unittest.main(verbosity=2)
