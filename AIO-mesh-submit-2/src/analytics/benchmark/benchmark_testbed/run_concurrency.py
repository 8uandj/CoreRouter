"""Matched HIL concurrency sweep against the live orchestration API.

Each concurrency level replays the same pre-generated request trace after a
state reset. The producer submits at most C requests at once (FIFO refill on
completion); throughput is completed HTTP operations divided by measured wall
time, never inferred from a latency percentile.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List

from .http_client import TestbedClient
from .models import RequestSpec
from .preflight import run_preflight
from .scenarios.common import request_from_profile, weighted_service
from .runner import stable_name_offset


def build_request_trace(count: int, seed: int) -> List[RequestSpec]:
    if count < 1:
        raise ValueError("request count must be positive")
    rng = random.Random(seed + stable_name_offset("concurrency_trace"))
    result = []
    while len(result) < count:
        source = rng.randint(0, 9)
        target = rng.randint(0, 9)
        while target == source:
            target = rng.randint(0, 9)
        result.append(request_from_profile(
            rng, weighted_service(rng), source, target, 10, 50
        ))
    return result


def run_level(client: TestbedClient, requests: List[RequestSpec], concurrency: int) -> tuple[list[dict], float]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")

    def submit_one(pool, index):
        spec = requests[index]
        submitted_at = time.perf_counter()

        def call():
            status, body, latency_ms = client.orchestrate(spec.to_payload())
            detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            accepted = status == 200 and body.get("status") == "success"
            timing = data.get("timings_ms") or {}
            return {
                "request_id": f"req-{index:08d}",
                "request_index": index,
                "status_code": status,
                "admitted": accepted,
                "safe_admitted": accepted,
                "actuation_requested": bool(data.get("migration_result")),
                "deployment_status": str((data.get("migration_result") or {}).get("status", "not_requested")),
                "reject_reason": str(detail.get("reason_key") or detail.get("code") or ""),
                "http_latency_ms": round(float(latency_ms), 3),
                "client_dispatch_overhead_ms": round((time.perf_counter() - submitted_at) * 1000.0 - float(latency_ms), 3),
                "state_sync_ms": timing.get("state_sync_ms", ""),
                "state_snapshot_ms": timing.get("state_snapshot_ms", ""),
                "mask_construction_ms": timing.get("mask_construction_ms", ""),
                "policy_inference_ms": timing.get("policy_inference_ms", timing.get("heuristic_inference_ms", "")),
                "admission_validation_ms": timing.get("admission_validation_ms", ""),
                "controller_handoff_ms": timing.get("controller_handoff_ms", ""),
                "server_decision_ms": timing.get("server_decision_ms", ""),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        return pool.submit(call)

    run_start = time.perf_counter()
    rows = []
    next_index = 0
    pending = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while next_index < min(concurrency, len(requests)):
            pending[submit_one(pool, next_index)] = next_index
            next_index += 1
        while pending:
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in sorted(completed, key=lambda item: pending[item]):
                pending.pop(future)
                rows.append(future.result())
                if next_index < len(requests):
                    pending[submit_one(pool, next_index)] = next_index
                    next_index += 1
    return sorted(rows, key=lambda row: row["request_index"]), max(0.0, time.perf_counter() - run_start)


def summarize(rows: List[dict], concurrency: int, wall_s: float) -> dict:
    latencies = [float(row["http_latency_ms"]) for row in rows]
    admitted = sum(bool(row["admitted"]) for row in rows)
    ordered = sorted(latencies)

    def pct(p):
        if not ordered:
            return 0.0
        index = max(0, min(len(ordered) - 1, round((p / 100.0) * (len(ordered) - 1))))
        return ordered[index]

    return {
        "concurrency": concurrency,
        "queue_policy": "bounded FIFO producer; at most concurrency in-flight HTTP operations",
        "generated": len(rows),
        "completed": len(rows),
        "admitted": admitted,
        "rejected": len(rows) - admitted,
        "acceptance_rate": 100.0 * admitted / len(rows) if rows else 0.0,
        "http_latency_mean_ms": mean(latencies) if latencies else 0.0,
        "http_latency_p50_ms": pct(50),
        "http_latency_p95_ms": pct(95),
        "http_latency_p99_ms": pct(99),
        "wall_clock_s": wall_s,
        "completed_ops_per_s": len(rows) / wall_s if wall_s > 0 else 0.0,
        "client_dispatch_overhead_p95_ms": pct_values([float(r["client_dispatch_overhead_ms"]) for r in rows], 95),
    }


def pct_values(values: List[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay matched requests at several live API concurrency levels")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--sdn-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output-dir", default="results/benchmark_testbed/concurrency")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    client = TestbedClient(args.api_base_url, args.sdn_base_url, request_timeout_s=60.0)
    if not args.skip_preflight:
        ok, checks = run_preflight(client)
        if not ok:
            raise SystemExit(f"HIL preflight failed: {json.dumps(checks, sort_keys=True)}")

    request_trace = build_request_trace(args.requests, args.seed)
    out_dir = Path(args.output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_summaries = []
    for concurrency in args.concurrency:
        if concurrency < 1:
            raise SystemExit("All concurrency levels must be positive")
        client.reset()
        client.set_alert(False)
        rows, wall_s = run_level(client, request_trace, concurrency)
        for row in rows:
            row["seed"] = args.seed
            row["trace_id"] = f"concurrency-{args.seed}-{args.requests}"
        summary = summarize(rows, concurrency, wall_s)
        summary.update({"seed": args.seed, "trace_id": f"concurrency-{args.seed}-{args.requests}"})
        all_summaries.append(summary)
        with (out_dir / f"concurrency_{concurrency}_requests.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["request_id"])
            writer.writeheader()
            writer.writerows(rows)

    with (out_dir / "concurrency_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_summaries[0].keys()))
        writer.writeheader()
        writer.writerows(all_summaries)
    manifest = {
        "protocol": "matched-live-api-concurrency-v1",
        "request_count": args.requests,
        "concurrency_levels": args.concurrency,
        "seed": args.seed,
        "trace_sha256": __import__("hashlib").sha256(
            json.dumps([spec.to_payload() for spec in request_trace], sort_keys=True).encode()
        ).hexdigest(),
        "api_base_url": args.api_base_url,
        "workers": args.concurrency,
        "queue_policy": "bounded FIFO producer, at most C in-flight requests",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Saved matched concurrency sweep to {out_dir}")


if __name__ == "__main__":
    main()
