#!/usr/bin/env bash
# Re-run a single simulator cell. The results do not overwrite the archived runs.
set -euo pipefail
cd "$(dirname "$0")/.."
exp= topo= workload= seed= load= model= normalizer=
out=results/rerun
while (( $# )); do
    case "$1" in
        --exp) exp="$2";;
        --topo) topo="$2";;
        --workload) workload="$2";;
        --seed) seed="$2";;
        --load) load="$2";;
        --model) model="$2";;
        --normalizer) normalizer="$2";;
        --out) out="$2";;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2;;
    esac
    shift 2
done
: "${exp:?--exp is required}" "${topo:?--topo is required}" "${seed:?--seed is required}"
data=data/real_telecom_combined.csv
python_bin="${AIOMESH_PYTHON:-venv/bin/python}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
case "$exp" in
    benchmark)
        : "${workload:?--workload is required}"
        args=()
        [[ -z "$model" ]] || args+=(--model-path "$model")
        [[ -z "$normalizer" ]] || args+=(--normalizer-path "$normalizer")
        exec "$python_bin" -m src.analytics.benchmark.benchmark_algorithm.run_all \
            --topology "$topo" --scenario "$workload" --seeds "$seed" --steps 3000 \
            --load stress --skip-exhaustive --data-path "$data" --output-dir "$out" "${args[@]}"
        ;;
    ablation)
        : "${workload:?--workload is required}"
        exec "$python_bin" -m src.analytics.ablation_study --topology "$topo" \
            --scenario "$workload" --seeds "$seed" --steps 3000 --data-path "$data" --output-dir "$out"
        ;;
    load_sweep)
        : "${load:?--load is required}" "${model:?--model is required}" "${normalizer:?--normalizer is required}"
        exec "$python_bin" - "$topo" "$seed" "$load" "$data" "$model" "$normalizer" "$out" <<'PY'
import csv
import sys
from pathlib import Path

from src.analytics.benchmark.benchmark_algorithm.run_load_sweep import run_sweep

topo, seed, load, data, model, norm, output = sys.argv[1:]
rows = run_sweep(topo, [float(load)], 3000, [int(seed)], Path(data), Path(model), Path(norm))
output = Path(output)
output.mkdir(parents=True, exist_ok=True)
with (output / f'load_{topo}_{load}_{seed}.csv').open('x', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
    writer.writeheader()
    writer.writerows(rows)
PY
        ;;
    *) printf 'Unknown experiment: %s\n' "$exp" >&2; exit 2;;
esac
