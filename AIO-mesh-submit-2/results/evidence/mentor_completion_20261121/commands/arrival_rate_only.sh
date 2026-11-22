#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
root=AIO-mesh-submit-2/results/evidence/mentor_completion_20261121/arrival_rate_only
mkdir -p "$root"
git rev-parse HEAD > "$root/source_commit.txt"
sha256sum AIO-mesh-submit-2/scripts/rev1/run_arrival_rate_sweep.py AIO-mesh-submit-2/src/analytics/benchmark/benchmark_algorithm/algorithms.py AIO-mesh-submit-2/data/real_telecom_combined.csv > "$root/source_sha256.txt"
printf '%s\n' 'venv/bin/python -u AIO-mesh-submit-2/scripts/rev1/run_arrival_rate_sweep.py --topology all --output-dir AIO-mesh-submit-2/results/evidence/mentor_completion_20261121/arrival_rate_only' > "$root/command.txt"
exec venv/bin/python -u AIO-mesh-submit-2/scripts/rev1/run_arrival_rate_sweep.py --topology all --output-dir "$root"
