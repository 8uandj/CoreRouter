#!/usr/bin/env python3
"""Final inventory: ledger profile x Kubernetes Deployment/Pod x creation evidence.

Usage: inventory_table.py <run_dir> <out_csv>
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


def main():
    run, out = Path(sys.argv[1]), Path(sys.argv[2])
    state = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/orchestrate/state", timeout=30).read())["data"]
    names = [n["name"] for n in state["nodes"]]
    deps = json.loads(subprocess.run(["kubectl", "-n", "core-router", "get", "deploy", "-o", "json"],
                                     capture_output=True, text=True).stdout)["items"]
    pods = json.loads(subprocess.run(["kubectl", "-n", "core-router", "get", "pods", "-o", "json"],
                                     capture_output=True, text=True).stdout)["items"]
    origin = {}
    for kind, d in (("backend e2e campaign (alert, backend MBB)", run / "campaign" / "requests"),
                    ("driver-orchestrated (admission + /api/deploy + /steer)", run / "expand" / "requests")):
        for f in sorted(d.glob("[0-9][0-9][0-9][0-9].json")):
            r = json.loads(f.read_text())
            if r.get("vnf_name"):
                origin[r["vnf_name"]] = f"{kind} #{r['index']}"
    for p in run.glob("campaign/recovered_*"):
        st = json.loads((p / "actuation_status.json").read_text())
        origin[st["data"]["new_vnf"]] = f"backend e2e campaign (record recovered) {p.name}"
    b = run / "actuation_burst" / "burst.json"
    if b.exists():
        for r in json.loads(b.read_text())["results"]:
            if r["http"] == 200:
                origin[r["body"]["data"]["vnf_name"]] = f"backend actuation burst #{r['i']}"
    origin["vnf-voc-237923df"] = "pilot2 (backend e2e)"
    rows = []
    for v in sorted(state["active_vnfs"], key=lambda x: x["name"]):
        dep = next((d for d in deps if d["metadata"]["name"] == v["name"]), {})
        pod = next((p for p in pods if p["metadata"].get("labels", {}).get("app") == v["name"]
                    and not p["metadata"].get("deletionTimestamp")), {})
        rows.append({"vnf": v["name"], "cpu_req": v["cpu_req"], "ram_req": v["ram_req"], "msd_req": v["msd_req"],
                     "v_place": v["v_place"], "placement": names[v["v_place"]], "v_route": v["v_route"], "route": names[v["v_route"]],
                     "accounting_unknown": v.get("accounting_unknown"), "deployment_ready": v.get("deployment_ready"),
                     "k8s_ready": f"{(dep.get('status') or {}).get('readyReplicas', 0)}/{(dep.get('spec') or {}).get('replicas', '')}",
                     "image": ";".join(c["image"] for c in dep.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])) if dep else "",
                     "k8s_node": (pod.get("spec") or {}).get("nodeName", ""), "pod_ip": (pod.get("status") or {}).get("podIP", ""),
                     "created_by": origin.get(v["name"], "baseline (seeded 2026-11-17)" if v["name"].startswith("vnf-attack") else "unknown")})
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows;", sum(r["accounting_unknown"] is False for r in rows), "known profiles;",
          sum(r["k8s_ready"] == "1/1" for r in rows), "ready")


if __name__ == "__main__":
    main()
