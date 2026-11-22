#!/usr/bin/env python3
"""Request-correlated end-to-end HIL campaign on the live testbed.

Per offered request (alert on => DRL branch with actuation):
  admitted (HTTP 200, admitted_realization) -> deployment initiated (backend MAKE log,
  PipelineRun) -> Ready (backend READY log, Pod Ready condition) -> rules installed
  (controller log) and read back (simple_switch_CLI table_dump on every path switch)
  -> steering verified (controller confirm_steer_done, backend STEERED) -> packets
  received (e2e_packet_probe: HTTP marker echo for vVOC, ICMP marker otherwise).
Rejected requests keep the full HTTP error body.

Usage:
  e2e_campaign.py --out DIR --target-new 30 --max-requests 600 --seed 2026 [--probe-n 20]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
API = "http://127.0.0.1:8000/api"
PY = "/home/CoreRouter/venv/bin/python"
TYPES = ["voc", "idps", "nat", "lb", "firewall", "data", "video", "router", "voc"]
PROFILES = {"URLLC": (4, 2), "VoIP": (6, 3), "Data": (10, 5), "Video": (18, 9)}
NODE_K8S = {0: "k8s-master", 1: "k8s-master", 2: "k8s-master", 3: "worker1", 4: "worker1", 5: "worker1",
            6: "worker2", 7: "worker2", 8: "worker2", 9: "worker2"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def http(method, path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        body, code = e.read(), e.code
    except (urllib.error.URLError, socket.timeout) as e:
        return 0, {"client_error": str(e)}, (time.perf_counter() - t0) * 1000
    try:
        return code, json.loads(body), (time.perf_counter() - t0) * 1000
    except ValueError:
        return code, {"raw": body.decode(errors="replace")}, (time.perf_counter() - t0) * 1000


def sh(cmd, timeout=120):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout).stdout


def kjson(args):
    try:
        return json.loads(sh(["kubectl", "-n", "core-router", "get", *args, "-o", "json"]))
    except ValueError:
        return {}


def log_lines(container, since, pattern):
    out = subprocess.run(["docker", "logs", "--timestamps", "--since", since, container],
                         capture_output=True, text=True).stdout + \
        subprocess.run(["docker", "logs", "--timestamps", "--since", since, container],
                       capture_output=True, text=True).stderr
    return [l for l in out.splitlines() if pattern in l]


def first_ts(lines, needle):
    for l in lines:
        if needle in l:
            return l.split(" ", 1)[0]
    return ""


def readback(switch_path, sids):
    """Expected: route to next-hop SID on every non-terminal switch, End.DX4 at terminal."""
    rows = []
    for cur, nxt in zip(switch_path, switch_path[1:]):
        dump = sh([str(TOOLS / "p4cli.sh"), f"s{cur}", "table_dump routing_v6"])
        key = socket.inet_pton(socket.AF_INET6, f"fc00:{nxt}::1").hex()
        rows.append({"switch": f"s{cur}", "table": "routing_v6", "key": f"fc00:{nxt}::1/128",
                     "present": key in dump and "ipv6_forward" in dump})
    t = switch_path[-1]
    dump = sh([str(TOOLS / "p4cli.sh"), f"s{t}", "table_dump srv6_end_dx4_table"])
    key = socket.inet_pton(socket.AF_INET6, f"fc00:{t}::1").hex()
    rows.append({"switch": f"s{t}", "table": "srv6_end_dx4_table", "key": f"fc00:{t}::1",
                 "present": key in dump and "srv6_end_dx4" in dump})
    return rows


def pod_info(name):
    d = kjson(["pod", "-l", f"app={name}"])
    for it in d.get("items", []):
        if it["metadata"].get("deletionTimestamp"):
            continue
        cond = {c["type"]: c["lastTransitionTime"] for c in it["status"].get("conditions", [])}
        return {"pod": it["metadata"]["name"], "created": it["metadata"]["creationTimestamp"],
                "node": it["spec"].get("nodeName"), "ip": it["status"].get("podIP"), "conditions": cond}
    return {}


def pipelineruns(name):
    d = kjson(["pipelineruns"])
    rows = []
    for it in d.get("items", []):
        p = {x["name"]: x.get("value") for x in it["spec"].get("params", [])}
        if name in (p.get("deployName"), p.get("newDeployName"), p.get("oldDeployName"), p.get("vnfName")) \
                or name in it["metadata"]["name"]:
            c = (it.get("status", {}).get("conditions") or [{}])[0]
            rows.append({"name": it["metadata"]["name"], "pipeline": it["spec"].get("pipelineRef", {}).get("name"),
                         "created": it["metadata"]["creationTimestamp"], "completed": it.get("status", {}).get("completionTime"),
                         "reason": c.get("reason"), "params": p})
    return sorted(rows, key=lambda r: r["created"])


def make_request(rng, i):
    svc = TYPES[i % len(TYPES)]
    prof = rng.choice(list(PROFILES))
    cpu, ram = PROFILES[prof]
    jitter = rng.randint(0, max(1, int(cpu * 0.2)))
    return {"service_type": svc, "cpu_req": float(cpu + jitter), "ram_req": float(ram + jitter * 0.5),
            "msd_req": rng.randint(2, 5), "alert_flag": True, "source_node": rng.randint(0, 9),
            "destination_node": rng.randint(0, 9), "flow_id": f"e2e-{i:04d}", "_profile": prof}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target-new", type=int, default=30)
    ap.add_argument("--max-requests", type=int, default=600)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--probe-n", type=int, default=20)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--target-total", type=int, default=0,
                    help="stop when the total active VNF count reaches this (net growth; migrations replace)")
    a = ap.parse_args()
    out = a.out.resolve()
    (out / "requests").mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    for _ in range(a.start_index):
        make_request(rng, 0)
    _, st, _ = http("GET", "/orchestrate/state")
    baseline = {v["name"] for v in st["data"]["active_vnfs"]}
    (out / "baseline_active.json").write_text(json.dumps(sorted(baseline)))
    rows_path = out / "requests.csv"
    new_count = 0
    for i in range(a.start_index, a.start_index + a.max_requests):
        req = make_request(rng, i)
        prof = req.pop("_profile")
        rec = {"index": i, "request": req, "profile": prof, "t": {"submit_utc": utc()}}
        since = rec["t"]["submit_utc"]
        code, body, rtt = http("POST", "/orchestrate", req)
        rec["t"]["response_utc"] = utc()
        rec.update({"http_status": code, "api_rtt_ms": round(rtt, 3)})
        data = body.get("data") if isinstance(body, dict) else None
        if code != 200 or not isinstance(data, dict):
            rec["outcome"] = "rejected" if code == 409 else f"http_{code}"
            rec["error"] = body.get("detail", body) if isinstance(body, dict) else body
        else:
            name = data["vnf_name"]
            real = data.get("admitted_realization") or {}
            rec.update({"vnf_name": name, "placement": data["placement_node"], "route": data["routing_node"],
                        "realization": real, "migration_result": data.get("migration_result"),
                        "server_timings_ms": data.get("timings_ms")})
            status = {}
            mr = data.get("migration_result") or {}
            if mr:
                deadline = time.time() + 420
                while time.time() < deadline:
                    c, status, _ = http("GET", f"/orchestrate/migrations/{name}")
                    if c == 200 and status.get("status") in ("success", "error", "warning"):
                        break
                    time.sleep(1.0)
                rec["t"]["status_terminal_seen_utc"] = utc()
            rec["actuation_status"] = status
            blog = log_lines("3s-com-backend", since, name)
            clog = log_lines("gracious_jackson", since, "")
            steer_start = first_ts([l for l in clog if f"Installing rules for {name}" in l], "START")
            rec["t"].update({
                "backend_make_utc": first_ts(blog, "PHASE: MAKE"),
                "backend_ready_utc": first_ts(blog, "is READY"),
                "controller_steer_start_utc": steer_start,
            })
            after = [l for l in clog if steer_start and l.split(" ", 1)[0] >= steer_start]
            rec["t"]["controller_confirm_utc"] = first_ts(after, "confirm_steer_done = True")
            rec["controller_rule_log"] = [l for l in after[:20] if "route +" in l or "End.DX4" in l or "dx4" in l.lower()]
            rec["backend_log"] = blog[:40]
            rec["pipelineruns"] = pipelineruns(name)
            rec["pod"] = pod_info(name)
            sd = status.get("data") or {}
            path = real.get("switch_path") or []
            sids = real.get("sid_stack") or []
            if path:
                rec["t"]["readback_utc"] = utc()
                rec["readback"] = readback(path, sids)
            old = sd.get("old_vnf")
            rec["migration_old_vnf"] = old
            if old:
                rec["old_vnf_pod_after"] = pod_info(old)
            ok = sd.get("steer_status") == "CONFIRMED" or (
                status.get("status") == "success" and sd.get("recovery_state") in ("STEERED", "COMPLETED"))
            rec["recovery_state"] = sd.get("recovery_state")
            rec["outcome"] = "steered" if ok else f"actuation_{status.get('status')}_{sd.get('recovery_state')}"
            pod_ip = (sd.get("dynamic_endpoint") or {}).get("ip") or rec["pod"].get("ip")
            if ok and pod_ip and path:
                mode = "http" if req["service_type"] == "voc" else "icmp"
                pdir = out / "requests" / f"{i:04d}_{name}_probe"
                rec["t"]["probe_start_utc"] = utc()
                txt = sh([PY, str(TOOLS / "e2e_packet_probe.py"), "--out", str(pdir), "--mode", mode,
                          "--src-node", str(req["source_node"]), "--place-node", str(data["placement_node"]["id"]),
                          "--switch-path", ",".join(map(str, path)), "--sids", ",".join(sids),
                          "--pod-ip", pod_ip, "--request-id", name, "-n", str(a.probe_n)], timeout=900)
                try:
                    probe = json.loads((pdir / "probe.json").read_text())
                    rec["probe"] = {"mode": mode, **probe["summary"], "delta": probe["counter_delta"],
                                    "captured": probe["captured_packets"],
                                    "first_received_utc": next((h.get("sent_utc") for h in probe["http"] if h["marker_echoed_by_vnf"]), probe["t"].get("send_start_utc"))}
                except (OSError, ValueError, KeyError):
                    rec["probe"] = {"error": txt[-500:]}
            _, st, _ = http("GET", "/orchestrate/state")
            active_names = {v["name"] for v in st["data"]["active_vnfs"]}
            new_count = len(active_names - baseline)
            rec["active_total_after"] = len(active_names)
        rec["new_vnfs_after"] = new_count
        (out / "requests" / f"{i:04d}.json").write_text(json.dumps(rec, indent=2, default=str))
        row = {"index": i, "submit_utc": rec["t"]["submit_utc"], "service_type": req["service_type"],
               "source": req["source_node"], "msd_req": req["msd_req"], "cpu": req["cpu_req"], "ram": req["ram_req"],
               "http": rec["http_status"], "outcome": rec["outcome"], "vnf": rec.get("vnf_name", ""),
               "placement": (rec.get("placement") or {}).get("id", ""), "switch_path": "-".join(map(str, (rec.get("realization") or {}).get("switch_path", []))),
               "old_vnf": rec.get("migration_old_vnf") or "",
               "reason": (rec.get("error") or {}).get("reason_key", "") if isinstance(rec.get("error"), dict) else "",
               "message": (rec.get("error") or {}).get("message", "") if isinstance(rec.get("error"), dict) else "",
               "probe_sent": (rec.get("probe") or {}).get("sent", ""), "probe_recv": (rec.get("probe") or {}).get("app_received", ""),
               "new_vnfs_after": new_count}
        new_file = not rows_path.exists()
        with rows_path.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if new_file:
                w.writeheader()
            w.writerow(row)
        print(json.dumps(row), flush=True)
        if a.target_total and rec.get("active_total_after", 0) >= a.target_total:
            break
        if not a.target_total and new_count >= a.target_new:
            break
        time.sleep(0.3)


if __name__ == "__main__":
    main()
