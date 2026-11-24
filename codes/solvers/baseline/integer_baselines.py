"""Direct bounded-integer polynomial models for CP-SAT and Gurobi.

Products use bounded auxiliary variables, not Boolean-product MILP expansion.
Every returned witness is checked against the original problem with exact arithmetic.
"""
from functools import reduce
from math import ceil, floor, gcd
import time

from solvers.baseline.scip_baseline import number, integer_polynomial, interval


class Unsupported(ValueError):
    pass


def solve(problem, backend, seconds, begin_verify=lambda: None):
    from telemetry import progress, quality
    started = time.monotonic()
    if backend not in ('CP-SAT', 'GUROBI'):
        raise ValueError(backend)
    if problem.get('objective', {}).get('factor_blocks'):
        return {'status': 'UNSUPPORTED', 'verified': False,
                'error': 'baseline requires an explicit polynomial objective'}
    bounds = {n: (ceil(number(v['lb'])), floor(number(v['ub'])))
              for n, v in problem['variables'].items()}
    if any(lo > hi for lo, hi in bounds.values()):
        return {'status': 'UNSAT', 'verified': False}
    cp = backend == 'CP-SAT'
    try:
        if cp:
            from ortools.sat.python import cp_model
            model = cp_model.CpModel()
            limit = (1 << 62) - 1
        else:
            import gurobipy as gp
            # Parameters are set on a private environment before license startup.
            env = gp.Env(empty=True)
            env.setParam('OutputFlag', 0)
            env.start()
            model = gp.Model('NLIP_native', env=env)
            model.Params.Threads = 1
            model.Params.Seed = 0
            model.Params.NonConvex = 2
            model.Params.MIPGap = 0
            model.Params.MIPGapAbs = 0
            model.Params.FeasibilityTol = 1e-9
            model.Params.IntFeasTol = 1e-9
            limit = 1 << 53

        def checked(v):
            if abs(v) > limit:
                raise Unsupported('UNSUPPORTED_NUMERIC_RANGE: model integer exceeds backend range')
            return int(v)

        def variable(lo, hi, name, binary=False):
            lo, hi = checked(lo), checked(hi)
            if cp:
                return model.new_bool_var(name) if binary else model.new_int_var(lo, hi, name)
            return model.addVar(lb=lo, ub=hi, vtype=gp.GRB.BINARY if binary else gp.GRB.INTEGER, name=name)

        original = {n: variable(lo, hi, n) for n, (lo, hi) in bounds.items()}
        products = {}

        def monomial(key):
            if not key:
                return 1
            if key in products:
                return products[key]
            factors = [n for n, power in key for _ in range(power)]
            value = original[factors[0]]
            lo, hi = bounds[factors[0]]
            for pos, name in enumerate(factors[1:], 1):
                a, b = bounds[name]
                endpoints = (lo*a, lo*b, hi*a, hi*b)
                lo, hi = min(endpoints), max(endpoints)
                out = variable(lo, hi, f'prod_{len(products)}_{pos}')
                if cp:
                    model.add_multiplication_equality(out, [value, original[name]])
                else:
                    model.addQConstr(out == value * original[name])
                value = out
            products[key] = value
            return value

        def expression(poly):
            lo, hi = interval(poly, bounds)
            checked(lo)
            checked(hi)
            return sum(checked(c) * monomial(key) for key, c in poly.items())

        selectors = 0

        def add_relation(relation, guard):
            if cp:
                row = model.add(relation)
                if guard is not None:
                    row.only_enforce_if(guard)
            elif guard is None:
                model.addConstr(relation)
            else:
                model.addGenConstrIndicator(guard, True, relation)

        def constraint(atom, guard=None):
            nonlocal selectors
            if atom.get('type') == 'disjunction':
                choices = []
                for branch in atom.get('disjuncts', []):
                    flag = variable(0, 1, f'branch_{selectors}', binary=True)
                    selectors += 1
                    choices.append(flag)
                    if guard is not None:
                        add_relation(flag <= guard, None)
                    for child in branch:
                        constraint(child, flag)
                add_relation(sum(choices) >= (1 if guard is None else guard), None)
                return
            poly, scale = integer_polynomial(atom.get('terms', atom.get('lhs', [])))
            rhs = number(atom.get('rhs', 0)) * scale - poly.pop((), 0)
            divisor = reduce(gcd, (abs(c) for c in poly.values()), 0) or 1
            poly = {key: c // divisor for key, c in poly.items()}
            rhs /= divisor
            # Keep a backend expression for constant and empty constraints too.
            expr = expression(poly) + 0 * next(iter(original.values())) if original else expression(poly)
            rel = atom.get('rel', atom.get('sense', '<='))
            if rel in ('<', '<='):
                add_relation(expr <= checked(ceil(rhs)-1 if rel == '<' else floor(rhs)), guard)
            elif rel in ('>', '>='):
                add_relation(expr >= checked(floor(rhs)+1 if rel == '>' else ceil(rhs)), guard)
            elif rel in ('=', '=='):
                add_relation(expr <= checked(floor(rhs)), guard)
                add_relation(expr >= checked(ceil(rhs)), guard)
            else:
                raise Unsupported('unsupported relation ' + rel)

        for atom in problem.get('constraints', []):
            constraint(atom)
        objective = problem.get('objective', {})
        poly, scale = integer_polynomial(objective.get('terms', []))
        constant = poly.pop((), 0)
        divisor = reduce(gcd, (abs(c) for c in poly.values()), 0) or 1
        poly = {key: c // divisor for key, c in poly.items()}
        expr = expression(poly)
        minimize = objective.get('sense', 'max').lower() in ('min', 'minimize')
        if cp:
            (model.minimize if minimize else model.maximize)(expr)
            invalid = model.validate()
            if invalid:
                raise Unsupported('CP-SAT model validation: ' + invalid)
        else:
            model.setObjective(expr, gp.GRB.MINIMIZE if minimize else gp.GRB.MAXIMIZE)
        build = time.monotonic() - started
        stats = {'route': 'native-polynomial-products', 'products': len(products),
                 'objective_scale': scale, 'objective_constant': constant, 'objective_divisor': divisor}
        progress('solve', formula=stats, solver_timings={'build': build})
        remaining = seconds - build
        if remaining <= 0:
            return {'status': 'TIMEOUT', 'verified': False}
        if cp:
            solver = cp_model.CpSolver()
            solver.parameters.num_search_workers = 1
            solver.parameters.random_seed = 0
            solver.parameters.max_time_in_seconds = remaining
            status = solver.solve(model)
            if status == cp_model.MODEL_INVALID:
                raise Unsupported(solver.solution_info())
            optimal, feasible = status == cp_model.OPTIMAL, status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            infeasible = status == cp_model.INFEASIBLE
            backend_status = solver.status_name(status)
            values = {n: solver.value(v) for n, v in original.items()} if feasible else None
            bound = solver.best_objective_bound if status != cp_model.UNKNOWN else None
            encoded_objective = solver.value(expr) if feasible else None
            nodes = solver.num_branches
        else:
            model.Params.TimeLimit = remaining
            model.optimize()
            optimal, feasible = model.Status == gp.GRB.OPTIMAL, model.SolCount > 0
            infeasible = model.Status == gp.GRB.INFEASIBLE
            backend_status = str(model.Status)
            raw = {n: v.X for n, v in original.items()} if feasible else {}
            values = {n: round(v) for n, v in raw.items()} if feasible else None
            if any(abs(raw[n]-values[n]) > 1e-6 for n in raw):
                raise ValueError('nonintegral original witness')
            encoded_objective = model.ObjVal if feasible else None
            bound = model.ObjBound if model.Status not in (gp.GRB.INF_OR_UNBD, gp.GRB.UNBOUNDED) else None
            nodes = model.NodeCount
        solved = time.monotonic()
        result = {'status': 'UNSAT' if infeasible else 'UNKNOWN', 'verified': False,
                  'backend_status': backend_status, 'formula': stats,
                  'solver_timings': {'build': build, 'solve': solved-started-build}}
        result['quality'] = quality(stats, encoded_objective, bound, None, nodes)
        progress(quality=result['quality'])
        if feasible:
            begin_verify()
            from tools.verify import verify_values
            value, checks, source = verify_values(problem, values)
            encoded = (number(value)*scale-constant)/divisor
            if (cp and encoded != encoded_objective) or (not cp and abs(float(encoded)-encoded_objective) > 1e-6):
                raise ValueError('backend objective disagrees with original objective')
            result.update(status='OPTIMAL' if optimal else 'FEASIBLE', verified=True,
                          objective_exact=str(value), witness=values,
                          verification={'constraint_checks': checks, 'source_smt_verified': source})
            result['solver_timings']['verify'] = time.monotonic()-solved
        elif not infeasible and ((cp and status == cp_model.UNKNOWN) or
                                 (not cp and model.Status == gp.GRB.TIME_LIMIT)):
            result['status'] = 'TIMEOUT'
        return result
    except Unsupported as exc:
        return {'status': 'UNSUPPORTED', 'verified': False, 'error': str(exc)}
    except Exception as exc:
        if not cp and getattr(exc, 'errno', None) in (10009, 10010):
            return {'status': 'LICENSE_LIMIT', 'verified': False, 'error': str(exc)}
        raise
    finally:
        if not cp:
            if 'model' in locals():
                model.dispose()
            if 'env' in locals():
                env.dispose()
