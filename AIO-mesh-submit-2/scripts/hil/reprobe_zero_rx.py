#!/usr/bin/env python3
"""Re-probe steered requests whose campaign probe received 0 packets (kept as recorded).
Usage: reprobe_zero_rx.py <campaign_dir> <out_dir>"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataplane_stability_loop import pod, PY, TOOLS, utc
camp, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
rows = []
for f in sorted((camp / "requests").glob("[0-9][0-9][0-9][0-9].json")):
    r = json.loads(f.read_text()); p = r.get("probe") or {}
    if r.get("outcome") != "steered" or p.get("app_received"):
        continue
    info = pod(r["vnf_name"]); row = {"index": r["index"], "vnf": r["vnf_name"], "utc": utc(),
        "campaign_recv": p.get("app_received"), "pod": info}
    if not info.get("ip"):
        row["result"] = "vnf no longer exists (replaced by later migration)"
    else:
        real = r["realization"]; d = out / f"{r['index']:04d}_{r['vnf_name']}"
        subprocess.run([PY, str(TOOLS / "e2e_packet_probe.py"), "--out", str(d), "--mode", p.get("mode", "icmp"),
            "--src-node", str(r["request"]["source_node"]), "--place-node", str(r["placement"]["id"]),
            "--switch-path", ",".join(map(str, real["switch_path"])), "--sids", ",".join(real["sid_stack"]),
            "--pod-ip", info["ip"], "--request-id", r["vnf_name"], "-n", "20"], capture_output=True, timeout=900)
        s = json.loads((d / "probe.json").read_text())["summary"]
        row["result"] = {"sent": s["sent"], "received": s["app_received"]}
    rows.append(row); print(json.dumps(row), flush=True)
(out / "reprobe_summary.json").write_text(json.dumps(rows, indent=1))
