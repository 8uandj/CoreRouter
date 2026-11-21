#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
export CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
root=results/evidence/mentor_completion_20261121/independent_training
venv/bin/python -c 'import torch; assert torch.cuda.is_available(); print("CUDA:",torch.cuda.get_device_name(0),flush=True)'
for seed in 7 2024; do
 out="$root/matched_seed_$seed"
 mkdir -p "$out"
 printf '%s\n' "venv/bin/python -m src.analytics.training.train_v11 --topology vietnam --device cuda --total-steps 2001920 --seed $seed --n-envs 4 --rollout-steps 512 --batch-size 32 --checkpoint-freq 100000 --data-path data/real_telecom_combined.csv --model-dir $out" > "$out/command.txt"
 git rev-parse HEAD > "$out/source_commit.txt"
 sha256sum data/real_telecom_combined.csv src/analytics/training/train_v11.py src/orchestration/jo_vdpr/{env,gnn_policy,rewards,topology}.py > "$out/source_sha256.txt"
 venv/bin/python -u -m src.analytics.training.train_v11 --topology vietnam --device cuda --total-steps 2001920 --seed "$seed" --n-envs 4 --rollout-steps 512 --batch-size 32 --checkpoint-freq 100000 --data-path data/real_telecom_combined.csv --model-dir "$out" > "$out/train.log" 2>&1
 printf 'seed=%s completed\n' "$seed"
done
