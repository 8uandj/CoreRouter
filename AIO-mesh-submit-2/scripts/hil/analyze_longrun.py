#!/usr/bin/env python3
"""Summarize one long run: admission records, Kubernetes readiness samples, data-plane probes.
Usage: analyze_longrun.py <long_run_dir>  (writes <dir>/analysis/longrun_summary.json)"""
import csv, glob, json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_campaign import pct

d = Path(sys.argv[1]).resolve(); out = d / "analysis"; out.mkdir(exist_ok=True)
s = {"run_dir": d.name}
m = d / "MODEL.json"
if m.exists(): s["model"] = json.loads(m.read_text())
recs = glob.glob(str(d / "admission" / "*" / "all_records.csv"))
if recs:
    r = list(csv.DictReader(open(recs[0])))
    lat = sorted(float(x["decision_latency_ms"]) for x in r if x["decision_latency_ms"])
    s["admission"] = {"source": str(Path(recs[0]).relative_to(d)), "requests": len(r),
        "accepted": sum(x["accepted"] == "True" for x in r), "status_codes": Counter(x["status_code"] for x in r),
        "reject_reason": Counter(x["reject_reason"] for x in r if x["accepted"] != "True"),
        "msd_req": Counter(x["msd_req"] for x in r), "timeouts": sum(x["status_code"] in ("", "0", "timeout") for x in r),
        "admitted_violations": sum(x["accepted"] == "True" and x["msd_violation"] == "True" for x in r),
        "decision_latency_ms": {"p50": pct(lat, 50), "p95": pct(lat, 95), "p99": pct(lat, 99)},
        "first_utc": r[0]["timestamp_utc"], "last_utc": r[-1]["timestamp_utc"]}
k = d / "kubernetes_readiness.csv"
if k.exists():
    k = list(csv.DictReader(open(k)))
    s["kubernetes"] = {"samples": len(k), "deployments": sorted({x["deployment_count"] for x in k}),
        "samples_all_ready": sum(x["ready_deployments"] == x["deployment_count"] and x["ready_replicas"] == x["desired_replicas"] for x in k),
        "min_ready_deployments": min(int(x["ready_deployments"]) for x in k)}
p = d / "dataplane" / "stability_probes.csv"
if p.exists():
    p = list(csv.DictReader(open(p))); rtt = sorted(float(x["rtt_p50_ms"]) for x in p if x["rtt_p50_ms"])
    s["dataplane"] = {"rounds": len(p), "targets": len(json.load(open(d / "dataplane" / "targets.json"))),
        "distinct_vnfs_probed": len({x["vnf"] for x in p}), "sent": sum(int(x["sent"] or 0) for x in p),
        "received": sum(int(x["received"] or 0) for x in p), "rounds_full": sum(x["sent"] == x["received"] != "0" for x in p),
        "rounds_zero": sum(x["received"] == "0" for x in p), "pod_ip_changed": sum(x["pod_ip_changed"] == "True" for x in p),
        "msd_violation_delta_total": sum(int(x["msd_violation_delta"] or 0) for x in p), "errors": sum(bool(x["error"]) for x in p),
        "rtt_p50_ms": {"p50": pct(rtt, 50), "p95": pct(rtt, 95)}, "first_utc": p[0]["utc"], "last_utc": p[-1]["utc"]}
st = d / "state_after_longrun.json"
if st.exists():
    n = json.loads(st.read_text())["data"]
    s["state_after"] = {"active_vnfs": len(n["active_vnfs"]), "node_cpu_util": {x["name"]: x["cpu_util"] for x in n["nodes"]},
                        "unaccounted_vnfs": n["unaccounted_vnfs"]}
(out / "longrun_summary.json").write_text(json.dumps(s, indent=1))
print(json.dumps(s, indent=1))
