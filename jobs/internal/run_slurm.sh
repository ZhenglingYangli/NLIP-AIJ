#!/usr/bin/env bash
#SBATCH --job-name=nlip-aij
#SBATCH --partition=bigmem-amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=nlip-%j.log
set -euo pipefail
if [[ -n "${AIJ_RUNNER_DIR:-}" ]]; then
    cd "$AIJ_RUNNER_DIR/.."
else
    cd "${SLURM_SUBMIT_DIR:?Submit from the project root}"
fi
: "${AIJ_PYTHON:?Submit through the generated submit.sh}"
NLIP_PYTHON="$AIJ_PYTHON"
echo "host=$(hostname) job=${SLURM_JOB_ID:-local}"
if [[ -n "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    exec "$NLIP_PYTHON" -u jobs/goSolver.py --campaign "${AIJ_CAMPAIGN:?}" --index "$SLURM_ARRAY_TASK_ID"
fi
exec "$NLIP_PYTHON" -u jobs/goSolver.py test "$@" --config "${AIJ_CONFIG:-jobs/config.cluster.json}"
