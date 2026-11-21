#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
while tmux -L harp_mentor_completion_20261121 has-session -t '=independent_train' 2>/dev/null; do sleep 60; done
for seed in 7 2024; do
 out="results/evidence/mentor_completion_20261121/independent_training/matched_seed_$seed"
 test -s "$out/dgrl_v11_final_vietnam.zip" && test -s "$out/vec_normalize_v11_vietnam.pkl" || { printf 'missing finished model/normalizer for seed %s\n' "$seed"; exit 1; }
done
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
exec venv/bin/python -u scripts/rev1/evaluate_independent_training.py
