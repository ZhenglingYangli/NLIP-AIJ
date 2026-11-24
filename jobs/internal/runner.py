"""Execute a prepared instance list with shared budgets, resume and verification."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
from queue import Queue
import signal
import subprocess
import threading

from internal.experiment import ROOT


def available_cpus():
    import psutil
    found = {}
    for cpu in psutil.Process().cpu_affinity():
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        try:
            key = ((topology / 'physical_package_id').read_text().strip(),
                   (topology / 'core_id').read_text().strip())
        except OSError:
            key = ('logical', cpu)
        found.setdefault(key, cpu)
    return list(found.values())


def git_identity(code, executable='git'):
    def git(*args):
        return subprocess.check_output([executable, '-C', code, *args], text=True).strip()
    return {'commit': git('rev-parse', 'HEAD'),
            'dirty': bool(git('status', '--porcelain', '--', code))}




def resume_compatible(previous, current):
    if previous.get('cpu_model'):
        def comparable(value):
            return {k:v for k,v in value.items() if k not in ('host', 'cpus')}
        return comparable(previous) == comparable(current)
    return previous == {k:v for k,v in current.items() if k != 'cpu_model'}


def run_jobs(config, jobs, *, profile, matrix, workers, output=None, resume=False,
             code_version=None, runner_version=None):
    """Run the selected jobs; Slurm passes the identities prepared on its login node."""
    limits = config['profiles'][profile]
    if os.name != 'posix':
        raise ValueError('execution requires Linux; edit/run this package on the Ubuntu or cluster host')
    import psutil
    from internal.supervisor import supervise
    cpus = available_cpus()
    if workers < 1 or workers > len(cpus):
        raise ValueError(f'workers must be between 1 and {len(cpus)} available distinct cores')
    memory = psutil.virtual_memory().available
    if os.environ.get('SLURM_MEM_PER_NODE'):
        memory = min(memory, int(os.environ['SLURM_MEM_PER_NODE']) * 1024**2)
    cgroup = Path('/sys/fs/cgroup/memory.max')
    if cgroup.exists() and cgroup.read_text().strip() != 'max':
        memory = min(memory, int(cgroup.read_text()))
    needed = (workers * limits['memory_gib'] + .5) * 1024**3
    if memory < needed:
        raise ValueError(f'need {needed/1024**3:.1f} GiB including runner reserve; available/allocation {memory/1024**3:.1f} GiB')
    selected = {j['method']['solver'] for j in jobs}
    external = selected & {'MAXHS', 'WMAXCDCL', 'UWRMAXSAT', 'EVALMAXRES', 'OPENWBO', 'CADICAL'}
    absent = external - set(config['solver_paths'])
    if absent:
        raise ValueError('missing solver paths: ' + ', '.join(sorted(absent)))
    for solver in external:
        if not os.access(config['solver_paths'][solver], os.X_OK):
            raise ValueError(f'{solver} binary is missing or not executable: {config["solver_paths"][solver]}')
    if code_version is not None:
        identity = code_version
        execution_identity = runner_version
    elif profile in ('smoke', 'pilot'):
        # Small diagnostics do not require Git on the compute node.
        identity = execution_identity = {'commit': None, 'dirty': None}
    else:
        identity = git_identity(config['code_root'], config['git'])
        execution_identity = git_identity(str(ROOT), config['git'])
    if profile == 'formal' and (identity['dirty'] or execution_identity['dirty']):
        raise ValueError('commit both the active solver and experiment runner code before a formal batch')
    versions = subprocess.check_output([config['python'], '-c',
        "import importlib.metadata as m,json,sys; print(json.dumps({'python':sys.version, **{p:m.version(p) for p in ['python-sat','pindakaas','z3-solver','psutil']}}))"], text=True)
    versions = json.loads(versions)
    if any(j['method']['solver'].startswith('SCIP') for j in jobs):
        scip_version = subprocess.check_output([config['python'], '-c',
            "import pyscipopt as b,json,numpy; m=b.Model(); print(json.dumps({'pyscipopt':b.__version__, 'numpy':numpy.__version__, 'scip':f'{m.getMajorVersion()}.{m.getMinorVersion()}.{m.getTechVersion()}'}))"], cwd=ROOT, text=True)
        versions.update(json.loads(scip_version))
    if any(j['method']['solver'] == 'CVC5' for j in jobs):
        versions['cvc5'] = subprocess.check_output([config['python'], '-c',
            'import cvc5; print(cvc5.__version__)'], cwd=ROOT, text=True).strip()
    for package, solver in [('ortools', 'CP-SAT'), ('gurobipy', 'GUROBI')]:
        if solver in selected:
            versions[package] = subprocess.check_output([config['python'], '-c',
                f'import importlib.metadata as m; print(m.version({package!r}))'], text=True).strip()
    external_identity = {}
    for solver in external:
        path = Path(config['solver_paths'][solver])
        stat = path.stat()
        info = config.get('solver_metadata', {}).get(solver, {})
        if profile == 'formal' and (not info.get('release') or not info.get('mode')):
            raise ValueError(f'{solver}: record solver_metadata release and mode in the site config before a formal run')
        external_identity[solver] = dict(info, path=str(path), realpath=str(path.resolve()),
            size=stat.st_size, modified_ns=stat.st_mtime_ns,
            arguments=config.get('external_solver_args', {}).get(solver, []))
    versions['external_solvers'] = external_identity
    if profile == 'formal' and 'GUROBI' in selected:
        probe = '''import gurobipy as gp
with gp.Env(params={'OutputFlag':0}) as env, gp.Model(env=env) as m:
 m.Params.Threads=1
 m.Params.TimeLimit=2
 x=m.addVars(2001,vtype=gp.GRB.BINARY)
 m.addConstr(x.sum()<=1)
 m.setObjective(x.sum(),gp.GRB.MAXIMIZE)
 m.optimize()
'''
        subprocess.run([config['python'], '-c', probe], check=True, timeout=30)
    cpu_model = sorted({line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                        if line.startswith('model name')})
    snapshot = {'config': config, 'profile': profile, 'matrix': matrix, 'jobs': jobs,
                'workers': workers, 'cpus': cpus[:workers], 'code': identity,
                'execution_code': execution_identity,
                'versions': versions, 'host': platform.node(), 'platform': platform.platform(), 'cpu_model': cpu_model}
    output = (output or ROOT / '../results' /
              (profile + '-' + matrix + '-' + datetime.now().strftime('%Y%m%d-%H%M%S'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    import fcntl
    run_lock = (output / '.runner.lock').open('a')
    try:
        fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('another runner is already using this output directory')
    planfile = output / 'run.json'
    if planfile.exists():
        if not resume:
            raise ValueError('output already contains a run; use --resume or choose another output directory')
        previous = json.loads(planfile.read_text())['plan']
        # Cluster requeues can use another node of the same hardware class.
        if not resume_compatible(previous, snapshot):
            raise ValueError('resume requires the same code, configuration, CPU model, platform, versions and inputs')
    else:
        if resume:
            raise ValueError('no existing run.json to resume')
        planfile.write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(),
                                       'plan': snapshot}, ensure_ascii=False, indent=2))
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    cpu_queue = Queue()
    for cpu in cpus[:workers]:
        cpu_queue.put(cpu)

    def run(job):
        if stop.is_set():
            return None
        folder = output / 'jobs' / job['id']
        resultfile = folder / 'result.json'
        if resultfile.exists():
            return json.loads(resultfile.read_text())
        cpu = cpu_queue.get()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            payload = dict(job, cpu=cpu)
            jobfile = folder / 'job.json'
            jobfile.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            command = [config['python'], '-u', str(ROOT / 'internal/worker.py'), str(jobfile)]
            result = supervise(command, folder, limits, stop)
            if result['status'] == 'INTERRUPTED':
                return None
            result.update(job_id=job['id'], family=job['family'], task=job['task'],
                          input=job['input'], method=job['method'], cpu=cpu, command=command,
                          host=platform.node(), cpu_model=cpu_model)
            temporary = folder / 'result.json.tmp'
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            temporary.replace(resultfile)
            print(job['id'], result['status'], result.get('objective_exact'), flush=True)
            return result
        finally:
            cpu_queue.put(cpu)

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(run, job) for job in jobs]
    try:
        for future in as_completed(futures):
            future.result()
    except KeyboardInterrupt:
        stop.set()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    subprocess.run([config["python"], str(ROOT.parent / "sumup/summarize.py"), str(output)], check=True)
    print('Results:', output)
    if profile in ('smoke', 'pilot'):
        from internal.testing import check_results
        if not check_results(output, jobs):
            raise ValueError('test acceptance failed; see ' + str(output / 'test-result.txt'))
    return output
