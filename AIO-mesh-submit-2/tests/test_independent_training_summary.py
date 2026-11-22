import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/rev1"))
from summarize_independent_training import summarize


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture(tmp_path):
    evaluation = tmp_path / "evaluation"
    evaluation.mkdir()
    models = {}
    for training_seed in (42, 7, 2024):
        model = tmp_path / f"model_{training_seed}.zip"
        normalizer = tmp_path / f"normalizer_{training_seed}.pkl"
        model.write_bytes(str(training_seed).encode())
        normalizer.write_bytes(b"normalizer")
        models[str(training_seed)] = {"model": str(model), "normalizer": str(normalizer)}
        for evaluation_seed in (11, 23):
            write_csv(evaluation / f"train_{training_seed}_eval_{evaluation_seed}.csv", [{
                "training_seed": training_seed, "seed": evaluation_seed,
                "requests": 3000, "safe_acceptance_rate": training_seed / 100 + evaluation_seed,
                "trace_sha256": f"trace-{evaluation_seed}",
            }])
    (evaluation / "manifest.json").write_text(json.dumps({
        "training_seeds": [42, 7, 2024], "evaluation_seeds": [11, 23],
        "checkpoints": models,
    }))
    return evaluation


def test_summarize_requires_complete_paired_grid(tmp_path):
    evaluation = fixture(tmp_path)
    summary = summarize(evaluation, (11, 23), (42, 7, 2024))
    assert len(summary["per_model"]) == 3
    assert summary["across_training"]["n_training_seeds"] == 3
    assert summary["per_model"][42]["mean_safe_acceptance_pct"] == 17.42
    (evaluation / "train_2024_eval_23.csv").unlink()
    with pytest.raises(ValueError, match="Expected 6 evaluation rows"):
        summarize(evaluation, (11, 23), (42, 7, 2024))


def test_summarize_rejects_trace_mismatch(tmp_path):
    evaluation = fixture(tmp_path)
    path = evaluation / "train_7_eval_23.csv"
    row = list(csv.DictReader(path.open()))[0]
    row["trace_sha256"] = "different"
    write_csv(path, [row])
    with pytest.raises(ValueError, match="Trace mismatch"):
        summarize(evaluation, (11, 23), (42, 7, 2024))
