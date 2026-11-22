#!/usr/bin/env python3
"""Per-request stage timing and outcome accounting for an e2e campaign directory.

Output (in <campaign>/analysis/): per_request_stages.csv, stage_percentiles.csv,
outcomes.json. Percentiles use the rounded-rank rule of the testbed metrics; every
statistic reports its denominator n. Kubernetes condition times have 1-s
resolution; docker log times are sub-millisecond; status polling is 1 s.
Usage: analyze_campaign.py <campaign_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def ts(x):
    if not x:
        return None
    x = x.replace("Z", "+00:00")
    if "." in x:
        head, rest = x.split(".", 1)
        import re
        frac = re.match(r"\d*", rest).group(0)
        tz = rest[len(frac):] or "+00:00"
        x = f"{head}.{frac[:6]}{tz}"
    if "+" not in x[10:] and "-" not in x[10:]:
        x += "+00:00"
    return datetime.fromisoformat(x)


def dsec(a, b):
    a, b = ts(a), ts(b)
    return round((b - a).total_seconds(), 3) if a and b else ""


def pct(v, q):
    s = sorted(v)
    return s[max(0, min(len(s) - 1, round(q / 100 * (len(s) - 1))))] if s else ""


LIVE_PR = {}


def load_pipelineruns():
    """PipelineRun timing re-read at analysis time (campaign snapshots may predate completion)."""
    import subprocess
    d = json.loads(subprocess.run(["kubectl", "-n", "core-router", "get", "pipelineruns", "-o", "json"],
                                  capture_output=True, text=True).stdout)
    for it in d["items"]:
        p = {x["name"]: x.get("value") for x in it["spec"].get("params", [])}
        name = p.get("deployName") or p.get("newDeployName")
        if name and it["spec"].get("pipelineRef", {}).get("name") in ("vnf-lcm-fast", "vnf-migrate-single"):
            LIVE_PR[name] = {"name": it["metadata"]["name"], "created": it["metadata"]["creationTimestamp"],
                             "completed": it.get("status", {}).get("completionTime")}


def main():
    c = Path(sys.argv[1]).resolve()
    load_pipelineruns()
    (c / "analysis").mkdir(exist_ok=True)
    (c / "analysis" / "pipelineruns_at_analysis.json").write_text(json.dumps(LIVE_PR, indent=1))
    out = c / "analysis"
    out.mkdir(exist_ok=True)
    recs = [json.loads(f.read_text()) for f in sorted((c / "requests").glob("[0-9][0-9][0-9][0-9].json"))]
    rows = []
    for r in recs:
        t = r["t"]
        row = {"index": r["index"], "service_type": r["request"]["service_type"], "msd_req": r["request"]["msd_req"],
               "http": r["http_status"], "outcome": r["outcome"], "vnf": r.get("vnf_name", ""),
               "reject_message": (r.get("error") or {}).get("message", "") if isinstance(r.get("error"), dict) else "",
               "admit_s": dsec(t["submit_utc"], t["response_utc"])}
        if r.get("vnf_name"):
            pr = LIVE_PR.get(r["vnf_name"], {})
            pod = r.get("pod") or {}
            cond = pod.get("conditions") or {}
            probe = r.get("probe") or {}
            row.update({
                "placement": r["placement"]["id"], "k8s_node": pod.get("node", ""),
                "switch_path": "-".join(map(str, (r.get("realization") or {}).get("switch_path", []))),
                "sid_depth": len((r.get("realization") or {}).get("sid_stack", [])),
                "migration_old_vnf": r.get("migration_old_vnf") or "",
                "submit_to_make_s": dsec(t["submit_utc"], t.get("backend_make_utc")),
                "pipelinerun_created_minus_make_s": dsec(t.get("backend_make_utc"), pr.get("created")),
                "pipelinerun_duration_s": dsec(pr.get("created"), pr.get("completed")),
                "make_to_pod_ready_k8s_s": dsec(t.get("backend_make_utc"), cond.get("Ready")),
                "make_to_backend_ready_s": dsec(t.get("backend_make_utc"), t.get("backend_ready_utc")),
                "backend_ready_to_steer_start_s": dsec(t.get("backend_ready_utc"), t.get("controller_steer_start_utc")),
                "rule_install_and_confirm_s": dsec(t.get("controller_steer_start_utc"), t.get("controller_confirm_utc")),
                "submit_to_steer_confirm_s": dsec(t["submit_utc"], t.get("controller_confirm_utc")),
                "readback_all_present": all(x["present"] for x in r.get("readback", [])) if r.get("readback") else "",
                "probe_mode": probe.get("mode", ""), "probe_sent": probe.get("sent", ""),
                "probe_received": probe.get("app_received", ""), "probe_loss": probe.get("loss", ""),
                "probe_rtt_p50_ms": pct(probe.get("rtt_total_ms") or [], 50),
                "msd_violation_delta": sum(v.get("msd_violation", 0) for v in (probe.get("delta") or {}).values()) if probe.get("delta") else "",
                "captured": json.dumps(probe.get("captured", "")),
            })
        rows.append(row)
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[-1].keys()).index(k) if k in rows[-1] else 999)
    with (out / "per_request_stages.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    stages = ["admit_s", "submit_to_make_s", "pipelinerun_duration_s", "make_to_pod_ready_k8s_s", "make_to_backend_ready_s",
              "backend_ready_to_steer_start_s", "rule_install_and_confirm_s", "submit_to_steer_confirm_s", "probe_rtt_p50_ms"]
    with (out / "stage_percentiles.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stage", "population", "n", "p50", "p95", "p99", "min", "max"])
        for s in stages:
            pop = "all offered" if s == "admit_s" else "steered requests"
            v = [r[s] for r in rows if r.get(s) not in ("", None) and (s == "admit_s" or r["outcome"] == "steered")]
            w.writerow([s, pop, len(v), pct(v, 50), pct(v, 95), pct(v, 99), min(v) if v else "", max(v) if v else ""])
    steered = [r for r in rows if r["outcome"] == "steered"]
    oc = {"offered": len(rows), "admitted_http200": sum(r["http"] == 200 for r in rows),
          "outcomes": dict(Counter(r["outcome"] for r in rows)),
          "reject_messages": dict(Counter(r["reject_message"] for r in rows if r["http"] == 409)),
          "steered": len(steered), "migrations": sum(bool(r.get("migration_old_vnf")) for r in rows),
          "readback_all_present": sum(r.get("readback_all_present") is True for r in steered),
          "probe_packets_sent": sum(int(r["probe_sent"] or 0) for r in steered),
          "probe_packets_received": sum(int(r["probe_received"] or 0) for r in steered),
          "probes_with_full_delivery": sum(r["probe_sent"] != "" and r["probe_sent"] == r["probe_received"] for r in steered),
          "by_k8s_node": dict(Counter((r.get("k8s_node"), r["probe_sent"] == r["probe_received"]) for r in steered).most_common()) if steered else {},
          }
    oc["by_k8s_node"] = {f"{k[0]}|full_delivery={k[1]}": v for k, v in Counter((r.get("k8s_node"), r["probe_sent"] == r["probe_received"]) for r in steered).items()}
    (out / "outcomes.json").write_text(json.dumps(oc, indent=2))
    print(json.dumps(oc, indent=1))
    print((out / "stage_percentiles.csv").read_text())


if __name__ == "__main__":
    main()
