# NLIPSat package

This directory contains the installable NLIPSat solver and its Python API. For the formal experiment matrix, fixed dependencies and MatriCS setup, use [MATRICS_GUIDE.md](../MATRICS_GUIDE.md).

## Structure

- `main.py` is the single-model command-line entry.
- `encoders/` implements OH, UNA, BIN and decomposition.
- `solver/` contains encoding configuration and SAT/MaxSAT calls.
- `tools/` handles parsing, preprocessing, exact arithmetic and verification.
- `nlipsat/` exposes the Python API and installed command.
- `baselines/` contains direct-model baseline adapters.
- `examples/` contains a small JSON model and an API example.
- `tests/` contains core correctness and interface tests.
- `pyproject.toml` defines the installable package.

## Run one model

After setting up the project environment, execute from the repository root:

```bash
source matrics.env
"$AIJ_PYTHON" codes/main.py codes/examples/example4.json --preset mainline --verify
"$AIJ_PYTHON" codes/main.py --help
```

The example has original objective 2. The `mainline` preset selects BIN+D with RC2, exact multiplication, shared substructures and preprocessing, with LRN disabled. Formal experiment jobs select their own registered backends through `jobs/internal/experiment.py`.

To install the API and command in the same environment:

```bash
"$AIJ_PYTHON" -m pip install --no-deps -e ./codes
"$AIJ_PYTHON" -m nlipsat codes/examples/example4.json --preset mainline --verify
```

The dependency installation is covered in the MatriCS guide. Use `-s NONE -o output.wcnf` to export a formula without solving. JSON, QPLIB, bounded SMT-LIB2 and CNF inputs are supported. CNF with `--k 2` or larger represents a DiverseSAT optimization model. SMT translation rejects unsupported assertions and variables without justified finite bounds.

## Python API

Run from the repository root after installation:

```python
from nlipsat import load_problem, mainline_config, MAINLINE_SOLVER, build_wcnf, solve, verify_solution

problem = load_problem("codes/examples/example4.json")
cfg = mainline_config()
wcnf, name2idx, vpool = build_wcnf(problem, "BIN", cfg)
result = solve(problem, encoding=cfg.encoding, config=cfg, solver=MAINLINE_SOLVER)
ok, report = verify_solution(problem, result)
print(result["objective_value"], ok)  # 2 True
```

Successful results are checked against the original constraints and objective. Use `objective_value_exact` in the API or `OPTExact` in CLI output for exact objective values. `--no-preprocess` disables optional propagation and probing while preserving variable shifts and exact normalization.

## Core tests

From the repository root, using the configured environment:

```bash
"$AIJ_PYTHON" -m unittest discover -s codes/tests -v
"$AIJ_PYTHON" codes/tests/test_api.py
```
