from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from .models import RequestRecord, ScenarioSummary


def write_records_csv(path: Path, records: Iterable[RequestRecord]) -> None:
    rows = [asdict(record) for record in records]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["tags"] = json.dumps(row.get("tags") or {}, sort_keys=True)
            writer.writerow(row)


def write_summary_csv(path: Path, summaries: Iterable[ScenarioSummary]) -> None:
    rows = [asdict(summary) for summary in summaries]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, summaries: List[ScenarioSummary], records: List[RequestRecord]) -> None:
    payload = {
        "summaries": [asdict(summary) for summary in summaries],
        "records": [asdict(record) for record in records],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

