#!/usr/bin/env bash
# Launch six new-model HARP benchmarks in independent tmux sessions.
# Results are isolated under results/evidence; no historical output is replaced.
set -euo pipefail
cd "$(dirname "$0")/../.."

run_tag="${1:-$(date -u +%Y%m%d_%H%M%S)}"
root="results/evidence/multinode_benchmark_${run_tag}"
socket="harp_multinode_benchmark_${run_tag}"
if [[ -e "$root" ]]; then
    printf 'Evidence directory already exists; refusing to reuse it: %s\n' "$root" >&2
    exit 1
fi
mkdir -p "$root/logs" "$root/commands"
python_bin="$PWD/venv/bin/python"
data="$PWD/data/real_telecom_combined.csv"
seeds=(42 100 2024 8888 9999 7 17 73 314 2718 11 23 47 89 101 211 512 1024 4096 8192)
topologies=(vietnam nsfnet geant2 synthetic_25 synthetic_50 synthetic_100)

model_for() {
    case "$1" in
        vietnam) echo "$PWD/results/models/retrain_v11_20261119_corrected/vietnam/dgrl_v11_final_vietnam.zip" ;;
        nsfnet) echo "$PWD/results/models/retrain_v11_20261119_corrected/nsfnet/dgrl_v11_final_nsfnet.zip" ;;
        geant2) echo "$PWD/results/models/retrain_v11_20261119_corrected/geant2/dgrl_v11_final_geant2.zip" ;;
        synthetic_*) echo "$PWD/results/models/v11_$1/dgrl_v11_final_$1.zip" ;;
    esac
}
norm_for() {
    case "$1" in
        vietnam) echo "$PWD/results/models/retrain_v11_20261119_corrected/vietnam/vec_normalize_v11_vietnam.pkl" ;;
        nsfnet) echo "$PWD/results/models/retrain_v11_20261119_corrected/nsfnet/vec_normalize_v11_nsfnet.pkl" ;;
        geant2) echo "$PWD/results/models/retrain_v11_20261119_corrected/geant2/vec_normalize_v11_geant2.pkl" ;;
        synthetic_*) echo "$PWD/results/models/v11_$1/vec_normalize_v11_$1.pkl" ;;
    esac
}

command -v tmux >/dev/null
test -r "$data"
for topo in "${topologies[@]}"; do
    model="$(model_for "$topo")"
    norm="$(norm_for "$topo")"
    test -r "$model"
    test -r "$norm"
done

export HARP_BENCH_ROOT="$root" HARP_BENCH_SOCKET="$socket"
"$python_bin" - <<'PY'
import hashlib, json, os, subprocess
from pathlib import Path

root = Path(os.environ["HARP_BENCH_ROOT"])
topologies = ("vietnam", "nsfnet", "geant2", "synthetic_25", "synthetic_50", "synthetic_100")
seeds = [42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718, 11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192]
models = {}
for topology in topologies:
    if topology in ("vietnam", "nsfnet", "geant2"):
        base = Path("results/models/retrain_v11_20261119_corrected") / topology
        model = base / f"dgrl_v11_final_{topology}.zip"
        normalizer = base / f"vec_normalize_v11_{topology}.pkl"
    else:
        base = Path("results/models") / f"v11_{topology}"
        model = base / f"dgrl_v11_final_{topology}.zip"
        normalizer = base / f"vec_normalize_v11_{topology}.pkl"
    def sha(path):
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    models[topology] = {"model": str(model), "model_sha256": sha(model),
                        "normalizer": str(normalizer), "normalizer_sha256": sha(normalizer)}
manifest = {
    "kind": "new_multinode_benchmark",
    "run_tag": root.name.removeprefix("multinode_benchmark_"),
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "protocol": "benchmark-v2, three stress workloads (Elephant/Heavy-tail, Bursty, Chaos), 20 fixed seeds, 3000 offered steps per seed/workload, skip exhaustive policy, one seed worker per topology session",
    "scenario_argument": "ablation (in run_all this selects exactly elephant_stress, burst_surge, chaos; it does not enable the retired ablation path)",
    "seeds": seeds, "topologies": list(topologies), "models": models,
    "data_path": "data/real_telecom_combined.csv",
    "data_sha256": sha(Path("data/real_telecom_combined.csv")),
    "python": subprocess.check_output([str(Path("venv/bin/python")), "--version"], text=True).strip(),
    "tmux_socket": os.environ["HARP_BENCH_SOCKET"],
    "result_root": str(root),
}
(root / "launch_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

seeds_arg="${seeds[*]}"
for topo in "${topologies[@]}"; do
    model="$(model_for "$topo")"
    norm="$(norm_for "$topo")"
    out="$PWD/$root/$topo"
    log="$PWD/$root/logs/$topo.log"
    cmd="cd $PWD && env MPLCONFIGDIR=/tmp/mpl_multinode_${run_tag}_${topo} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 $python_bin -u -m src.analytics.benchmark.benchmark_algorithm.run_all --topology $topo --scenario ablation --load stress --steps 3000 --seeds $seeds_arg --skip-exhaustive --workers 1 --data-path $data --model-path $model --normalizer-path $norm --output-dir $out >> $log 2>&1"
    printf '%s\n' "$cmd" > "$root/commands/$topo.txt"
    tmux -L "$socket" new-session -d -s "mnb_${run_tag}_${topo}" "$cmd"
done

printf 'Evidence root: %s\n' "$root"
printf 'tmux socket: %s\n' "$socket"
tmux -L "$socket" list-sessions
