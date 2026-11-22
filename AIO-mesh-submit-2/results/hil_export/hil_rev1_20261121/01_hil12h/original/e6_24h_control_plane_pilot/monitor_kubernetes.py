#!/usr/bin/env python3
"""Read-only, periodic Kubernetes readiness sampler for E6 control-plane HIL."""

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def kubectl_json(resource, namespace):
    raw = subprocess.check_output(
        ["kubectl", "get", resource, "-n", namespace, "-o", "json"],
        text=True,
        stderr=subprocess.STDOUT,
    )
    return json.loads(raw)


def snapshot(namespace):
    deployments = kubectl_json("deployments", namespace).get("items", [])
    pods = kubectl_json("pods", namespace).get("items", [])
    deployment_rows = []
    ready_deployments = 0
    desired_replicas = 0
    ready_replicas = 0
    for item in deployments:
        name = item.get("metadata", {}).get("name", "")
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        desired = int(spec.get("replicas", 1) or 0)
        ready = int(status.get("readyReplicas", 0) or 0)
        available = int(status.get("availableReplicas", 0) or 0)
        desired_replicas += desired
        ready_replicas += ready
        ready_deployments += int(desired > 0 and ready >= desired)
        deployment_rows.append("{}:{}/{}/{}".format(name, ready, desired, available))

    ready_pods = 0
    running_pods = 0
    pod_rows = []
    for item in pods:
        metadata = item.get("metadata", {}) or {}
        status = item.get("status", {}) or {}
        name = metadata.get("name", "")
        phase = status.get("phase", "Unknown")
        is_ready = any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in status.get("conditions", []) or []
        )
        running_pods += int(phase == "Running")
        ready_pods += int(is_ready)
        pod_rows.append("{}:{}:{}".format(name, phase, "ready" if is_ready else "not-ready"))

    return {
        "deployment_count": len(deployments),
        "ready_deployments": ready_deployments,
        "desired_replicas": desired_replicas,
        "ready_replicas": ready_replicas,
        "pod_count": len(pods),
        "running_pods": running_pods,
        "ready_pods": ready_pods,
        "deployment_detail": ";".join(deployment_rows),
        "pod_detail": ";".join(pod_rows),
        "snapshot_error": "",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="core-router")
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval-s", type=float, default=60.0)
    parser.add_argument("--duration-hours", type=float, default=24.0)
    args = parser.parse_args()
    if args.interval_s <= 0 or args.duration_hours <= 0:
        parser.error("interval and duration must be positive")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "timestamp_utc", "elapsed_s", "namespace", "deployment_count",
        "ready_deployments", "desired_replicas", "ready_replicas", "pod_count",
        "running_pods", "ready_pods", "deployment_detail", "pod_detail", "snapshot_error",
    ]
    run_start = time.monotonic()
    with output.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        handle.flush()
        end_after_s = args.duration_hours * 3600.0
        while time.monotonic() - run_start < end_after_s:
            sample_start = time.monotonic()
            row = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_s": round(sample_start - run_start, 3),
                "namespace": args.namespace,
            }
            try:
                row.update(snapshot(args.namespace))
            except Exception as exc:  # preserve failures as observations, not missing rows
                row.update({key: "" for key in fields if key not in row})
                row["snapshot_error"] = "{}: {}".format(type(exc).__name__, exc)
            writer.writerow(row)
            handle.flush()
            remaining = args.interval_s - (time.monotonic() - sample_start)
            if remaining > 0:
                time.sleep(min(remaining, max(0.0, end_after_s - (time.monotonic() - run_start))))


if __name__ == "__main__":
    main()
