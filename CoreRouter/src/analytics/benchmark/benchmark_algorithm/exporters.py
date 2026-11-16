from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List

from .metrics import RunMetrics, aggregate_runs


def write_seed_summary(path: Path, runs: Iterable[RunMetrics]) -> None:
    rows = [run.as_summary() for run in runs]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_aggregate_summary(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    rows = [aggregate_runs(runs) for runs in grouped_runs.values() if runs]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, grouped_runs: Dict[str, List[RunMetrics]]) -> None:
    payload = {
        algorithm: [run.as_summary() for run in runs]
        for algorithm, runs in grouped_runs.items()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

