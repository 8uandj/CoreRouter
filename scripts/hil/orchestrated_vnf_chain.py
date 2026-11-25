#!/usr/bin/env python3
"""Correlate one live /api/orchestrate VNF realization with dataplane receipts.

This exercises the existing pair-level orchestration contract for one VNF. It
does not claim that the policy selected the two-Pod relay chain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8000/api"
SDN = "http://127.0.0.1:8765"
PROBE = ROOT / "results/hil/e2e_tools/e2e_packet_probe.py"
PYTHON = ROOT / "venv/bin/python"


def utc():
    return datetime.now(timezone.utc).isoformat()


def http(base, method, path, payload=None, timeout=20):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, code = resp.read(), resp.status
    except urllib.error.HTTPError as exc:
        raw, code = exc.read(), exc.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, {"raw": raw.decode(errors="replace")}


def run(args, timeout=120):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("{} failed ({}): {}".format(" ".join(map(str, args)), result.returncode,
                                                        (result.stderr or result.stdout)[-1500:]))
    return result.stdout


def kubectl_json(*args):
    return json.loads(run(["kubectl", "-n", "core-router", "get", *args, "-o", "json"]))


def source_hashes(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def pod_for(name):
    doc = kubectl_json("pods", "-l", "app={}".format(name))
    for pod in doc.get("items", []):
        conditions = {c["type"]: c.get("status") for c in pod.get("status", {}).get("conditions", [])}
        if pod.get("metadata", {}).get("deletionTimestamp") is None:
            return {"name": pod["metadata"]["name"], "ip": pod.get("status", {}).get("podIP"),
                    "node": pod.get("spec", {}).get("nodeName"), "conditions": conditions,
                    "ready": conditions.get("Ready") == "True"}
    return {}


def pipeline_runs_for(name):
    rows = []
    for pr in kubectl_json("pipelineruns").get("items", []):
        params = {p["name"]: p.get("value") for p in pr.get("spec", {}).get("params", [])}
        if name not in params.values() and name not in pr["metadata"]["name"]:
            continue
        condition = next((c for c in pr.get("status", {}).get("conditions", [])
                          if c.get("type") == "Succeeded"), {})
        rows.append({"name": pr["metadata"]["name"],
                     "pipeline": pr.get("spec", {}).get("pipelineRef", {}).get("name"),
                     "created": pr["metadata"].get("creationTimestamp"),
                     "completed": pr.get("status", {}).get("completionTime"),
                     "reason": condition.get("reason"), "params": params})
    return rows


def readback(path):
    import socket
    rows = []
    for cur, nxt in zip(path, path[1:]):
        dump = run([str(ROOT / "results/hil/e2e_tools/p4cli.sh"), "s{}".format(cur), "table_dump routing_v6"])
        key = socket.inet_pton(socket.AF_INET6, "fc00:{}::1".format(nxt)).hex()
        rows.append({"switch": "s{}".format(cur), "table": "routing_v6", "key": "fc00:{}::1/128".format(nxt),
                     "present": key in dump and "ipv6_forward" in dump, "raw": dump})
    terminal = path[-1]
    dump = run([str(ROOT / "results/hil/e2e_tools/p4cli.sh"), "s{}".format(terminal),
                "table_dump srv6_end_dx4_table"])
    key = socket.inet_pton(socket.AF_INET6, "fc00:{}::1".format(terminal)).hex()
    rows.append({"switch": "s{}".format(terminal), "table": "srv6_end_dx4_table",
                 "key": "fc00:{}::1".format(terminal),
                 "present": key in dump and "srv6_end_dx4" in dump, "raw": dump})
    return rows


def run_probe(out, name, req, placement, realization, pod, count):
    path = realization["switch_path"]
    if not pod.get("ip") or not pod.get("ready") or not path:
        raise RuntimeError("probe gated: Ready Pod, IP, or admitted P4 path missing")
    probe_dir = out / "probes" / ("pilot3" if count == 3 else "run20")
    cmd = [str(PYTHON), str(PROBE), "--out", str(probe_dir), "--mode", "http", "--endpoint", "echo",
           "--src-node", str(req["source_node"]), "--place-node", str(placement["id"]),
           "--switch-path", ",".join(map(str, path)), "--sids", ",".join(realization["sid_stack"]),
           "--pod-ip", pod["ip"], "--request-id", name, "-n", str(count)]
    run(cmd, timeout=300)
    doc = json.loads((probe_dir / "probe.json").read_text())
    if doc["summary"]["sent"] != count or doc["summary"]["app_received"] != count:
        raise RuntimeError("probe receipt gate failed: {}".format(doc["summary"]))
    # Captures use broad host/IP filters. TCP handshake, ACKs, and unrelated
    # live traffic add frames; the app marker count is the per-request receipt.
    if any(doc["captured_packets"].get(k, 0) < count for k in ("src_egress_srv6", "place_host_decap")):
        raise RuntimeError("PCAP evidence missing expected traffic: {}".format(doc["captured_packets"]))
    return {"directory": str(probe_dir.relative_to(out)), "summary": doc["summary"],
            "counter_delta": doc["counter_delta"], "captured_packets": doc["captured_packets"],
            "http_codes": doc["summary"].get("http_codes", []),
            "app_response_receipts": sum(bool(x.get("marker_echoed_by_vnf")) for x in doc.get("http", [])),
            "probe_sha256": hashlib.sha256((probe_dir / "probe.json").read_bytes()).hexdigest()}


def write_manifest(out, rec):
    evidence = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in ("manifest.json", "manifest.json.sha256"):
            evidence[str(path.relative_to(out))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"run_id": rec["request"]["flow_id"], "vnf_name": rec.get("vnf_name"),
                "evidence_class": rec["evidence_class"], "source_sha256": source_hashes(
                    [Path(__file__).resolve(), PROBE, ROOT / "scripts/hil/live_inventory.py"]),
                "evidence_sha256": evidence,
                "scope_note": "This orchestration request realizes one VNF. The two-Pod relay-chain run is separate evidence and was not selected by this request."}
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out / "manifest.json.sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  manifest.json\n")


def complete_pilot(rec, out, record_path):
    name, real = rec["vnf_name"], rec["realization"]
    status = {}
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        sc, status = http(API, "GET", "/orchestrate/migrations/{}".format(name))
        if sc == 200 and status.get("status") in ("success", "error", "warning"):
            break
        time.sleep(1)
    rec["t"]["terminal_status_utc"] = utc()
    rec["actuation_status"] = status
    rec["pod"] = pod_for(name)
    rec["pipelineruns"] = pipeline_runs_for(name)
    path = real.get("switch_path", [])
    rec["p4_readback"] = readback(path) if path else []
    code, steer_status = http(SDN, "GET", "/steer/status")
    rec["controller_steer_status_http"], rec["controller_steer_status"] = code, steer_status
    sd = status.get("data", {})
    ctrl = steer_status if isinstance(steer_status, dict) else {}
    identity_ok = (sd.get("steer_operation_id") == real.get("operation_id")
                   and ctrl.get("new_deploy") == name
                   and ctrl.get("request_id") == real.get("request_id")
                   and ctrl.get("operation_id") == real.get("operation_id")
                   and ctrl.get("topology_hash") == real.get("topology_hash")
                   and ctrl.get("profile_id") == real.get("profile_id")
                   and ctrl.get("p4_topology_hash") == real.get("p4_topology_hash"))
    rec["correlation_checks"] = {
        "request_operation_identity": identity_ok,
        "pod_ready": rec["pod"].get("ready", False),
        "pipelinerun_succeeded": any(p.get("reason") == "Succeeded" for p in rec["pipelineruns"]),
        "readback_all_present": bool(rec["p4_readback"]) and all(x["present"] for x in rec["p4_readback"]),
        "steering_confirmed": sd.get("steer_status") == "CONFIRMED",
    }
    record_path.write_text(json.dumps(rec, indent=2) + "\n")
    if not all(rec["correlation_checks"].values()):
        raise RuntimeError("orchestration correlation gate failed; packet probe not started")
    rec["pilot"] = run_probe(out, name, rec["request"], rec["placement"], real, rec["pod"], 3)
    rec["t"]["pilot_done_utc"] = utc()
    record_path.write_text(json.dumps(rec, indent=2) + "\n")
    write_manifest(out, rec)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stage", choices=("pilot", "resume", "run20"), required=True)
    ap.add_argument("--record", type=Path, help="existing successful pilot record for --stage run20")
    ap.add_argument("--flow-id", help="unique experiment service identity")
    ap.add_argument("--source-node", type=int, default=0)
    ap.add_argument("--msd-depth", type=int, default=2)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / "orchestration.json"
    if args.stage == "pilot":
        if record_path.exists():
            raise RuntimeError("refusing to overwrite existing orchestration record")
        inventory_path = out / "baseline_inventory.json"
        run([str(PYTHON), str(ROOT / "scripts/hil/live_inventory.py"), "--out", str(inventory_path)])
        pre_state_code, pre_state = http(API, "GET", "/orchestrate/state")
        if pre_state_code != 200 or pre_state.get("data", {}).get("unaccounted_vnfs"):
            raise RuntimeError("baseline state unavailable or has unaccounted VNFs")
        if not args.flow_id:
            raise RuntimeError("--stage pilot requires --flow-id")
        req = {"flow_id": args.flow_id, "service_type": "voc", "cpu_req": 4.0,
               "ram_req": 2.0, "msd_req": args.msd_depth, "alert_flag": True,
               "source_node": args.source_node, "destination_node": 9}
        rec = {"evidence_class": "single-VNF orchestration plus separate two-Pod chain evidence",
               "request": req, "t": {"baseline_utc": utc()},
               "baseline_inventory": json.loads(inventory_path.read_text()),
               "baseline_state": pre_state["data"]}
        code, body = http(API, "POST", "/orchestrate", req, timeout=45)
        rec["t"]["response_utc"] = utc()
        rec["http_status"], rec["response"] = code, body
        data = body.get("data", {}) if isinstance(body, dict) else {}
        if code != 200 or not data.get("migration_result"):
            record_path.write_text(json.dumps(rec, indent=2) + "\n")
            raise RuntimeError("request did not enter the admitted alert actuation path")
        name = data["vnf_name"]
        rec.update({"vnf_name": name, "placement": data["placement_node"], "route": data["routing_node"],
                    "realization": data["admitted_realization"], "migration_result": data["migration_result"]})
        record_path.write_text(json.dumps(rec, indent=2) + "\n")
        complete_pilot(rec, out, record_path)
    elif args.stage == "resume":
        rec = json.loads(record_path.read_text())
        if not rec.get("vnf_name") or not rec.get("realization", {}).get("operation_id"):
            raise RuntimeError("no admitted realization to resume in orchestration record")
        complete_pilot(rec, out, record_path)
    else:
        if not args.record or not args.record.is_file():
            raise RuntimeError("--stage run20 requires --record from an accepted pilot")
        rec = json.loads(args.record.read_text())
        if not all(rec.get("correlation_checks", {}).values()) or rec.get("pilot", {}).get("summary", {}).get("app_received") != 3:
            raise RuntimeError("20-packet stage refused: pilot or orchestration gate did not pass")
        req, name = rec["request"], rec["vnf_name"]
        rec["run20"] = run_probe(out, name, req, rec["placement"], rec["realization"], rec["pod"], 20)
        rec["t"]["run20_done_utc"] = utc()
        record_path.write_text(json.dumps(rec, indent=2) + "\n")
        write_manifest(out, rec)
    print(json.dumps({"run": args.flow_id, "stage": args.stage,
                      "vnf": rec.get("vnf_name"), "correlation": rec.get("correlation_checks"),
                      "pilot": rec.get("pilot", {}).get("summary"),
                      "run20": rec.get("run20", {}).get("summary")}))


if __name__ == "__main__":
    main()
