# AIJ execution code

This directory is the only NLIPSat source tree used for new AIJ runs.

It was formed by a semantic review of the 12 Python files that differ between
the public-tool snapshot and the SAT 2026 experiment snapshot.  The two source
trees remain beside this directory as read-only provenance references.

Before a development change is accepted, run the following on the Guangzhou
Ubuntu execution host. On another site, use the interpreter selected in
`../jobs/config.cluster.json` instead of the Ubuntu environment path:

```bash
../.venv-solvers/bin/python tests/test_aij_semantics.py
../.venv-solvers/bin/python tests/test_api.py
```

`test_aij_semantics.py` checks exact and directional multiplication, exact SMT
Boolean lowering against Z3 under exhaustive assignments, all three integer
encodings, preprocessing with shifted bounds, hard-UNSAT status, verification,
and both WCNF export paths.

SMT parsing is strict by default.  Unsupported assertions and variables that
would need artificial finite bounds are rejected instead of being silently
relaxed.  This is required for all reported AIJ results.

The adopted single-instance entry is
`../.venv-solvers/bin/python codes/main.py INPUT --preset mainline` from this
directory. It selects complete BIN+D + RC2 with LRN disabled. Formal BIN+D
matrix jobs reuse the same encoding preset and runtime; their other backends
and the unshared decomposition comparison remain explicit matrix choices.

Runtime versions are pinned in `../jobs/requirements-core.txt` and
`../jobs/requirements-baselines.txt`. The current Ubuntu environment has passed
dependency checks and small-instance integration. Formal performance runs use
a committed execution tree and retain the protocol's CPU allocation,
3600-second total timeout and 16-GiB memory limit; cluster execution and full
CPLEX licensing require validation on the actual compute nodes.
