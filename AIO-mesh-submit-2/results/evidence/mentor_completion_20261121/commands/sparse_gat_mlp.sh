#!/usr/bin/env bash
set -u
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
pids=()
for topo in vietnam nsfnet geant2; do
 venv/bin/python scripts/rev1/run_sparse_gat_mlp.py --topology "$topo" --output "results/evidence/mentor_completion_20261121/sparse_gat_mlp/$topo" > "results/evidence/mentor_completion_20261121/logs/sparse_gat_mlp_$topo.log" 2>&1 & pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do wait "$pid"; rc=$?; printf 'pid=%s exit=%s\n' "$pid" "$rc"; (( rc == 0 )) || status=1; done
exit "$status"
