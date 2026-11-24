# NLIP-AIJ experiment artifact

The main matrix contains 1,265 inputs, 58 family/method configurations and 22,220 instance runs. QPLIB, DiverseSAT application models and MIPO compare OH/UNA/BIN, with BIN+D additionally on MIPO, using MaxHS, WMaxCDCL, UWrMaxSAT and EvalMaxRes. Optimization baselines are SCIP-native, Z3, CP-SAT and Gurobi. Bounded SMT uses four encodings with CaDiCaL, plus Z3 and cvc5. LRN is disabled.

Start with the [complete experiment and MatriCS handbook](docs/EXPERIMENT_HANDBOOK.md), covering the matrix, solver versions, source layout, installation and step-by-step operation.

## Two operator files

- `jobs/generate_scripts.py` checks dependencies and generates the Slurm campaign and submission script.
- `jobs/goSolver.py` runs instances, using the shared time/memory supervision and original-problem verification.

This retains the original generator/runner division. Slurm calls `goSolver.py` automatically. The generated `submit.sh` submits the array and dependent analysis and saves both job IDs. Resource supervision and solver dispatch remain internal modules. NLIP parsing, encoding and solving are timed together.

```bash
# Select the actual interpreter and configure this machine first.
export AIJ_PYTHON="$PWD/.venv-solvers/bin/python"
"$AIJ_PYTHON" jobs/tools/configure_cluster.py
"$AIJ_PYTHON" jobs/tools/check_environment.py
"$AIJ_PYTHON" jobs/generate_scripts.py --profile smoke --output results/smoke-new-solvers
bash results/smoke-new-solvers/submit.sh
# Inspect the computing-node test log before formal submission.
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main-new-solvers
bash results/main-new-solvers/submit.sh
sacct -j "$(cat results/main-new-solvers/array_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
```

The formal allocation is bigmem-amd, one exclusive node per configuration, 60 physical cores, 970 GiB and one active configuration at a time. Each instance receives one core, 16 GiB and 3,600 seconds for startup through solving, followed by up to 120 seconds for original-problem verification. The outer cap is 4,000 seconds. Results distinguish optimal, feasible, timeout, memory limit, invalid, license and unsupported outcomes.

See [solver versions and configuration](docs/SOLVER_VERSIONS.md), [code and experiment overview](docs/CODE_GUIDE.md), [experiment setup](jobs/README.md), [step-by-step cluster handoff](docs/COLLABORATOR_GUIDE.md) and [solver installation and API](codes/README.md).

## Development and handoff

The Guangzhou development directory is `/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ`. The separate Ubuntu checkout `/home/ubuntu/NLIP-Journal-Artifact-publish` is used to prepare GitHub delivery. Collaborators pull that repository into `/scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-` on MatriCS. These are stages of one delivery chain, not separate experiments.

Site-specific `jobs/config.cluster.json`, Python environments, solver binaries, licenses, raw benchmarks and results stay on their respective machines. Synchronizing source code does not copy those site settings. Formal plans must be generated on MatriCS after pulling the intended commit and completing the computing-node checks.

Raw records are under `results/<campaign>/runs/`, the combined table is `results.csv`, legacy-format tables are in `sumup/` and comparisons/plots are in `analysis/`. Historical formal LRN records are not modified by this experiment.
