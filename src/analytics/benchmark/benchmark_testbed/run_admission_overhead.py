"""Bounded live admission timing without reset or actuation.

Each accepted selection-only reservation is verified as pending and released by
its exact returned VNF name before the worker completes. The script is
fail-closed: ambiguous state, actuation, or failed cleanup stops new requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .http_client import TestbedClient


def percentile(values: list[float], p: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1))))
    return float(ordered[index])


class AdmissionRun:
    def __init__(self, args: argparse.Namespace, out_dir: Path):
        self.args = args
        self.out_dir = out_dir
        self.write_lock = threading.Lock()
        self.stop = threading.Event()
        self.raw_path = out_dir / "requests.jsonl"

    def snapshot(self, client: TestbedClient, allowed_pending: set[str] | None = None) -> dict[str, Any]:
        code, body, _ = client.state()
        if code != 200 or body.get("status") != "success":
            raise RuntimeError(f"state read failed: HTTP {code}")
        data = body.get("data") or {}
        active = data.get("active_vnfs") or []
        if data.get("unaccounted_vnfs"):
            raise RuntimeError("unaccounted VNFs are present")
        if any(v.get("accounting_unknown") or v.get("presence_unconfirmed") for v in active):
            raise RuntimeError("unknown or presence-unconfirmed VNF ledger entry is present")
        pending = {str(v.get("name")) for v in active if v.get("is_pending")}
        if pending - (allowed_pending or set()):
            raise RuntimeError(f"unexpected pending reservation(s): {sorted(pending - (allowed_pending or set()))}")
        if data.get("alert_flag"):
            raise RuntimeError("global alert flag is active")
        status_code, status, _ = client.status()
        if status_code != 200 or status.get("is_migrating"):
            raise RuntimeError("migration status is not idle")
        return data

    def append(self, row: dict[str, Any]) -> None:
        with self.write_lock, self.raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()

    def request(self, level: int, index: int) -> dict[str, Any]:
        row: dict[str, Any] = {
            "concurrency": level,
            "request_index": index,
            "flow_id": f"p12-{uuid.uuid4().hex}",
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if self.stop.is_set():
            row.update(outcome="not_started_due_to_stop_gate")
            self.append(row)
            return row

        client = TestbedClient(self.args.api_base_url, self.args.sdn_base_url,
                               request_timeout_s=self.args.timeout)
        payload = {
            "flow_id": row["flow_id"], "service_type": "Data",
            "cpu_req": self.args.cpu, "ram_req": self.args.ram,
            "msd_req": self.args.msd, "alert_flag": False,
            "is_ddos_spike": False,
        }
        started = time.perf_counter()
        code, body, latency = client.orchestrate(payload)
        row.update(payload=payload, http_code=code, http_latency_ms=latency,
                   response=body, outcome="rejected_or_failed")
        if code == 409:
            row["outcome"] = "admission_rejected"
            row["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
            row["request_wall_ms"] = (time.perf_counter() - started) * 1000
            row["event"] = "admission"
            self.append(row)
            return row
        if code != 200 or body.get("status") != "success":
            self.stop.set()
            row["stop_reason"] = "unexpected admission response"
            row["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
            row["event"] = "admission"
            self.append(row)
            return row

        data = body.get("data") or {}
        name = data.get("vnf_name")
        if not name or data.get("migration_result") is not None:
            self.stop.set()
            row["stop_reason"] = "missing reservation name or unexpected actuation"
            row["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
            row["event"] = "admission"
            self.append(row)
            return row

        row["admission_timings_ms"] = data.get("timings_ms") or body.get("timings_ms") or {}
        row["admitted_realization"] = data.get("admitted_realization")
        row["vnf_name"] = name
        row["outcome"] = "admitted_pending_verification"
        row["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        row["request_wall_ms"] = (time.perf_counter() - started) * 1000
        row["event"] = "admission"
        self.append(row)
        return row

    def verify_and_cleanup(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        client = TestbedClient(self.args.api_base_url, self.args.sdn_base_url,
                               request_timeout_s=self.args.timeout)
        owned_names = {str(r["vnf_name"]) for r in rows
                       if r.get("outcome") == "admitted_pending_verification"}
        state = self.snapshot(client, allowed_pending=owned_names)
        entries = {str(v.get("name")): v for v in state.get("active_vnfs", [])}
        pending_names = {name for name, v in entries.items() if v.get("is_pending")}
        if pending_names != owned_names:
            self.stop.set()
            raise RuntimeError(
                f"pending inventory differs from this cohort: owned={sorted(owned_names)}, "
                f"pending={sorted(pending_names)}"
            )

        row_by_name = {str(r["vnf_name"]): r for r in rows
                       if r.get("outcome") == "admitted_pending_verification"}
        for name in sorted(owned_names):
            entry = entries.get(name)
            row = row_by_name[name]
            if (not entry or not entry.get("is_pending")
                    or entry.get("actuation_requested")
                    or entry.get("accounting_unknown")
                    or entry.get("presence_unconfirmed")):
                self.stop.set()
                row["stop_reason"] = "reservation is not positively verified as unactuated/pending"
                row["outcome"] = "safety_gate_failed"
                row["event"] = "cleanup"
                self.append(row)
                raise RuntimeError(f"owned reservation {name} failed verification")
            response = row["response"]
            data = response.get("data") or {}
            placement, routing = data.get("placement_node") or {}, data.get("routing_node") or {}
            if (not isinstance(placement, dict) or not isinstance(routing, dict)
                    or placement.get("id") is None or routing.get("id") is None):
                self.stop.set()
                row["stop_reason"] = "returned placement/routing IDs are unavailable"
                row["outcome"] = "safety_gate_failed"
                row["event"] = "cleanup"
                self.append(row)
                raise RuntimeError(f"owned reservation {name} cannot be mapped for exact cleanup")
            free_code, free_body, free_ms = client.free({
                "vnf_name": name, "v_place": int(placement["id"]),
                "v_route": int(routing["id"]), "cpu_req": self.args.cpu,
                "ram_req": self.args.ram, "msd_req": self.args.msd,
            })
            row["cleanup"] = {"http_code": free_code, "latency_ms": free_ms,
                               "response": free_body}
            if free_code != 200 or free_body.get("status") != "success":
                self.stop.set()
                row["stop_reason"] = "exact reservation cleanup failed"
                row["outcome"] = "cleanup_failed_accounted"
                row["event"] = "cleanup"
                self.append(row)
                raise RuntimeError(f"exact cleanup failed for owned reservation {name}")
            row["reservation_verified"] = True
            row["outcome"] = "admitted_and_cleaned"
            row["event"] = "cleanup"
            self.append(row)

        after = self.snapshot(client)
        if any(v.get("name") in owned_names for v in after.get("active_vnfs", [])):
            self.stop.set()
            raise RuntimeError("one or more cohort reservations remain after cleanup")
        return after


def summarize(rows: list[dict[str, Any]], level: int, wall_s: float) -> dict[str, Any]:
    timings = [float(r["admission_timings_ms"]["admission_validation_ms"])
               for r in rows if "admission_validation_ms" in r.get("admission_timings_ms", {})]
    decisions = [float(r["admission_timings_ms"]["server_decision_ms"])
                 for r in rows if "server_decision_ms" in r.get("admission_timings_ms", {})]
    http = [float(r["http_latency_ms"]) for r in rows if r.get("http_latency_ms") is not None]
    return {
        "concurrency": level, "generated": len(rows),
        "accepted_and_cleaned": sum(r.get("outcome") == "admitted_and_cleaned" for r in rows),
        "admission_rejected": sum(r.get("outcome") == "admission_rejected" for r in rows),
        "failed_or_stopped": sum(r.get("outcome") not in ("admitted_and_cleaned", "admission_rejected") for r in rows),
        "admission_validation_ms": {f"p{p}": percentile(timings, p) for p in (50, 95, 99)},
        "server_decision_ms": {f"p{p}": percentile(decisions, p) for p in (50, 95, 99)},
        "http_latency_ms": {f"p{p}": percentile(http, p) for p in (50, 95, 99)},
        "completed_ops_per_s": len(rows) / wall_s if wall_s > 0 else 0.0,
        "wall_clock_s": wall_s,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--sdn-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output-dir", type=Path, default=Path("results/rev1/p1_2_live_admission"))
    parser.add_argument("--requests-per-level", type=int, default=10)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--cpu", type=float, default=1.0)
    parser.add_argument("--ram", type=float, default=1.0)
    parser.add_argument("--msd", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    if args.requests_per_level < 1 or not args.concurrency or any(c not in (1, 2, 4) for c in args.concurrency):
        raise SystemExit("bounded protocol requires requests >= 1 and concurrency levels from {1, 2, 4}")
    if args.cpu <= 0 or args.ram <= 0 or not 1 <= args.msd <= 10:
        raise SystemExit("request resources must be positive and MSD must be in [1, 10]")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=False)
    run = AdmissionRun(args, out_dir)
    client = TestbedClient(args.api_base_url, args.sdn_base_url, request_timeout_s=args.timeout)
    baseline = run.snapshot(client)
    summaries = []
    all_rows = []
    for level in args.concurrency:
        if run.stop.is_set():
            break
        run.snapshot(client)
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            futures = [pool.submit(run.request, level, i)
                       for i in range(args.requests_per_level)]
            rows = [future.result() for future in as_completed(futures)]
        wall_s = time.perf_counter() - started
        rows.sort(key=lambda r: r["request_index"])
        try:
            after_level = run.verify_and_cleanup(rows)
        except Exception as exc:
            run.stop.set()
            failure = {"concurrency": level, "safety_gate_error": f"{type(exc).__name__}: {exc}"}
            (out_dir / "safety_gate_failure.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            break
        for row in rows:
            if row.get("outcome") == "admitted_pending_verification":
                row["post_cleanup_state_version"] = after_level.get("state_version")
        all_rows.extend(rows)
        summaries.append(summarize(rows, level, wall_s))
        if run.stop.is_set():
            break

    final_error = None
    try:
        final = run.snapshot(client)
    except Exception as exc:
        final = {}
        final_error = f"{type(exc).__name__}: {exc}"
        run.stop.set()
    manifest = {
        "protocol": "live-admission-overhead-no-reset-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reset_called": False, "alert_actuation_requested": False,
        "request_profile": {"service_type": "Data", "cpu": args.cpu,
                            "ram": args.ram, "msd": args.msd},
        "concurrency_levels_requested": args.concurrency,
        "requests_per_level": args.requests_per_level,
        "baseline": {"state_version": baseline.get("state_version"),
                     "active_vnf_count": len(baseline.get("active_vnfs", [])),
                     "global_utilization": baseline.get("global_utilization")},
        "final": {"state_version": final.get("state_version"),
                  "active_vnf_count": len(final.get("active_vnfs", [])),
                  "global_utilization": final.get("global_utilization"),
                  "unaccounted_vnfs": final.get("unaccounted_vnfs"),
                  "state_read_error": final_error},
        "summaries": summaries,
        "stopped_on_safety_gate": run.stop.is_set(),
        "python": platform.python_version(), "platform": platform.platform(),
        "request_records_sha256": hashlib.sha256(run.raw_path.read_bytes()).hexdigest()
            if run.raw_path.exists() else None,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir), "summaries": summaries,
                      "baseline_vnfs": manifest["baseline"]["active_vnf_count"],
                      "final_vnfs": manifest["final"]["active_vnf_count"],
                      "stopped_on_safety_gate": run.stop.is_set()}, indent=2, sort_keys=True))
    if run.stop.is_set():
        raise SystemExit("stopped on a live safety gate; inspect requests.jsonl and manifest.json")


if __name__ == "__main__":
    main()
