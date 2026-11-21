#!/usr/bin/env bash
set -u
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
pids=()
for topo in vietnam nsfnet geant2; do
 for chains in 0 25 50 100; do
  venv/bin/python scripts/rev1/run_seeded_load_chains.py --topology "$topo" --chains "$chains" --output "results/evidence/mentor_completion_20261121/seeded_load_chains/${topo}_${chains}" > "results/evidence/mentor_completion_20261121/logs/seeded_load_${topo}_${chains}.log" 2>&1 & pids+=("$!")
 done
done
status=0
for pid in "${pids[@]}"; do wait "$pid"; rc=$?; printf 'pid=%s exit=%s\n' "$pid" "$rc"; (( rc == 0 )) || status=1; done
exit "$status"
