#!/usr/bin/env python3
"""Rebuild the control-plane HIL table from its request and readiness logs.

The input is a completed HIL run directory containing all_records.csv,
kubernetes_readiness.csv, run_manifest.json, and CONTROL_PLANE_SCOPE.json.
The generated table intentionally excludes forwarding, deployment, and packet
claims: this run sent no traffic through P4 and requested no actuation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RUN = Path("results/rev1/e6_12h_control_plane/runs/20261117_190242")
DEFAULT_OUT = Path("docs/AIO-mesh-rev1/generated")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def percentile(values: list[float], pct: float) -> float:
    """Match benchmark_testbed.metrics.percentile's rounded rank convention."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a percentile over no observations")
    rank = round((pct / 100.0) * (len(ordered) - 1))
    return ordered[max(0, min(rank, len(ordered) - 1))]


def pct_text(numerator: int, denominator: int) -> str:
    return f"{numerator:,} ({100.0 * numerator / denominator:.2f}\%)" if denominator else "0 (—)"


def latex_escape(value: str) -> str:
    for old, new in (("_", r"\_"), ("%", r"\%"), ("&", r"\&")):
        value = value.replace(old, new)
    return value


def derive(run_dir: Path) -> tuple[dict[str, Any], str]:
    records_path = run_dir / "all_records.csv"
    readiness_path = run_dir / "kubernetes_readiness.csv"
    manifest_path = run_dir / "run_manifest.json"
    scope_path = run_dir / "CONTROL_PLANE_SCOPE.json"

    records = read_csv(records_path, (
        "status_code", "decision_latency_ms", "msd_req", "sid_count",
        "reject_reason", "method_used", "hybrid_branch", "deployed",
        "actuation_requested", "hour_index", "timing_ms",
    ))
    readiness = read_csv(readiness_path, (
        "deployment_count", "ready_deployments", "desired_replicas",
        "ready_replicas", "snapshot_error", "elapsed_s",
    ))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))

    if scope.get("evidence_class") != "control_plane_hil" or scope.get("traffic_through_p4") is not False:
        raise ValueError("scope file does not identify a control-plane-only HIL run")
    if manifest.get("workers") != 1 or manifest.get("reset_before_scenario") is not False:
        raise ValueError("this table definition expects the recorded sequential, no-reset run")

    n = len(records)
    statuses = Counter(row["status_code"] for row in records)
    reasons = Counter(row["reject_reason"] for row in records)
    depth_demand = Counter(int(row["msd_req"]) for row in records)
    latencies = [float(row["decision_latency_ms"]) for row in records]
    hourly: dict[int, list[float]] = defaultdict(list)
    hourly_admissions: dict[int, int] = defaultdict(int)
    for row in records:
        hour = int(row["hour_index"])
        hourly[hour].append(float(row["decision_latency_ms"]))
        hourly_admissions[hour] += row["status_code"] == "200"
    hourly_p95 = [percentile(values, 95.0) for _, values in sorted(hourly.items())]
    hourly_admission_rates = {
        str(hour): {
            "requests": len(hourly[hour]),
            "admitted": hourly_admissions[hour],
            "rate_percent": 100.0 * hourly_admissions[hour] / len(hourly[hour]),
        }
        for hour in sorted(hourly)
    }

    accepted = statuses.get("200", 0)
    rejected = statuses.get("409", 0)
    if accepted + rejected != n:
        raise ValueError(f"unexpected HTTP status counts: {dict(statuses)}")

    accepted_rows = [row for row in records if row["status_code"] == "200"]
    accepted_methods = Counter(row["method_used"] for row in accepted_rows)
    accepted_branches = Counter(row["hybrid_branch"] for row in accepted_rows)
    if not accepted_methods or not accepted_branches:
        raise ValueError("accepted rows do not contain policy attribution")

    component_values: dict[str, list[float]] = defaultdict(list)
    for row in accepted_rows:
        timing = json.loads(row["timing_ms"] or "{}")
        for key, value in timing.items():
            component_values[key].append(float(value))

    readiness_clean = all(not row["snapshot_error"] for row in readiness)
    dep_counts = {int(row["deployment_count"]) for row in readiness}
    ready_dep_counts = {int(row["ready_deployments"]) for row in readiness}
    desired_replica_counts = {int(row["desired_replicas"]) for row in readiness}
    ready_replica_counts = {int(row["ready_replicas"]) for row in readiness}
    if not (len(dep_counts) == len(ready_dep_counts) == len(desired_replica_counts) == len(ready_replica_counts) == 1):
        raise ValueError("readiness inventory varied; refusing to summarize as a constant baseline")

    all_times = [row["elapsed_s"] for row in readiness]
    actuation = sum(row["actuation_requested"].lower() == "true" for row in records)
    deployed = sum(row["deployed"].lower() == "true" for row in records)

    result: dict[str, Any] = {
        "evidence_class": "control_plane_hil",
        "source_run": str(run_dir),
        "run_start_utc": manifest.get("created_at_utc"),
        "duration_hours": manifest.get("duration_hours"),
        "workers": manifest.get("workers"),
        "request_interval_s": manifest.get("request_interval_s"),
        "topology": manifest.get("topology"),
        "topology_nodes": manifest.get("nodes"),
        "msd_limits_sid_by_node": manifest.get("msd_limits"),
        "requests": n,
        "http_status_counts": dict(statuses),
        "reject_reason_counts": dict(reasons),
        "requested_sid_depth_counts": {str(k): depth_demand[k] for k in sorted(depth_demand)},
        "api_rtt_ms": {
            f"p{p}": percentile(latencies, p) for p in (50, 95, 99)
        },
        "hourly_api_rtt_p95_ms": {
            "count": len(hourly_p95),
            "min": min(hourly_p95),
            "max": max(hourly_p95),
            "values": hourly_p95,
        },
        "hourly_admission_rates_percent": hourly_admission_rates,
        "accepted_policy_methods": dict(accepted_methods),
        "accepted_hybrid_branches": dict(accepted_branches),
        "accepted_backend_component_percentiles_ms": {
            key: {f"p{p}": percentile(values, p) for p in (50, 95, 99)}
            for key, values in sorted(component_values.items())
        },
        "actuation_requested": actuation,
        "deployed_requests": deployed,
        "readiness": {
            "samples": len(readiness),
            "start_elapsed_s": float(all_times[0]),
            "end_elapsed_s": float(all_times[-1]),
            "snapshot_errors": sum(bool(row["snapshot_error"]) for row in readiness),
            "deployment_count": next(iter(dep_counts)),
            "ready_deployments": next(iter(ready_dep_counts)),
            "desired_replicas": next(iter(desired_replica_counts)),
            "ready_replicas": next(iter(ready_replica_counts)),
            "all_samples_clean": readiness_clean,
        },
        "msd_drop_measurement": "not measured during this run; preflight-only counter reads are excluded",
        "forwarding_evidence": "none from this run; traffic_through_p4=false",
        "source_sha256": {
            path.name: sha256(path)
            for path in (records_path, readiness_path, manifest_path, scope_path)
        },
    }
    if actuation or deployed:
        raise ValueError("unexpected actuation/deployment in the control-plane-only run")

    rows: list[tuple[str, str]] = [
        ("API requests", f"{n:,}"),
        ("Requested SID depth 1 / 2", f"{depth_demand.get(1, 0):,} / {depth_demand.get(2, 0):,}"),
        ("Configured per-node MSD limit (SID entries)", ", ".join(map(str, manifest.get("msd_limits", [])))),
        ("Admitted (HTTP 200)", pct_text(accepted, n)),
        ("Rejected (HTTP 409)", pct_text(rejected, n)),
        ("\\quad MSD rejection", pct_text(reasons.get("msd_violation", 0), n)),
        ("\\quad Other no-safe-action", pct_text(reasons.get("no_safe_action", 0), n)),
        ("\\quad CPU/RAM capacity rejection", pct_text(reasons.get("cpu_capacity", 0) + reasons.get("ram_capacity", 0), n)),
        ("API timeouts", f"{statuses.get('timeout', 0):,}"),
        ("Accepted policy / branch", f"{', '.join(accepted_methods)} / {', '.join(accepted_branches)}"),
        ("Client-observed API RTT P50 / P95 / P99 (ms)", " / ".join(f"{result['api_rtt_ms'][f'p{p}']:.2f}" for p in (50, 95, 99))),
        ("Hourly API RTT P95 range (ms)", f"{min(hourly_p95):.2f}--{max(hourly_p95):.2f}"),
        ("Hourly admission-rate range (% of requests)",
         f"{min(v['rate_percent'] for v in hourly_admission_rates.values()):.2f}--{max(v['rate_percent'] for v in hourly_admission_rates.values()):.2f}"),
        ("Backend policy inference P50 / P95 / P99 (ms; admitted only)", _fmt_component(result, "policy_inference_ms")),
        ("Backend admission validation P50 / P95 / P99 (ms; admitted only)", _fmt_component(result, "admission_validation_ms")),
        ("Actuation requested / deployment confirmed", f"{actuation:,} / {deployed:,}"),
        ("Baseline Deployments Ready", f"{result['readiness']['ready_deployments']}/{result['readiness']['deployment_count']} in {len(readiness):,}/{len(readiness):,} samples"),
        ("Baseline replicas Ready", f"{result['readiness']['ready_replicas']}/{result['readiness']['desired_replicas']} in {len(readiness):,}/{len(readiness):,} samples"),
        ("MSD drops / forwarding", "not measured / not part of this run"),
    ]
    tex = [
        "% Generated by scripts/paper/make_table11.py; do not hand-edit.",
        "\\begin{tabular}{@{}lr@{}}",
        "\\toprule",
        "Metric & Observed value \\\\",
        "\\midrule",
    ]
    tex.extend(f"{latex_escape(label)} & {value} \\\\" for label, value in rows)
    tex.extend(["\\bottomrule", "\\end{tabular}", ""])
    return result, "\n".join(tex)


def _fmt_component(result: dict[str, Any], key: str) -> str:
    component = result["accepted_backend_component_percentiles_ms"].get(key)
    if not component:
        return "not recorded"
    return " / ".join(f"{component[f'p{p}']:.2f}" for p in (50, 95, 99))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    data, table = derive(args.run_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "table11.tex").write_text(table, encoding="utf-8")
    (args.output_dir / "table11.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output_dir / 'table11.tex'}")
    print(f"Wrote {args.output_dir / 'table11.json'}")


if __name__ == "__main__":
    main()
