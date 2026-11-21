#!/usr/bin/env bash
set -uo pipefail
cd /dis/users/dcs/CoreRouter
out=results/evidence/completion_20261121/reruns
export AIOMESH_PYTHON=venv/bin/python OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
scripts/rerun_cell.sh --exp benchmark --topo vietnam --workload burst_surge --seed 42 --model results/models/retrain_v11_20261119_corrected/vietnam/dgrl_v11_final_vietnam.zip --normalizer results/models/retrain_v11_20261119_corrected/vietnam/vec_normalize_v11_vietnam.pkl --out "$out/benchmark" > "$out/../logs/benchmark.log" 2>&1 & p1=$!
scripts/rerun_cell.sh --exp ablation --topo nsfnet --workload chaos --seed 7 --out "$out/ablation" > "$out/../logs/ablation.log" 2>&1 & p2=$!
scripts/rerun_cell.sh --exp load_sweep --topo geant2 --load 1.2 --seed 2024 --model results/models/retrain_v11_20261119_corrected/geant2/dgrl_v11_final_geant2.zip --normalizer results/models/retrain_v11_20261119_corrected/geant2/vec_normalize_v11_geant2.pkl --out "$out/load" > "$out/../logs/load.log" 2>&1 & p3=$!
for p in "$p1" "$p2" "$p3"; do wait "$p"; printf 'pid=%s exit=%s\n' "$p" "$?"; done
