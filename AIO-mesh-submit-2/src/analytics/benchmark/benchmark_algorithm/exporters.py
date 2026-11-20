from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List

from .metrics import RunMetrics, aggregate_runs
from src.analytics.benchmark.revision.statistics import paired_statistics


def write_seed_summary(path: Path, runs: Iterable[RunMetrics]) -> None:
    rows = [run.as_summary() for run in runs]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_aggregate_summary(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    rows = [aggregate_runs(runs) for runs in grouped_runs.values() if runs]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    payload = {
        algorithm: [run.as_summary() for run in runs]
        for algorithm, runs in grouped_runs.items()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_paired_statistics(path: Path, runs: Iterable[RunMetrics]) -> None:
    rows = [run.as_summary() for run in runs]
    result = paired_statistics(rows, {
        "metric": "acceptance_rate",
        "comparisons": [{"name": "harp_vs_saf_h_protected", "treatment": "harp_protected", "control": "saf_h_protected"}],
        "n_bootstrap": 10_000,
        "analysis_seed": 20261116,
    })
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

