#!/usr/bin/env python3
"""Make-before-break ordering and timing for every migration in the campaign/burst.

For each admitted request whose actuation named an old VNF:
  new Ready (backend log) <= controller confirm_steer_done <= BREAK request (backend
  log 'Deleting old VNF: <old>') <= terminal status (COMPLETED / BREAK_UNCONFIRMED).
Ordering violations are reported, never dropped. No packet continuity is claimed:
clients address the Pod IP, which changes on migration.
Usage: analyze_mbb.py <run_dir> [campaign_subdir=campaign] [out_subdir=analysis_mbb] [--no-burst]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from analyze_campaign import dsec, pct, ts


def main():
    run = Path(sys.argv[1]).resolve()
    pos = [x for x in sys.argv[2:] if not x.startswith("--")]
    camp = pos[0] if pos else "campaign"
    outname = pos[1] if len(pos) > 1 else "analysis_mbb"
    logs = []
    for f in sorted((run / "cluster_changes").glob("backend_container_log_*.log")):
        logs += f.read_text(errors="replace").splitlines()
    breaks = {}
    for l in logs:
        if "Deleting old VNF: " in l:
            old = l.rsplit("Deleting old VNF: ", 1)[1].strip()
            breaks.setdefault(old, l.split(" ", 1)[0])
    recs = []
    for f in sorted((run / camp / "requests").glob("[0-9][0-9][0-9][0-9].json")):
        r = json.loads(f.read_text())
        old = r.get("migration_old_vnf")
        if old:
            recs.append(("campaign", r["index"], r["vnf_name"], old, r["t"].get("backend_ready_utc"),
                         r["t"].get("controller_confirm_utc"), r["t"].get("status_terminal_seen_utc"),
                         (r.get("actuation_status") or {}).get("data", {}).get("recovery_state")))
    burst = run / "actuation_burst" / "burst.json"
    if burst.exists() and "--no-burst" not in sys.argv:
        for r in json.loads(burst.read_text())["results"]:
            st = (r.get("actuation_status") or {}).get("data") or {}
            if r["http"] == 200 and st.get("old_vnf"):
                recs.append(("burst", r["i"], r["body"]["data"]["vnf_name"], st["old_vnf"], r.get("backend_ready_utc"),
                             r.get("controller_confirm_utc"), r.get("terminal_seen_utc"), st.get("recovery_state")))
    rows = []
    for src, idx, new, old, ready, confirm, term, state in recs:
        brk = breaks.get(old, "")
        ordered = bool(ready and confirm and brk) and ts(ready) <= ts(confirm) <= ts(brk)
        rows.append({"source": src, "index": idx, "new_vnf": new, "old_vnf": old, "final_state": state,
                     "new_ready_utc": ready, "steer_confirm_utc": confirm, "break_request_utc": brk,
                     "terminal_seen_utc": term, "ready_to_confirm_s": dsec(ready, confirm),
                     "confirm_to_break_s": dsec(confirm, brk), "break_to_terminal_s": dsec(brk, term),
                     "make_before_break_order_ok": ordered})
    out = run / outname
    out.mkdir(exist_ok=True)
    with (out / "mbb_per_migration.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summ = {"migrations": len(rows), "order_ok": sum(r["make_before_break_order_ok"] for r in rows),
            "final_states": {s: sum(r["final_state"] == s for r in rows) for s in {r["final_state"] for r in rows}}}
    for k in ("ready_to_confirm_s", "confirm_to_break_s", "break_to_terminal_s"):
        v = [r[k] for r in rows if r[k] != ""]
        summ[k] = {"n": len(v), "p50": pct(v, 50), "p95": pct(v, 95), "p99": pct(v, 99), "max": max(v) if v else ""}
    (out / "mbb_summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
