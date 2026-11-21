#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
for topo in vietnam nsfnet geant2; do
 for load in 1.2 1.5; do
  venv/bin/python scripts/rev1/run_oracle_load_refresh.py --topology "$topo" --load "$load" --output "results/evidence/mentor_completion_20261121/oracle/${topo}_${load}" > "results/evidence/mentor_completion_20261121/logs/oracle_${topo}_${load}.log" 2>&1 &
 done
done
wait
