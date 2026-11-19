"""Index available archived evidence and report missing original run paths."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = "docs/AIO-mesh-rev1"
EVIDENCE = f"{DOCS}/evidence"
HIL = "results/rev1/e6_12h_control_plane/runs/20261117_190242"
FORWARDING = "results/hil/rebuild_20261117T123405Z"
OUT = ROOT / EVIDENCE / "run_index"
BENCHMARK_SOURCES = json.loads((ROOT / EVIDENCE / "policy_tradeoffs/sources.json").read_text())
SWEEP_SOURCES = json.loads((ROOT / EVIDENCE / "load_sweep/sources.json").read_text())
EXPERIMENTS = {
    "algorithm_benchmark": ([f"{EVIDENCE}/policy_tradeoffs/benchmark_tradeoffs.csv"],
                            BENCHMARK_SOURCES),
    "matched_trace_ablation": ([f"{EVIDENCE}/e3/manifest.json",
                                f"{EVIDENCE}/e3/ablation_admission_summary.csv",
                                f"{EVIDENCE}/e3/ablation_pooled_summary.csv"],
                               ["results/rev1/e3"]),
    "timed_ablation": ([], ["results/rev1/e3_timed"]),
    "offered_intensity": ([f"{EVIDENCE}/load_sweep/all_modes_per_seed.csv"], SWEEP_SOURCES),
    "background_chains": ([], ["results/rev1/e4_active_chains/geant2_rerun"]),
    "pair_oracle": ([], ["results/rev1/nonhil_studies/20261117_233441"]),
    "decision_cost": ([], ["results/rev1/nonhil_studies/20261117_233441"]),
    "grid_timing": ([], ["results/rev1/nonhil_studies/20261117_235132"]),
    "hil12h": ([f"{HIL}/{name}" for name in (
        "all_records.csv", "kubernetes_readiness.csv", "run_manifest.json",
        "run_provenance.json", "CONTROL_PLANE_SCOPE.json",
        "scenarios/normal_load/normal_load_hourly_summary.csv",
    )], []),
    "forwarding": ([f"{FORWARDING}/{name}" for name in (
        "phase18_h9_egress.pcap", "phase19_vxlan.pcap", "phase19_host_peer.pcap",
    )], ["results/raw/forwarding"]),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (files, source_paths) in EXPERIMENTS.items():
        original = source_paths if isinstance(source_paths, dict) else dict.fromkeys(source_paths)
        entries = []
        for relative in sorted(set(files) | original.keys()):
            path = ROOT / relative
            entries.append({
                "path": relative,
                "kind": "file" if path.is_file() else "directory" if path.is_dir() else "missing",
                "sha256": sha256(path) if path.is_file() else None,
                "recorded_original_sha256": original.get(relative),
            })
        info = {
            "experiment": name,
            "scope": (
                "Diagnostic endpoint probe only. No ordered multi-VNF trial is indexed."
                if name == "forwarding" else
                "File-level evidence index. Refer to run metadata for experiment provenance."
            ),
            "artifacts": entries,
        }
        (OUT / f"{name}.json").write_text(json.dumps(info, indent=2) + "\n")


if __name__ == "__main__":
    main()
