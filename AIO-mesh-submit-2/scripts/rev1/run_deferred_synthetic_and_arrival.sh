#!/usr/bin/env bash
set -euo pipefail
cd /dis/users/dcs/CoreRouter
LOG_DIR=results/rev1/training_logs
mkdir -p "$LOG_DIR"
printf '%s\n' "$(date -Is) waiting for all three final synthetic checkpoints" >> "$LOG_DIR/deferred_runs.log"

for n in 25 50 100; do
  model="results/models/v11_synthetic_${n}/dgrl_v11_final_synthetic_${n}.zip"
  normalizer="results/models/v11_synthetic_${n}/vec_normalize_v11_synthetic_${n}.pkl"
  while [[ ! -s "$model" || ! -s "$normalizer" ]]; do
    if ! tmux -L harp_synthetic_sessions has-session -t "harp_synthetic_${n}" 2>/dev/null; then
      printf '%s\n' "$(date -Is) training session synthetic_${n} ended without final artifacts" >> "$LOG_DIR/deferred_runs.log"
      exit 1
    fi
    sleep 60
  done
done

for n in 25 50 100; do
  model="results/models/v11_synthetic_${n}/dgrl_v11_final_synthetic_${n}.zip"
  normalizer="results/models/v11_synthetic_${n}/vec_normalize_v11_synthetic_${n}.pkl"
  printf '%s\n' "$(date -Is) evaluating synthetic_${n}" >> "$LOG_DIR/deferred_runs.log"
  MPLCONFIGDIR="/tmp/mpl_syn_eval_${n}" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    ./venv/bin/python -u -m src.analytics.benchmark.benchmark_algorithm.run_all \
      --topology "synthetic_${n}" --scenario ablation --load stress --steps 3000 \
      --seeds 42 100 2024 8888 9999 7 17 73 314 2718 11 23 47 89 101 211 512 1024 4096 8192 \
      --skip-exhaustive --model-path "$model" --normalizer-path "$normalizer" \
      --output-dir results/rev1/synthetic_harp_benchmark \
      >> "$LOG_DIR/synthetic_${n}_benchmark.log" 2>&1
done

printf '%s\n' "$(date -Is) running arrival-rate-only sweep" >> "$LOG_DIR/deferred_runs.log"
MPLCONFIGDIR=/tmp/mpl_arrival_rate OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  ./venv/bin/python -u -m scripts.rev1.run_arrival_rate_sweep --topology all \
  >> "$LOG_DIR/arrival_rate_sweep.log" 2>&1
printf '%s\n' "$(date -Is) deferred synthetic evaluations and arrival-rate sweep complete" >> "$LOG_DIR/deferred_runs.log"
