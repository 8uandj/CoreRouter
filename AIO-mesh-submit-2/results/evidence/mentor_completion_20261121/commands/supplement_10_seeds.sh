#!/usr/bin/env bash
set -u
cd /dis/users/dcs/CoreRouter
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
root=results/evidence/mentor_completion_20261121
supp="$root/supplement_10_seeds"
pids=()
for topo in vietnam nsfnet geant2; do
 for kind in seeded_bursty saf_weight_sensitivity sparse_gat_mlp; do
  case "$kind" in seeded_bursty) script=run_seeded_bursty;; saf_weight_sensitivity) script=run_saf_weight_sensitivity;; sparse_gat_mlp) script=run_sparse_gat_mlp;; esac
  venv/bin/python "$supp/scripts/$script.py" --topology "$topo" --output "$supp/$kind/$topo" > "$root/logs/supp_${kind}_${topo}.log" 2>&1 & pids+=("$!")
 done
 for chains in 0 25 50 100; do
  venv/bin/python "$supp/scripts/run_seeded_load_chains.py" --topology "$topo" --chains "$chains" --output "$supp/seeded_load_chains/${topo}_${chains}" > "$root/logs/supp_load_${topo}_${chains}.log" 2>&1 & pids+=("$!")
 done
done
status=0
for pid in "${pids[@]}"; do wait "$pid"; rc=$?; printf 'pid=%s exit=%s\n' "$pid" "$rc"; ((rc == 0)) || status=1; done
exit "$status"
