#!/usr/bin/env bash
# Launch three independent HARP retrains on the CUDA devices selected by the operator.
set -euo pipefail
if [[ $# -ne 3 ]]; then
    printf 'Usage: %s VIETNAM_GPU NSFNET_GPU GEANT2_GPU\n' "$0" >&2
    exit 2
fi

cd "$(dirname "$0")/../.."
repo="$PWD"
python_bin="$repo/venv/bin/python"
data="$repo/data/real_telecom_combined.csv"
topologies=(vietnam nsfnet geant2)
gpu_devices=("$@")
command -v tmux >/dev/null
if ! command -v nvidia-smi >/dev/null; then
    printf 'nvidia-smi is unavailable. No retrain sessions were started.\n' >&2
    exit 1
fi
nvidia-smi --query-gpu=index,name,memory.total,memory.free,utilization.gpu --format=csv
free -h
df -h "$repo"
test -r "$data"
for gpu in "$@"; do
    CUDA_VISIBLE_DEVICES="$gpu" "$python_bin" -c '
import torch
import tensorboard
import sb3_contrib
if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
    raise SystemExit("Expected exactly one CUDA device for this job")
print("CUDA device:", torch.cuda.get_device_name(0))
'
done

run_dir="$(mktemp -d "$repo/results/models/retrain_$(date -u +%Y%m%dT%H%M%SZ)_XXXXXXXX")"
run_id="$(basename "$run_dir")"
printf 'Source commit: %s\n' "$(git rev-parse HEAD)" > "$run_dir/source.txt"
sha256sum "$data" src/analytics/training/train_v11.py \
    src/orchestration/jo_vdpr/{env,gnn_policy,rewards,topology}.py >> "$run_dir/source.txt"

for index in "${!topologies[@]}"; do
    topology="${topologies[index]}"
    gpu="${gpu_devices[index]}"
    session="${run_id}_${topology}"
    output="$run_dir/$topology"
    mkdir "$output"
    command_line=(
        env "CUDA_VISIBLE_DEVICES=$gpu" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
        "$python_bin" -u -m src.analytics.training.train_v11 --topology "$topology"
        --device cuda --total-steps 3000000 --seed 42 --n-envs 4 --rollout-steps 512
        --batch-size 64 --checkpoint-freq 100000 --data-path "$data" --model-dir "$output"
    )
    printf -v shell_command '%q ' "${command_line[@]}"
    printf '%s\n' "$shell_command" > "$output/command.txt"
    printf -v redirect ' >> %q 2>&1' "$output/train.log"
    tmux new-session -d -s "$session" -c "$repo" "exec $shell_command$redirect"
    printf '%s  %s\n' "$session" "$output/train.log"
done
