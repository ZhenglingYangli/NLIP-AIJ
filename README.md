# NLIP-AIJ experiment artifact

Read [MATRICS_GUIDE.md](MATRICS_GUIDE.md) for the experiment matrix, fixed solver versions and arguments, installation, submission and result collection. First-time operators start at section 4.

The main experiment contains **1,265 inputs, 58 configurations and 22,220 runs** across QPLIB, DiverseSAT application models, MIPO and bounded SMT. LRN is disabled. A separate decomposition-sharing ablation contains 1,020 runs.

## Layout

```text
MATRICS_GUIDE.md        Complete MatriCS operating guide
matrics.env.example    Paths, modules and license settings to fill in
jobs/                  Experiment generation and execution
  generate_scripts.py  Generate the Slurm campaign and submit.sh
  goSolver.py          Run instances and supervise resources
  internal/            Shared matrix, scheduling and solver dispatch
  tools/               Site configuration and environment checks
  data/                MIPO input preparation
  smoke/               Four small models with known answers
codes/                 Installable NLIPSat package and core tests
benchmarks/manifests/   Fixed instance lists
analysis/              Result aggregation, plots and export
tests/                 Experiment runner and analysis tests
```

## Run on MatriCS

Follow the guide to copy and edit `matrics.env.example`, install the solvers and generate `jobs/config.cluster.json`. Then, from the project root:

```bash
source matrics.env
"$AIJ_PYTHON" jobs/generate_scripts.py --profile smoke --output results/smoke-new-solvers
bash results/smoke-new-solvers/submit.sh
```

After the compute-node checks and all 58 small-test configurations pass:

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main-new-solvers
bash results/main-new-solvers/submit.sh
```

The generated submission script saves job IDs and schedules analysis after the array finishes. Raw records and summary tables are written under `results/<campaign>/`. Local configuration, environments, external solver binaries, full datasets, licenses and results are excluded from Git.

For individual models and the Python API, see [codes/README.md](codes/README.md).
