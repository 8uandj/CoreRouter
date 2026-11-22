#!/usr/bin/env python3
"""Long-running data-plane stability probes over already-steered VNFs.

Reads the campaign's per-request JSON files, keeps VNFs whose actuation reached
STEERED and whose first probe received packets, then every --interval-s seconds
probes the next VNF (round robin) with e2e_packet_probe.py (--no-capture except
every --capture-every-th probe). Each round also records the current Pod IP and
Ready condition (a changed IP is reported, never silently re-targeted) and the
per-switch msd_violation counters.

Usage: dataplane_stability_loop.py --campaign DIR --out DIR --hours 6 [--interval-s 120] [-n 20]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PY = "/home/CoreRouter/venv/bin/python"


def utc():
    return datetime.now(timezone.utc).isoformat()


def pod(name):
    try:
        d = json.loads(subprocess.run(["kubectl", "-n", "core-router", "get", "pod", "-l", f"app={name}", "-o", "json"],
                                      capture_output=True, text=True, timeout=60).stdout)
    except ValueError:
        return {}
    for it in d.get("items", []):
        if it["metadata"].get("deletionTimestamp"):
            continue
        ready = any(c["type"] == "Ready" and c["status"] == "True" for c in it["status"].get("conditions", []))
        return {"ip": it["status"].get("podIP"), "ready": ready, "node": it["spec"].get("nodeName"),
                "restarts": sum(cs.get("restartCount", 0) for cs in it["status"].get("containerStatuses", []))}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--interval-s", type=float, default=120.0)
    ap.add_argument("--capture-every", type=int, default=10)
    ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    targets = []
    files = [f for c in a.campaign for f in sorted((c / "requests").glob("[0-9][0-9][0-9][0-9].json"))]
    for f in files:
        r = json.loads(f.read_text())
        p = r.get("probe") or {}
        if r.get("outcome") == "steered" and p.get("app_received"):
            real = r["realization"]
            targets.append({"vnf": r["vnf_name"], "src": r["request"]["source_node"], "place": r["placement"]["id"],
                            "path": real["switch_path"], "sids": real["sid_stack"],
                            "ip0": ((r.get("actuation_status") or {}).get("data") or {}).get("dynamic_endpoint", {}).get("ip")
                                   or (r.get("pod") or {}).get("ip"),
                            "mode": p.get("mode", "icmp")})
    alive = []
    for t in targets:  # VNFs replaced by a later migration no longer exist
        if pod(t["vnf"]).get("ip"):
            alive.append(t)
    targets = alive
    (out / "targets.json").write_text(json.dumps(targets, indent=2))
    csv_path = out / "stability_probes.csv"
    end = time.time() + a.hours * 3600
    k = 0
    while time.time() < end and targets:
        t0 = time.time()
        t = targets[k % len(targets)]
        info = pod(t["vnf"])
        row = {"round": k, "utc": utc(), "vnf": t["vnf"], "mode": t["mode"], "switch_path": "-".join(map(str, t["path"])),
               "pod_ready": info.get("ready"), "pod_ip": info.get("ip"), "pod_ip_changed": info.get("ip") != t["ip0"],
               "pod_restarts": info.get("restarts"), "sent": 0, "received": 0, "rtt_p50_ms": "", "rtt_max_ms": "",
               "msd_violation_delta": "", "captured": "", "error": ""}
        if info.get("ip"):
            pdir = out / "probes" / f"{k:05d}_{t['vnf']}"
            args = [PY, str(TOOLS / "e2e_packet_probe.py"), "--out", str(pdir), "--mode", t["mode"],
                    "--src-node", str(t["src"]), "--place-node", str(t["place"]),
                    "--switch-path", ",".join(map(str, t["path"])), "--sids", ",".join(t["sids"]),
                    "--pod-ip", info["ip"], "--request-id", t["vnf"], "-n", str(a.n)]
            if k % a.capture_every:
                args.append("--no-capture")
            try:
                subprocess.run(args, capture_output=True, text=True, timeout=900)
                pr = json.loads((pdir / "probe.json").read_text())
                s = pr["summary"]
                rtts = s["rtt_total_ms"]
                row.update({"sent": s["sent"], "received": s["app_received"],
                            "rtt_p50_ms": rtts[len(rtts) // 2] if rtts else "", "rtt_max_ms": rtts[-1] if rtts else "",
                            "msd_violation_delta": sum(v["msd_violation"] for v in pr["counter_delta"].values()),
                            "captured": json.dumps(pr.get("captured_packets"))})
            except Exception as exc:  # recorded, never hidden
                row["error"] = repr(exc)[:300]
        else:
            row["error"] = "pod not found"
        new = not csv_path.exists()
        with csv_path.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if new:
                w.writeheader()
            w.writerow(row)
        print(json.dumps(row), flush=True)
        k += 1
        time.sleep(max(0.0, a.interval_s - (time.time() - t0)))


if __name__ == "__main__":
    main()
