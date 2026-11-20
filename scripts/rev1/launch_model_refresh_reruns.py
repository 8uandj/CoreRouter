#!/usr/bin/env python3
"""Create and launch parallel load/chain and oracle reruns for refreshed models."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAMP = "20261120_163000"
OUT = ROOT / "results/evidence" / f"model_refresh_reruns_{STAMP}"
SOCKET = f"harp_model_refresh_{STAMP}"
TOPOLOGIES = ("vietnam", "nsfnet", "geant2")
CHAINS = (0, 25, 50, 100)
SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
         11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    (OUT / "commands").mkdir(parents=True)
    (OUT / "logs").mkdir()
    (OUT / "load_chain").mkdir()
    (OUT / "oracle").mkdir()
    data = ROOT / "data/real_telecom_combined.csv"
    source_files = [
        ROOT / "src/analytics/benchmark/benchmark_algorithm/run_load_sweep.py",
        ROOT / "src/analytics/benchmark/benchmark_algorithm/algorithms.py",
        ROOT / "src/analytics/benchmark/benchmark_algorithm/config.py",
        ROOT / "scripts/rev1/run_nonhil_studies.py",
        ROOT / "src/orchestration/jo_vdpr/env.py",
        ROOT / "src/orchestration/jo_vdpr/topology.py",
    ]
    artifacts = {}
    for topology in TOPOLOGIES:
        base = ROOT / "results/models/retrain_v11_20261119_corrected" / topology
        models = sorted(base.glob("dgrl_v11_final_*.zip"))
        norms = sorted(base.glob("vec_normalize_v11_*.pkl"))
        if len(models) != 1 or len(norms) != 1:
            raise RuntimeError(f"expected one model and normalizer for {topology}: {models}, {norms}")
        artifacts[topology] = {
            "model_path": str(models[0].relative_to(ROOT)), "model_sha256": sha(models[0]),
            "normalizer_path": str(norms[0].relative_to(ROOT)), "normalizer_sha256": sha(norms[0]),
        }

    commands = []
    py = ROOT / "venv/bin/python"
    runner = "src.analytics.benchmark.benchmark_algorithm.run_load_sweep"
    for topology in TOPOLOGIES:
        artifact = artifacts[topology]
        for chains in CHAINS:
            name = f"load_{topology}_chains_{chains}"
            output = OUT / "load_chain" / topology / f"chains_{chains}"
            command = (
                f"cd {ROOT} && export MPLCONFIGDIR=/tmp/model-refresh-mpl "
                f"OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "
                f"&& {py} -m {runner} --topology {topology} --steps 3000 "
                f"--seeds {' '.join(map(str, SEEDS))} --data-path data/real_telecom_combined.csv "
                f"--model-path {artifact['model_path']} --normalizer-path {artifact['normalizer_path']} "
                f"--active-chains {chains} --output-dir {output}"
            )
            commands.append((name, command, output))

    oracle_script = ROOT / "scripts/rev1/run_nonhil_studies.py"
    for topology in TOPOLOGIES:
        artifact = artifacts[topology]
        name = f"oracle_{topology}"
        output = OUT / "oracle" / topology
        command = (
            f"cd {ROOT} && export MPLCONFIGDIR=/tmp/model-refresh-mpl "
            f"OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "
            f"&& {py} {oracle_script} --study oracle --topology {topology} --steps 3000 "
            f"--seeds {' '.join(map(str, SEEDS[:10]))} --oracle-stride 25 --data {data} "
            f"--model {artifact['model_path']} --normalizer {artifact['normalizer_path']} --output {output}"
        )
        commands.append((name, command, output))

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_dirty_at_launch": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "launcher_sha256": sha(Path(__file__)),
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_files},
        "dataset_path": str(data.relative_to(ROOT)), "dataset_sha256": sha(data),
        "models": artifacts,
        "load_chain_protocol": {
            "steps_per_seed": 3000, "seeds": list(SEEDS), "loads": [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5],
            "initial_active_chains": list(CHAINS), "scenario": "bursty",
            "policies": [f"{p}_{mode}" for mode in ("protected", "unprotected")
                         for p in ("harp", "saf_h", "cspf", "traditional_greedy", "decoupled_ai")],
            "chain_profile": {"cpu": 2, "ram": 2, "msd": 1, "bandwidth": 20, "placement": "round-robin"},
        },
        "oracle_protocol": {"steps_per_seed": 3000, "seeds": list(SEEDS[:10]), "stride": 25,
                            "policies": ["harp", "saf_h"], "scenario": "bursty", "load": 1.0},
        "tmux_socket": SOCKET,
        "sessions": [],
        "resource_note": "GPU driver was unavailable at launch preflight; these evaluation runners use CPU.",
    }
    for name, command, output in commands:
        cmdfile = OUT / "commands" / f"{name}.sh"
        logfile = OUT / "logs" / f"{name}.log"
        cmdfile.write_text("#!/usr/bin/env bash\nset -o pipefail\n" + command + f" 2>&1 | tee {logfile}\n", encoding="utf-8")
        cmdfile.chmod(0o755)
        manifest["sessions"].append({"name": name, "command_file": str(cmdfile.relative_to(ROOT)),
                                     "command_sha256": sha(cmdfile), "log_file": str(logfile.relative_to(ROOT)),
                                     "output_dir": str(output.relative_to(ROOT)), "status": "planned"})
    (OUT / "launch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for session in manifest["sessions"]:
        name = session["name"]
        subprocess.run(["tmux", "-L", SOCKET, "new-session", "-d", "-s", name,
                        "bash", str(ROOT / session["command_file"])], check=True)
        session["status"] = "launched"
        session["launched_utc"] = datetime.now(timezone.utc).isoformat()
        (OUT / "launch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "socket": SOCKET,
                      "sessions": [s["name"] for s in manifest["sessions"]]}, indent=2))


if __name__ == "__main__":
    main()
