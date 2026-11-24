"""Read every final input and check the native MIQP scope; no performance runs."""
from collections import Counter
from pathlib import Path
import argparse
import json
import sys
import contextlib
import io
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from internal.experiment import default_config, load_config, make_jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', type=Path, default=default_config())
    args = parser.parse_args()
    config = load_config(args.config)
    sys.path.insert(0,config['code_root'])
    from nlipsat import load_problem
    jobs=make_jobs(config,'formal','main',['qplib','diverse','mipo','smt'])
    result={'jobs':len(jobs),'by_family':dict(Counter(j['family'] for j in jobs)), 'inputs':{}}
    seen=set()
    for j in jobs:
        if j['input'] in seen: continue
        seen.add(j['input'])
        if j['family']=='smt':
            # SMT translation has its own semantic tests and per-run budget.
            report=result['inputs'].setdefault('smt',{'count':0,'check':'manifest inputs exist; representative solver tests run separately'})
            report['count']+=1
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            p=load_problem(j['input'],k=j.get('k'))
        report=result['inputs'].setdefault(j['family'],{'count':0,'degree_counts':{},'nonlinear_constraint_inputs':[]})
        report['count']+=1
        degree=max([sum(t.get('vars',{}).values()) for t in p.get('objective',{}).get('terms',[])]+[0])
        report['degree_counts'][str(degree)]=report['degree_counts'].get(str(degree),0)+1
        if j['family'] in ('qplib','diverse'):
            if any(c.get('type')=='disjunction' or any(sum(t.get('vars',{}).values())>1 for t in c.get('terms',c.get('lhs',[]))) for c in p.get('constraints',[])):
                report['nonlinear_constraint_inputs'].append(Path(j['input']).name)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
