#!/usr/bin/env python3
"""Bounded live-API admission concurrency sweep WITHOUT ledger reset or actuation.

Differences from src/analytics/benchmark/benchmark_testbed/run_concurrency.py:
  * never calls /api/orchestrate/reset (the live ledger holds 7 baseline VNFs);
  * every admitted reservation is released by name through /api/orchestrate/free
    after its TTL (counted in completed requests, as in the 12-h runner), and all
    remaining ones at the end of each level;
  * full HTTP error bodies, server timings and admitted realization (operation
    ID, switch path, SID stack) are kept per request;
  * the forecast alert stays off and the trace has no Attack/pps fields, so the
    router's actuation branch (DRL + alert) cannot be taken.

Per request it records client enqueue/dispatch/response times and the server's
own handler time, so client-observed RTT - server_decision_ms estimates time
spent waiting in front of the (single-worker) server.

Usage:
  /home/CoreRouter/venv/bin/python scripts/run_admission_concurrency.py <out_dir> \
      --requests 200 --levels 1 2 4 8 16 --seeds 42 43 44
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import platform
import shutil
import sqlite3
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/CoreRouter")
sys.path.insert(0, str(REPO))
from src.analytics.benchmark.benchmark_testbed.http_client import TestbedClient  # noqa: E402
from src.analytics.benchmark.benchmark_testbed.run_concurrency import build_request_trace  # noqa: E402

LEDGER = REPO / "results/rev1/runtime/reservations.sqlite3"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def pct(values, q):
    s = sorted(values)
    if not s:
        return None
    return s[max(0, min(len(s) - 1, round((q / 100.0) * (len(s) - 1))))]


def state_digest(client: TestbedClient) -> dict:
    code, body, _ = client.state()
    data = body.get("data", {}) if isinstance(body, dict) else {}
    active = data.get("active_vnfs") or []
    names = sorted(v.get("name") if isinstance(v, dict) else str(v) for v in active)
    return {"http": code, "mode": data.get("mode"), "alert_flag": data.get("alert_flag"),
            "state_version": data.get("state_version"), "global_utilization": data.get("global_utilization"),
            "reservation_persistence": data.get("reservation_persistence"),
            "unaccounted_vnfs": data.get("unaccounted_vnfs"), "active_vnf_names": names}


def backup_ledger(dest: Path) -> str:
    src = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dest))
    src.backup(dst)
    dst.close(); src.close()
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def run_level(client, trace, concurrency, seed, out_rows, free_rows):
    lock = threading.Lock()
    expiries: list = []  # (expire_at_completion, seq, vnf_name, request_id)
    completed = 0

    def call(index):
        spec = trace[index]
        payload = spec.to_payload()
        payload["alert_flag"] = False
        rid = f"conc-s{seed}-c{concurrency:02d}-{index:04d}"
        dispatch_utc, t0 = utc(), time.perf_counter()
        status, body, latency_ms = client.orchestrate(payload)
        t1 = time.perf_counter()
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        timing = data.get("timings_ms") or {}
        real = data.get("admitted_realization") or {}
        server_ms = timing.get("server_decision_ms")
        return {
            "request_id": rid, "seed": seed, "concurrency": concurrency, "trace_index": index,
            "service_type": spec.service_type, "cpu_req": spec.cpu_req, "ram_req": spec.ram_req,
            "msd_req": spec.msd_req, "source_node": spec.source_node, "destination_node": spec.destination_node,
            "ttl_steps": spec.ttl_steps,
            "dispatch_utc": dispatch_utc, "response_utc": utc(),
            "http_status": status, "admitted": status == 200 and body.get("status") == "success",
            "reason_key": detail.get("reason_key", ""), "error_code": detail.get("code", ""),
            "error_message": detail.get("message", "") if detail else (body.get("detail") if status != 200 else ""),
            "client_rtt_ms": round(float(latency_ms), 3), "client_wall_ms": round((t1 - t0) * 1000.0, 3),
            "server_decision_ms": server_ms if server_ms is not None else "",
            "est_wait_outside_handler_ms": round(float(latency_ms) - float(server_ms), 3) if server_ms is not None else "",
            "state_sync_ms": timing.get("state_sync_ms", ""), "state_snapshot_ms": timing.get("state_snapshot_ms", ""),
            "normalization_ms": timing.get("normalization_ms", ""), "mask_construction_ms": timing.get("mask_construction_ms", ""),
            "policy_inference_ms": timing.get("policy_inference_ms", timing.get("heuristic_inference_ms", "")),
            "admission_validation_ms": timing.get("admission_validation_ms", ""),
            "controller_handoff_ms": timing.get("controller_handoff_ms", ""),
            "method_used": data.get("method_used", ""), "hybrid_branch": data.get("hybrid_branch", ""),
            "vnf_name": data.get("vnf_name", ""), "operation_id": real.get("operation_id", ""),
            "v_place": (data.get("placement_node") or {}).get("id", ""),
            "v_route": (data.get("routing_node") or {}).get("id", ""),
            "switch_path": "-".join(str(x) for x in real.get("switch_path", [])),
            "sid_stack": " ".join(real.get("sid_stack", [])), "p4_topology_hash": real.get("p4_topology_hash", ""),
            "actuation": json.dumps(data.get("migration_result")) if data.get("migration_result") else "",
        }

    def release(row, rid, why):
        # FreeResourceRequest requires the full tuple even when vnf_name is given;
        # with vnf_name the backend releases exactly that named reservation.
        payload = {"vnf_name": row["vnf_name"], "v_place": int(row["v_place"]), "v_route": int(row["v_route"]),
                   "cpu_req": float(row["cpu_req"]), "ram_req": float(row["ram_req"]), "msd_req": int(row["msd_req"])}
        code, body, lat = client.free(payload)
        ok = code == 200 and body.get("status") == "success"
        free_rows.append({"request_id": rid, "vnf_name": row["vnf_name"], "why": why, "utc": utc(), "http_status": code,
                          "ok": ok, "latency_ms": round(float(lat), 3), "detail": json.dumps(body.get("detail", ""))})
        if not ok:
            raise RuntimeError(f"release failed for {row['vnf_name']}: HTTP {code} {body}")

    start = time.perf_counter()
    rows = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending, nxt, seqno = {}, 0, 0
        while nxt < min(concurrency, len(trace)):
            pending[pool.submit(call, nxt)] = nxt
            nxt += 1
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in sorted(done, key=lambda f: pending[f]):
                pending.pop(fut)
                row = fut.result()
                rows.append(row)
                completed += 1
                if row["admitted"] and row["vnf_name"]:
                    seqno += 1
                    heapq.heappush(expiries, (completed + int(row["ttl_steps"]), seqno, row["vnf_name"], row["request_id"], row))
                while expiries and expiries[0][0] <= completed:
                    _, _, name, rid, rrow = heapq.heappop(expiries)
                    release(rrow, rid, "ttl")
                if nxt < len(trace):
                    pending[pool.submit(call, nxt)] = nxt
                    nxt += 1
    wall = time.perf_counter() - start
    while expiries:
        _, _, name, rid, rrow = heapq.heappop(expiries)
        release(rrow, rid, "end_of_level")
    out_rows.extend(sorted(rows, key=lambda r: r["trace_index"]))
    return wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--api", default="http://127.0.0.1:8000/api")
    ap.add_argument("--sdn", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    client = TestbedClient(args.api, args.sdn, request_timeout_s=60.0)
    manifest = {"protocol": "live-api-admission-concurrency-noreset-v1", "started_utc": utc(),
                "argv": sys.argv, "python": platform.python_version(), "platform": platform.platform(),
                "requests_per_level": args.requests, "levels": args.levels, "seeds": args.seeds,
                "actuation": "disabled by construction (alert_flag=false, no pps, no Attack service)",
                "reset_used": False,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for rel in ("src/analytics/benchmark/benchmark_testbed/http_client.py",
                "src/analytics/benchmark/benchmark_testbed/run_concurrency.py",
                "src/analytics/benchmark/benchmark_testbed/scenarios/common.py",
                "src/portal/backend/app/routers/orchestration_router.py",
                "src/portal/backend/app/services/hybrid_decision.py"):
        manifest.setdefault("source_sha256", {})[rel] = hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
    manifest["ledger_backup_before_sha256"] = backup_ledger(out / "ledger_before.sqlite3")
    manifest["state_before"] = state_digest(client)
    if manifest["state_before"]["alert_flag"]:
        raise SystemExit("forecast alert is active; refusing to run (actuation branch could be taken)")
    code, body, _ = client.msd_drops()
    manifest["msd_drops_before"] = body
    rows, frees, summaries = [], [], []
    for seed in args.seeds:
        trace = build_request_trace(args.requests, seed)
        trace_hash = hashlib.sha256(json.dumps([t.to_payload() for t in trace], sort_keys=True).encode()).hexdigest()
        for level in args.levels:
            level_rows: list = []
            t_start = utc()
            wall = run_level(client, trace, level, seed, level_rows, frees)
            rows.extend(level_rows)
            st = state_digest(client)
            if st["active_vnf_names"] != manifest["state_before"]["active_vnf_names"]:
                manifest["aborted"] = f"state not back to baseline after seed {seed} level {level}: {len(st['active_vnf_names'])} active"
                (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
                raise SystemExit(manifest["aborted"])
            rtt = [r["client_rtt_ms"] for r in level_rows]
            srv = [float(r["server_decision_ms"]) for r in level_rows if r["server_decision_ms"] != ""]
            wait_ = [float(r["est_wait_outside_handler_ms"]) for r in level_rows if r["est_wait_outside_handler_ms"] != ""]
            reasons: dict = {}
            for r in level_rows:
                k = "admitted" if r["admitted"] else (r["reason_key"] or r["error_code"] or f"http_{r['http_status']}")
                reasons[k] = reasons.get(k, 0) + 1
            summaries.append({
                "seed": seed, "concurrency": level, "trace_sha256": trace_hash, "started_utc": t_start,
                "offered": len(level_rows), "completed": sum(r["http_status"] in (200, 409) for r in level_rows),
                "admitted": sum(r["admitted"] for r in level_rows),
                "http_5xx_or_timeout": sum(r["http_status"] not in (200, 409) for r in level_rows),
                "outcomes": json.dumps(reasons, sort_keys=True),
                "wall_s": round(wall, 3), "completed_ops_per_s": round(len(level_rows) / wall, 3),
                "rtt_p50_ms": pct(rtt, 50), "rtt_p95_ms": pct(rtt, 95), "rtt_p99_ms": pct(rtt, 99),
                "server_p50_ms": pct(srv, 50), "server_p95_ms": pct(srv, 95), "server_p99_ms": pct(srv, 99),
                "wait_p50_ms": pct(wait_, 50), "wait_p95_ms": pct(wait_, 95), "wait_p99_ms": pct(wait_, 99),
                "state_after_active_vnfs": len(st["active_vnf_names"]), "state_after_mode": st["mode"],
                "state_after_unaccounted": json.dumps(st["unaccounted_vnfs"]),
            })
            print(json.dumps({k: summaries[-1][k] for k in ("seed", "concurrency", "admitted", "http_5xx_or_timeout",
                                                             "completed_ops_per_s", "rtt_p95_ms", "server_p95_ms",
                                                             "state_after_active_vnfs")}), flush=True)
    manifest["state_after"] = state_digest(client)
    code, body, _ = client.msd_drops()
    manifest["msd_drops_after"] = body
    manifest["ledger_backup_after_sha256"] = backup_ledger(out / "ledger_after.sqlite3")
    manifest["finished_utc"] = utc()
    manifest["free_calls"] = {"total": len(frees), "ok": sum(f["ok"] for f in frees)}
    manifest["baseline_unchanged"] = (manifest["state_before"]["active_vnf_names"]
                                      == manifest["state_after"]["active_vnf_names"])
    for name, data in (("per_request.csv", rows), ("free_calls.csv", frees), ("per_seed_level_summary.csv", summaries)):
        with (out / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps({k: manifest[k] for k in ("free_calls", "baseline_unchanged")}))
    return 0 if manifest["baseline_unchanged"] and manifest["free_calls"]["total"] == manifest["free_calls"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
