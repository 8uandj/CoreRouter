from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List
from collections import defaultdict

from .models import RequestRecord, ScenarioSummary
from .metrics import percentile


def write_records_csv(path: Path, records: Iterable[RequestRecord]) -> None:
    rows = [asdict(record) for record in records]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["tags"] = json.dumps(row.get("tags") or {}, sort_keys=True)
            row["timing_ms"] = json.dumps(row.get("timing_ms") or {}, sort_keys=True)
            writer.writerow(row)


def write_hourly_summary_csv(path: Path, records: Iterable[RequestRecord]) -> None:
    grouped = defaultdict(list)
    for record in records:
        grouped[record.hour_index].append(record)
    rows = []
    for hour, items in sorted(grouped.items()):
        latencies = [item.decision_latency_ms for item in items]
        rows.append({
            "hour_index": hour,
            "generated_requests": len(items),
            "admitted": sum(item.admitted for item in items),
            "safe_admitted": sum(item.safe_admitted for item in items),
            "deployed": sum(item.deployed for item in items),
            "rejected": sum(not item.admitted for item in items),
            "rejection_cpu": sum(item.reject_reason == "cpu_capacity" for item in items),
            "rejection_ram": sum(item.reject_reason == "ram_capacity" for item in items),
            "rejection_msd": sum(item.reject_reason == "msd_violation" for item in items),
            "rejection_other": sum(not item.admitted and item.reject_reason not in {"cpu_capacity", "ram_capacity", "msd_violation"} for item in items),
            "decision_p50_ms": percentile(latencies, 50.0),
            "decision_p95_ms": percentile(latencies, 95.0),
            "decision_p99_ms": percentile(latencies, 99.0),
        })
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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

