#!/usr/bin/env python3
"""Validate paired Vietnam evaluations and summarize variation across training seeds."""

import csv
import hashlib
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = ROOT / "results/evidence/mentor_completion_20261121/independent_training/evaluation_2m"
OUTPUT = ROOT / "docs/AIO-mesh-rev1/evidence/mentor_completion_20261121"
BENCHMARK = ROOT / "docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv"
TRAINING_SEEDS = (42, 7, 2024)
EVALUATION_SEEDS = (42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
                    11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def summarize(evaluation, evaluation_seeds=EVALUATION_SEEDS,
              training_seeds=TRAINING_SEEDS, benchmark=None):
    evaluation = Path(evaluation)
    manifest = json.loads((evaluation / "manifest.json").read_text())
    if (set(map(int, manifest["training_seeds"])) != set(training_seeds)
            or set(map(int, manifest["evaluation_seeds"])) != set(evaluation_seeds)):
        raise ValueError("Evaluation manifest seed coverage mismatch")
    for seed in training_seeds:
        artifacts = manifest["checkpoints"][str(seed)]
        for kind, hash_key in (("model", "model_sha256"),
                               ("normalizer", "normalizer_sha256")):
            path = _artifact(artifacts[kind])
            if not path.is_file() or (hash_key in artifacts
                                      and sha256(path) != artifacts[hash_key]):
                raise ValueError(f"Missing or changed {kind} for training seed {seed}")
    paths = sorted(evaluation.glob("train_*_eval_*.csv"))
    expected = len(training_seeds) * len(evaluation_seeds)
    if len(paths) != expected:
        raise ValueError(f"Expected {expected} evaluation rows; found {len(paths)}")
    rows = {}
    traces = {}
    for path in paths:
        with path.open(newline="") as stream:
            records = list(csv.DictReader(stream))
        if len(records) != 1:
            raise ValueError(f"Expected one data row in {path}")
        row = records[0]
        train_seed, eval_seed = int(row["training_seed"]), int(row["seed"])
        if (train_seed not in training_seeds or eval_seed not in evaluation_seeds
                or path.name != f"train_{train_seed}_eval_{eval_seed}.csv"
                or (train_seed, eval_seed) in rows):
            raise ValueError(f"Unexpected or duplicated evaluation cell: {path}")
        if int(row["requests"]) != 3000:
            raise ValueError(f"Unexpected request count: {path}")
        if int(row["training_steps"]) != int(manifest["checkpoints"][str(train_seed)]["training_steps"]):
            raise ValueError(f"Training-step mismatch: {path}")
        trace = row["trace_sha256"]
        if eval_seed in traces and traces[eval_seed] != trace:
            raise ValueError(f"Trace mismatch for evaluation seed {eval_seed}")
        traces[eval_seed] = trace
        rows[train_seed, eval_seed] = row
    if set(rows) != {(t, e) for t in training_seeds for e in evaluation_seeds}:
        raise ValueError("Incomplete training-by-evaluation seed grid")
    if benchmark is not None:
        with Path(benchmark).open(newline="") as stream:
            base = {int(row["seed"]): row for row in csv.DictReader(stream)
                    if row["topology"] == "vietnam"
                    and row["scenario"] == "burst_surge"
                    and row["algorithm"] == "harp_protected"}
        if set(base) != set(evaluation_seeds):
            raise ValueError("Refreshed benchmark seed coverage mismatch")
        for seed in evaluation_seeds:
            row = rows[42, seed]
            if (row["trace_sha256"] != base[seed]["trace_sha256"]
                    or abs(float(row["safe_acceptance_rate"])
                           - float(base[seed]["safe_acceptance_rate"])) > 1e-9):
                raise ValueError(f"Seed-42 evaluation differs from benchmark: {seed}")
    per_model = {}
    for seed in training_seeds:
        values = [float(rows[seed, e]["safe_acceptance_rate"])
                  for e in evaluation_seeds]
        per_model[seed] = {
            "training_seed": seed,
            "training_steps": manifest["checkpoints"][str(seed)]["training_steps"],
            "n_evaluation_seeds": len(values),
            "mean_safe_acceptance_pct": statistics.mean(values),
            "sample_sd_evaluation_pct": statistics.stdev(values),
        }
    means = [per_model[seed]["mean_safe_acceptance_pct"] for seed in training_seeds]
    return {
        "per_model": per_model,
        "across_training": {
            "n_training_seeds": len(means),
            "mean_of_model_means_pct": statistics.mean(means),
            "sample_sd_model_means_pct": statistics.stdev(means),
            "min_model_mean_pct": min(means),
            "max_model_mean_pct": max(means),
        },
        "training_steps_by_seed": {
            str(seed): manifest["checkpoints"][str(seed)]["training_steps"]
            for seed in training_seeds
        },
        "raw_files": paths,
    }


def main():
    summary = summarize(EVALUATION, benchmark=BENCHMARK)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "independent_training_summary.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(summary["per_model"].values()))))
        writer.writeheader()
        writer.writerows(summary["per_model"].values())
    generated = ROOT / "docs/AIO-mesh-rev1/generated"
    table_path = generated / "independent_training_rows.tex"
    table_path.write_text("\n".join(
        f"{r['training_seed']} & {r['training_steps']:,} & {r['mean_safe_acceptance_pct']:.3f} & {r['sample_sd_evaluation_pct']:.3f} " + r"\\"
        for r in summary["per_model"].values()) + "\n")
    stats = summary["across_training"]
    macro_path = generated / "independent_training_numbers.tex"
    macro_path.write_text("\n".join(
        chr(92) + "newcommand{" + chr(92) + name + "}{" + f"{stats[key]:.3f}" + "}"
        for name, key in (("TrainingMeanMin", "min_model_mean_pct"),
                          ("TrainingMeanMax", "max_model_mean_pct"),
                          ("TrainingMeanSD", "sample_sd_model_means_pct"))) + "\n")
    inputs = [EVALUATION / "manifest.json", BENCHMARK, Path(__file__).resolve(),
              *summary["raw_files"]]
    manifest_path = OUTPUT / "independent_training_summary_manifest.json"
    manifest_path.write_text(json.dumps({
        "scope": "Three independently trained Vietnam final checkpoints at the nominal 2M-transition budget, evaluated on 20 matched Bursty traces per checkpoint; actual saved transition counts are retained in the evaluation manifest. Training-seed dispersion is descriptive with three models.",
        "command": "venv/bin/python scripts/rev1/summarize_independent_training.py",
        "inputs_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "outputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in (csv_path, table_path, macro_path)},
        "across_training": summary["across_training"],
    }, indent=2, sort_keys=True) + "\n")
    print(f"Validated {len(summary['raw_files'])} paired evaluation cells; wrote {csv_path}")


if __name__ == "__main__":
    main()
