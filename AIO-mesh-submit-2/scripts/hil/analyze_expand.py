#!/usr/bin/env python3
"""Stage timing/outcomes for inventory_expand.py records (driver-orchestrated actuation).

Output: <dir>/analysis/{per_request_stages.csv, stage_percentiles.csv, outcomes.json}
Usage: analyze_expand.py <expand_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from analyze_campaign import dsec, pct


def main():
    d = Path(sys.argv[1]).resolve()
    out = d / "analysis"
    out.mkdir(exist_ok=True)
    recs = [json.loads(f.read_text()) for f in sorted((d / "requests").glob("[0-9][0-9][0-9][0-9].json"))]
    rows = []
    for r in recs:
        t = r["t"]
        p = r.get("probe") or {}
        pod = r.get("pod") or {}
        rows.append({
            "index": r["index"], "service_type": r["request"]["service_type"], "msd_req": r["request"]["msd_req"],
            "http": r["http_status"], "outcome": r["outcome"], "vnf": r.get("vnf_name", ""),
            "reject_message": (r.get("error") or {}).get("message", "") if isinstance(r.get("error"), dict) else "",
            "placement": (r.get("placement") or {}).get("id", ""), "k8s_node": pod.get("node", ""),
            "switch_path": "-".join(map(str, (r.get("realization") or {}).get("switch_path", []))),
            "sid_depth": len((r.get("realization") or {}).get("sid_stack", [])),
            "admit_s": dsec(t["submit_utc"], t["response_utc"]),
            "deploy_submit_to_object_s": dsec(t.get("deploy_submit_utc"), t.get("deployment_object_seen_utc")),
            "deploy_submit_to_ready_s": dsec(t.get("deploy_submit_utc"), t.get("rollout_done_utc")),
            "pod_ready_k8s_minus_deploy_submit_s": dsec(t.get("deploy_submit_utc"), (pod.get("conditions") or {}).get("Ready")),
            "steer_submit_to_confirm_seen_s": dsec(t.get("steer_submit_utc"), t.get("steer_confirm_seen_utc")),
            "submit_to_steer_confirm_s": dsec(t["submit_utc"], t.get("steer_confirm_seen_utc")),
            "readback_all_present": all(x["present"] for x in r.get("readback", [])) if r.get("readback") else "",
            "ledger_profile_known": (r.get("ledger_record_after") or {}).get("accounting_unknown") is False if r.get("vnf_name") else "",
            "probe_mode": p.get("mode", ""), "probe_sent": p.get("sent", ""), "probe_received": p.get("app_received", ""),
            "probe_rtt_p50_ms": pct(p.get("rtt_total_ms") or [], 50),
            "msd_violation_delta": sum(v.get("msd_violation", 0) for v in (p.get("delta") or {}).values()) if p.get("delta") else "",
        })
    with (out / "per_request_stages.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    st = [r for r in rows if r["outcome"] == "steered"]
    with (out / "stage_percentiles.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stage", "population", "n", "p50", "p95", "p99", "min", "max"])
        for s in ("admit_s", "deploy_submit_to_object_s", "deploy_submit_to_ready_s", "steer_submit_to_confirm_seen_s",
                  "submit_to_steer_confirm_s", "probe_rtt_p50_ms"):
            pop = rows if s == "admit_s" else st
            v = [r[s] for r in pop if r[s] not in ("", None)]
            w.writerow([s, "all offered" if s == "admit_s" else "steered", len(v), pct(v, 50), pct(v, 95), pct(v, 99),
                        min(v) if v else "", max(v) if v else ""])
    oc = {"offered": len(rows), "admitted": sum(r["http"] == 200 for r in rows), "outcomes": dict(Counter(r["outcome"] for r in rows)),
          "reject_messages": dict(Counter(r["reject_message"] for r in rows if r["http"] == 409)),
          "steered": len(st), "readback_all_present": sum(r["readback_all_present"] is True for r in st),
          "ledger_profile_known": sum(r["ledger_profile_known"] is True for r in st),
          "probe_sent": sum(int(r["probe_sent"] or 0) for r in st), "probe_received": sum(int(r["probe_received"] or 0) for r in st),
          "by_node_delivery": {f"{k[0]}|{k[1]}": v for k, v in Counter((r["k8s_node"], r["probe_sent"] == r["probe_received"]) for r in st).items()}}
    (out / "outcomes.json").write_text(json.dumps(oc, indent=2))
    print(json.dumps(oc, indent=1))
    print((out / "stage_percentiles.csv").read_text())


if __name__ == "__main__":
    main()
