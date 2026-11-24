"""SAT backend invocation shared by the experiment worker and baseline CLI."""
import subprocess
import tempfile
from pathlib import Path


def solve_cnf(clauses, backend='CADICAL', executable=None):
    if executable is None:
        from pysat.solvers import Solver
        name = {'CADICAL': 'cadical300', 'GLUCOSE': 'glucose42'}[backend]
        with Solver(name=name, bootstrap_with=clauses) as solver:
            sat = solver.solve()
            return sat, solver.get_model() if sat else None, None
    if backend != 'CADICAL':
        raise ValueError('external SAT executable is supported for CaDiCaL only')
    from pysat.formula import CNF
    with tempfile.TemporaryDirectory(prefix='nlip-cadical-') as directory:
        formula = Path(directory) / 'input.cnf'
        CNF(from_clauses=clauses).to_file(str(formula))
        command = [str(executable), str(formula)]
        process = subprocess.run(command, capture_output=True, text=True)
    status = None
    model = []
    for line in process.stdout.splitlines():
        if line.startswith('s '):
            status = line[2:].strip()
        elif line.startswith('v '):
            model.extend(int(value) for value in line[2:].split() if value != '0')
    if status == 'UNSATISFIABLE' and process.returncode == 20:
        return False, None, command
    if status != 'SATISFIABLE' or process.returncode != 10:
        raise ValueError(f'CaDiCaL status/exit mismatch: {status}, {process.returncode}; {process.stderr[-1000:]}')
    values = set(model)
    if any(-literal in values for literal in values) or any(not any(literal in values for literal in clause) for clause in clauses):
        raise ValueError('CaDiCaL returned a model that does not satisfy the CNF')
    return True, model, command
