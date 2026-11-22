#!/usr/bin/env python3
"""Cross-check the 12-hour control-plane HIL run against independent server logs.

Inputs (all inside the export package):
  01_hil12h/original/e6_12h_control_plane/runs/20261117_190242/  (client records)
  01_hil12h/recovered_logs/backend_access_12h_window.log         (uvicorn access log)
  01_hil12h/recovered_logs/k8s_core_router_pipelineruns.csv
  01_hil12h/recovered_logs/mininet_sdn_controller_console.log
  00_inventory/at_start/processes_project.txt, sdn_msd_drops.txt
P4 adjacency is taken from the repository's infrastructure/sdn/p4_topology.py
(hash recorded in the output; it matched the backend container at export time).

Outputs (generated/hil12h/):
  per_request_hil12h.csv      one row per offered request with a derived request key
  reject_decomposition.csv    msd_req x HTTP status x reason_key, with the
                              source-code consequence of each combination
  hourly_hil12h.csv           per-hour offered/admitted/rejected and RTT percentiles
  crosscheck_hil12h.json      all consistency checks and their results

No value is imputed. Fields absent from the original logs stay empty.
Usage: python3 scripts/analyze_hil12h.py <export_root>
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path("/home/CoreRouter")
sys.path.insert(0, str(REPO))
from infrastructure.sdn.p4_topology import P4_EDGES, P4_NODE_COUNT, neighbors  # noqa: E402

RUN_REL = "01_hil12h/original/e6_12h_control_plane/runs/20261117_190242"
ACCESS = re.compile(r'^(\S+) INFO:\s+\S+ - "(\w+) (\S+) HTTP/1\.1" (\d{3})')


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pct(values, q):
    """Rounded-rank percentile, identical to benchmark_testbed.metrics.percentile."""
    s = sorted(values)
    rank = round((q / 100.0) * (len(s) - 1))
    return s[max(0, min(rank, len(s) - 1))]


def bfs_depth(src: int, dst: int) -> int:
    """Number of switch SIDs on the shortest P4 path (nodes on path)."""
    frontier, seen, depth = [src], {src}, 1
    while frontier:
        if dst in frontier:
            return depth
        nxt = []
        for n in frontier:
            for m in neighbors(n):
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier, depth = nxt, depth + 1
    raise ValueError("disconnected")


def parse_ts(text: str) -> datetime:
    # docker nanosecond timestamps -> microseconds
    m = re.match(r"(.*T\d\d:\d\d:\d\d)(\.\d+)?Z", text)
    frac = (m.group(2) or ".0")[:7]
    return datetime.fromisoformat(m.group(1) + frac + "+00:00")


def main() -> int:
    export = Path(sys.argv[1]).resolve()
    run = export / RUN_REL
    out = export / "generated" / "hil12h"
    out.mkdir(parents=True, exist_ok=True)
    checks: dict = {"inputs_sha256": {}}

    rec_path = run / "all_records.csv"
    rows = list(csv.DictReader(rec_path.open()))
    manifest = json.loads((run / "run_manifest.json").read_text())
    msd_limits = [float(x) for x in manifest["msd_limits"]]
    checks["inputs_sha256"]["all_records.csv"] = sha256(rec_path)

    # --- duplicate copies inside the run directory must be identical ---------
    dup = run / "scenarios/normal_load/all_records.csv"
    checks["scenario_copy_identical"] = sha256(dup) == checks["inputs_sha256"]["all_records.csv"]
    bj = json.loads((run / "benchmark_results.json").read_text())
    checks["benchmark_results_json_records"] = len(bj["records"])
    checks["benchmark_results_json_status_sequence_equal_csv"] = (
        [str(r["status_code"]) for r in bj["records"]] == [r["status_code"] for r in rows])

    # --- server access log ----------------------------------------------------
    log_path = export / "01_hil12h/recovered_logs/backend_access_12h_window.log"
    checks["inputs_sha256"]["backend_access_12h_window.log"] = sha256(log_path)
    orchestrate, frees, other = [], [], Counter()
    events = []  # ordered: ("orch"|"free", ts, status)
    for line in log_path.read_text(errors="replace").splitlines():
        m = ACCESS.match(line)
        if not m:
            continue
        ts, method, path, status = m.groups()
        if method == "POST" and path == "/api/orchestrate":
            orchestrate.append((parse_ts(ts), status))
            events.append(("orch", status))
        elif method == "POST" and path == "/api/orchestrate/free":
            frees.append((parse_ts(ts), status))
            events.append(("free", status))
        else:
            other[f"{method} {path} {status}"] += 1
    client_status = [r["status_code"] for r in rows]
    server_status = [s for _, s in orchestrate]
    checks["server_post_orchestrate_count"] = len(orchestrate)
    checks["server_status_counts"] = dict(Counter(server_status))
    checks["client_status_counts"] = dict(Counter(client_status))
    checks["status_sequence_identical_client_vs_server"] = client_status == server_status
    checks["server_free_calls"] = dict(Counter(s for _, s in frees))
    checks["server_other_requests_in_window"] = dict(other)
    # every free must follow an earlier admitted request (running balance >= 0)
    balance, min_balance = 0, 0
    for kind, status in events:
        if kind == "orch" and status == "200":
            balance += 1
        elif kind == "free" and status == "200":
            balance -= 1
        min_balance = min(min_balance, balance)
    checks["free_never_exceeds_prior_admissions"] = min_balance >= 0
    checks["unfreed_admissions_at_window_end"] = balance

    # --- per-request table ----------------------------------------------------
    per_req = []
    offsets_ms = []
    for i, r in enumerate(rows):
        srv_ts, srv_status = orchestrate[i] if i < len(orchestrate) else (None, "")
        cli_ts = datetime.fromisoformat(r["timestamp_utc"])
        off = (cli_ts - srv_ts).total_seconds() * 1000.0 if srv_ts else None
        if off is not None:
            offsets_ms.append(off)
        src = int(r["source_node"])
        place = int(r["placement_node_id"]) if r["placement_node_id"] else None
        depth = bfs_depth(src, place) if place is not None and place != src else None
        msd_req = int(r["msd_req"])
        if r["status_code"] == "200":
            consequence = "admitted; requested depth equals compiled source->placement path depth"
        elif msd_req < 2 and r["reject_reason"] == "msd_violation":
            consequence = ("depth mismatch by construction: msd_req=1 < minimum compiled depth 2 "
                           "(source != placement); not an MSD-limit exceedance")
        elif r["reject_reason"] == "msd_violation":
            consequence = ("label 'msd_violation' = message containing 'msd'; with depth <= 2 and "
                           "min MSD limit 4 this can only be a depth mismatch (placement not adjacent)")
        else:
            consequence = ("reason_key fallback 'no_safe_action'; original HTTP message not retained "
                           "(e.g. placement == source, or other ValueError)")
        per_req.append({
            "derived_request_key": f"hil12h-20261117T190242-step{int(r['step']):06d}",
            "row_index": i,
            "generator_step": r["step"],
            "client_timestamp_utc": r["timestamp_utc"],
            "server_log_timestamp_utc": srv_ts.isoformat() if srv_ts else "",
            "client_minus_server_ms": f"{off:.3f}" if off is not None else "",
            "http_status_client": r["status_code"],
            "http_status_server_log": srv_status,
            "service_type": r["service_type"],
            "cpu_req": r["cpu_req"], "ram_req": r["ram_req"], "msd_req": msd_req,
            "source_node": src, "destination_node": r["destination_node"],
            "placement_node": "" if place is None else place,
            "routing_node": r["routing_node_id"],
            "server_vnf_name": r["vnf_name"],
            "sid_count": r["sid_count"],
            "compiled_path_depth_recomputed": "" if depth is None else depth,
            "route_node_msd_limit": (msd_limits[int(r["routing_node_id"])] if r["routing_node_id"] else ""),
            "reason_key": r["reject_reason"],
            "source_code_consequence": consequence,
            "method_used": r["method_used"], "hybrid_branch": r["hybrid_branch"],
            "api_rtt_ms": r["decision_latency_ms"],
            "actuation_requested": r["actuation_requested"], "deployed": r["deployed"],
            "hour_index": r["hour_index"],
        })
    with (out / "per_request_hil12h.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_req[0].keys()))
        w.writeheader()
        w.writerows(per_req)
    offsets_ms.sort()
    checks["client_minus_server_timestamp_ms"] = {
        "n": len(offsets_ms), "min": offsets_ms[0], "p50": pct(offsets_ms, 50),
        "p99": pct(offsets_ms, 99), "max": offsets_ms[-1],
        "note": "client timestamp is taken after the HTTP response; server timestamp is the docker log write time of the access line",
    }

    # --- structural checks ----------------------------------------------------
    acc = [p for p in per_req if p["http_status_client"] == "200"]
    checks["accepted_depth_equals_msd_req"] = all(
        p["compiled_path_depth_recomputed"] == p["msd_req"] == int(p["sid_count"]) for p in acc)
    checks["accepted_server_vnf_names_unique"] = len({p["server_vnf_name"] for p in acc}) == len(acc)
    pairs = [(a, b) for a in range(P4_NODE_COUNT) for b in range(P4_NODE_COUNT) if a != b]
    depths = {pair: bfs_depth(*pair) for pair in pairs}
    checks["p4_topology"] = {
        "edges": [list(e) for e in P4_EDGES],
        "p4_topology_py_sha256": sha256(REPO / "infrastructure/sdn/p4_topology.py"),
        "min_compiled_depth_over_distinct_pairs": min(depths.values()),
        "max_compiled_depth_over_distinct_pairs": max(depths.values()),
        "depth_histogram": dict(Counter(depths.values())),
        "manifest_runtime_edges": manifest.get("edges"),
    }
    checks["msd_limits_from_manifest"] = msd_limits
    checks["max_requested_depth"] = max(int(r["msd_req"]) for r in rows)
    checks["true_msd_limit_exceedance_possible_in_this_run"] = (
        checks["max_requested_depth"] > min(msd_limits))
    checks["requested_depth_by_service"] = {
        k: dict(v) for k, v in _group(rows, "service_type", "msd_req").items()}

    # --- reject decomposition -------------------------------------------------
    deco = Counter((int(r["msd_req"]), r["status_code"], r["reject_reason"] or "-") for r in rows)
    with (out / "reject_decomposition.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["msd_req", "http_status", "reason_key", "count", "percent_of_offered", "source_code_consequence"])
        for (m, s, reason), n in sorted(deco.items()):
            cons = next(p["source_code_consequence"] for p in per_req
                        if p["msd_req"] == m and p["http_status_client"] == s and (p["reason_key"] or "-") == reason)
            w.writerow([m, s, reason, n, f"{100.0 * n / len(rows):.2f}", cons])

    # --- hourly ----------------------------------------------------------------
    by_hour = defaultdict(list)
    for p in per_req:
        by_hour[int(p["hour_index"])].append(p)
    with (out / "hourly_hil12h.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["hour_index", "offered", "admitted", "rejected_msd_label", "rejected_no_safe_action",
                    "admit_rate_percent", "rtt_p50_ms", "rtt_p95_ms", "rtt_p99_ms"])
        for h in sorted(by_hour):
            ps = by_hour[h]
            lat = [float(p["api_rtt_ms"]) for p in ps]
            adm = sum(p["http_status_client"] == "200" for p in ps)
            w.writerow([h, len(ps), adm, sum(p["reason_key"] == "msd_violation" for p in ps),
                        sum(p["reason_key"] == "no_safe_action" for p in ps),
                        f"{100.0 * adm / len(ps):.2f}", pct(lat, 50), pct(lat, 95), pct(lat, 99)])

    # --- Kubernetes / controller / counters -----------------------------------
    pr = list(csv.DictReader((export / "01_hil12h/recovered_logs/k8s_core_router_pipelineruns.csv").open()))
    start, end = rows[0]["timestamp_utc"][:19], rows[-1]["timestamp_utc"][:19]
    checks["pipelineruns_created_during_run"] = sum(start <= p["creationTimestamp"][:19] <= end for p in pr)
    ctl = (export / "01_hil12h/recovered_logs/mininet_sdn_controller_console.log").read_text(errors="replace")
    ctl_lines_in_window = [l for l in ctl.splitlines() if l[:19] >= start and l[:19] <= end]
    checks["controller_console_lines_during_run"] = len(ctl_lines_in_window)
    rd = list(csv.DictReader((run / "kubernetes_readiness.csv").open()))
    gaps = [float(b["elapsed_s"]) - float(a["elapsed_s"]) for a, b in zip(rd, rd[1:])]
    checks["readiness"] = {
        "samples": len(rd), "first": rd[0]["timestamp_utc"], "last": rd[-1]["timestamp_utc"],
        "interval_s_min": min(gaps), "interval_s_max": max(gaps),
        "deployments_ready_set": sorted({f"{r['ready_deployments']}/{r['deployment_count']}" for r in rd}),
        "replicas_ready_set": sorted({f"{r['ready_replicas']}/{r['desired_replicas']}" for r in rd}),
        "snapshot_errors": sum(bool(r["snapshot_error"]) for r in rd),
        "deployment_names_set": sorted({r["deployment_detail"] for r in rd}),
    }
    pre = json.loads((run / "preflight.json").read_text())
    checks["msd_drops"] = {
        "preflight_2026-11-17": pre["sdn_msd_drops"]["body"],
        "summary_msd_drop_delta": bj["summaries"][0].get("msd_drop_delta"),
        "read_at_export": (export / "00_inventory/at_start/sdn_msd_drops.txt").read_text().splitlines()[2],
        "switch_processes": "see 00_inventory/at_start/processes_project.txt (simple_switch started 2026-11-17 18:16:40-48 UTC, not restarted)",
        "interpretation": "cumulative per-switch msd_violation_counter stayed 0 from switch start through export; "
                          "the HIL run sent no packets through P4, so this is not a packet-level MSD measurement",
    }
    summ = bj["summaries"][0]
    checks["run_summary_notes"] = summ.get("notes")
    (out / "crosscheck_hil12h.json").write_text(json.dumps(checks, indent=2, default=str))
    flags = {k: v for k, v in checks.items() if isinstance(v, bool)}
    print(json.dumps(flags, indent=2))
    return 0 if all(v for k, v in flags.items() if k != "true_msd_limit_exceedance_possible_in_this_run") else 1


def _group(rows, key, val):
    g = defaultdict(Counter)
    for r in rows:
        g[r[key]][r[val]] += 1
    return g


if __name__ == "__main__":
    raise SystemExit(main())
