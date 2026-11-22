#!/usr/bin/env python3
"""Grow the HIL inventory with admission-profiled VNFs, steered and probed e2e.

Evidence class: "driver-orchestrated actuation". Per offered request:
  1. POST /api/orchestrate with alert off: the runtime policy selects placement and
     route, the path compiler and admission check SID depth/MSD/CPU/RAM, and the
     durable ledger records the profile under the returned vnf_name (pending).
  2. POST /api/deploy with exactly that name, the Tekton type for the service and
     the placement's location label (Tekton vnf-lcm-fast pipeline).
  3. Wait for the Deployment rollout (<=180 s); the next backend sync promotes the
     pending record to a deployed record with the admitted profile.
  4. POST controller /steer with the admitted realization identity (request ID,
     operation ID, topology/profile/P4 hashes, switch path, SID stack) and wait
     for confirm_steer_done for that request ID.
  5. Read back the path rules, then probe packets (HTTP marker for vVOC, ICMP
     marker otherwise).
Usage: inventory_expand.py --out DIR --target-total 37 --max-requests 600 --seed 3030
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import time
import urllib.request
from pathlib import Path

import e2e_campaign as ec

SDN = "http://127.0.0.1:8765"
TYPE = {"voc": "voc", "idps": "idps", "nat": "nat", "lb": "lb", "firewall": "firewall",
        "data": "router", "video": "router", "router": "router"}
LOC = {"Hanoi": "hanoi-1", "HaiPhong": "haiphong-1", "NinhBinh": "ninhbinh-1", "Vinh": "vinh-1", "Hue": "hue-1",
       "DaNang": "danang-1", "QuyNhon": "quynhon-1", "NhaTrang": "nhatrang-1", "HoChiMinh": "hcm-1", "CanTho": "cantho-1"}


def sdn(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(SDN + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read() or b"{}")


def finish(rec, out, probe_n):
    """Steps 3-5 for an admitted record whose Deployment was requested."""
    req, name, real, place = rec["request"], rec["vnf_name"], rec["realization"], rec["placement"]
    svc, i = req["service_type"], rec["index"]
    deadline = time.time() + 180
    while time.time() < deadline:
        if subprocess.run(["kubectl", "-n", "core-router", "get", f"deployment/{name}"],
                          capture_output=True).returncode == 0:
            break
        time.sleep(2)
    rec["t"]["deployment_object_seen_utc"] = ec.utc()
    roll = subprocess.run(["kubectl", "-n", "core-router", "rollout", "status", f"deployment/{name}",
                           "--timeout=240s"], capture_output=True, text=True)
    rec["t"]["rollout_done_utc"] = ec.utc()
    rec["rollout"] = {"rc": roll.returncode, "out": (roll.stdout + roll.stderr)[-400:]}
    pod = ec.pod_info(name)
    rec["pod"] = pod
    if roll.returncode or not pod.get("ip"):
        rec["outcome"] = "deploy_not_ready"
    else:
        payload = {"request_id": real["request_id"], "operation_id": real["operation_id"],
                   "topology_hash": real["topology_hash"], "profile_id": real["profile_id"],
                   "p4_topology_hash": real["p4_topology_hash"], "new_deploy": name,
                   "switch_path": real["switch_path"], "sid_stack": real["sid_stack"]}
        rec["steer_payload"] = payload
        rec["t"]["steer_submit_utc"] = ec.utc()
        sc, sb = sdn("POST", "/steer", payload)
        confirmed, st = False, {}
        for _ in range(60):
            _, st = sdn("GET", "/steer/status")
            if st.get("request_id") == name and st.get("steer_state") in ("done", "failed", "FAILED", "DONE") \
                    or (st.get("request_id") == name and st.get("confirm_steer_done")):
                confirmed = bool(st.get("confirm_steer_done"))
                break
            time.sleep(0.25)
        rec["t"]["steer_confirm_seen_utc"] = ec.utc()
        rec.update({"steer_http": sc, "steer_status": st})
        rec["t"]["readback_utc"] = ec.utc()
        rec["readback"] = ec.readback(real["switch_path"], real["sid_stack"])
        if not confirmed:
            rec["outcome"] = "steer_not_confirmed"
        else:
            rec["outcome"] = "steered"
            mode = "http" if svc == "voc" else "icmp"
            pdir = out / "requests" / f"{i:04d}_{name}_probe"
            rec["t"]["probe_start_utc"] = ec.utc()
            ec.sh([ec.PY, str(ec.TOOLS / "e2e_packet_probe.py"), "--out", str(pdir), "--mode", mode,
                   "--src-node", str(req["source_node"]), "--place-node", str(place["id"]),
                   "--switch-path", ",".join(map(str, real["switch_path"])),
                   "--sids", ",".join(real["sid_stack"]), "--pod-ip", pod["ip"],
                   "--request-id", name, "-n", str(probe_n)], timeout=900)
            try:
                pr = json.loads((pdir / "probe.json").read_text())
                rec["probe"] = {"mode": mode, **pr["summary"], "delta": pr["counter_delta"],
                                "captured": pr["captured_packets"]}
            except (OSError, ValueError, KeyError) as exc:
                rec["probe"] = {"error": repr(exc)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target-total", type=int, default=37)
    ap.add_argument("--max-requests", type=int, default=600)
    ap.add_argument("--seed", type=int, default=3030)
    ap.add_argument("--probe-n", type=int, default=20)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--finish", type=int, default=None, help="complete steps 3-5 for requests/<INDEX>.json")
    a = ap.parse_args()
    out = a.out.resolve()
    if a.finish is not None:
        f = out / "requests" / f"{a.finish:04d}.json"
        rec = json.loads(f.read_text())
        rec["finished_by_rerun_utc"] = ec.utc()
        finish(rec, out, a.probe_n)
        f.write_text(json.dumps(rec, indent=2, default=str))
        print(rec["outcome"], (rec.get("probe") or {}).get("app_received"))
        return
    (out / "requests").mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    rows_path = out / "requests.csv"
    for _ in range(a.start_index):
        ec.make_request(rng, 0)
    for i in range(a.start_index, a.start_index + a.max_requests):
        req = ec.make_request(rng, i)
        prof = req.pop("_profile")
        req["alert_flag"] = False
        req["flow_id"] = f"expand-{i:04d}"
        rec = {"index": i, "request": req, "profile": prof, "evidence_class": "driver-orchestrated actuation",
               "t": {"submit_utc": ec.utc()}}
        code, body, rtt = ec.http("POST", "/orchestrate", req)
        rec["t"]["response_utc"] = ec.utc()
        rec.update({"http_status": code, "api_rtt_ms": round(rtt, 3)})
        data = body.get("data") if isinstance(body, dict) else None
        if code != 200 or not isinstance(data, dict):
            rec["outcome"] = "rejected" if code == 409 else f"http_{code}"
            rec["error"] = body.get("detail", body) if isinstance(body, dict) else body
        else:
            name, real = data["vnf_name"], data.get("admitted_realization") or {}
            place = data["placement_node"]
            rec.update({"vnf_name": name, "placement": place, "route": data["routing_node"], "realization": real,
                        "server_timings_ms": data.get("timings_ms"), "migration_result": data.get("migration_result")})
            if not real.get("switch_path") or real.get("profile_id") != "p4-path-candidate-v1":
                rec["outcome"] = "admitted_without_p4_path"
            else:
                svc = req["service_type"]
                rec["t"]["deploy_submit_utc"] = ec.utc()
                c, dbody, _ = ec.http("POST", "/deploy", {"name": name, "type": TYPE.get(svc, "router"),
                                                          "profile": "standard", "location": LOC[place["name"]]})
                rec["deploy_response"] = dbody
                finish(rec, out, a.probe_n)
        _, st, _ = ec.http("GET", "/orchestrate/state")
        active = st["data"]["active_vnfs"]
        rec["active_total_after"] = len(active)
        rec["ledger_record_after"] = next((v for v in active if v["name"] == rec.get("vnf_name")), None)
        (out / "requests" / f"{i:04d}.json").write_text(json.dumps(rec, indent=2, default=str))
        row = {"index": i, "submit_utc": rec["t"]["submit_utc"], "service_type": req["service_type"],
               "source": req["source_node"], "msd_req": req["msd_req"], "cpu": req["cpu_req"], "ram": req["ram_req"],
               "http": code, "outcome": rec["outcome"], "vnf": rec.get("vnf_name", ""),
               "placement": (rec.get("placement") or {}).get("id", ""), "k8s_node": (rec.get("pod") or {}).get("node", ""),
               "switch_path": "-".join(map(str, (rec.get("realization") or {}).get("switch_path", []))),
               "message": (rec.get("error") or {}).get("message", "") if isinstance(rec.get("error"), dict) else "",
               "probe_sent": (rec.get("probe") or {}).get("sent", ""), "probe_recv": (rec.get("probe") or {}).get("app_received", ""),
               "active_total_after": len(active)}
        new = not rows_path.exists()
        with rows_path.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if new:
                w.writeheader()
            w.writerow(row)
        print(json.dumps(row), flush=True)
        if len(active) >= a.target_total:
            break
        time.sleep(0.3)


if __name__ == "__main__":
    main()
