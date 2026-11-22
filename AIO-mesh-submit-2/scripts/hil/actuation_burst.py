#!/usr/bin/env python3
"""Concurrent actuation burst: queueing of admitted requests at the backend's
single migration lock (Tekton create -> Ready -> steer are serialized there).

Submits --requests alert requests with --workers concurrent clients, then polls
each admitted request's actuation record until terminal and extracts per-request
stage timestamps from the backend and controller logs. No packets are sent here
(probe afterwards with e2e_packet_probe.py to keep counters unpolluted).

Usage: actuation_burst.py --out DIR --requests 40 --workers 8 --seed 77
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import e2e_campaign as ec


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--requests", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=77)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(a.seed)
    reqs = []
    for i in range(a.requests):
        r = ec.make_request(rng, i)
        r.pop("_profile")
        r["flow_id"] = f"burst-{i:03d}"
        reqs.append(r)
    t_start = utc()

    def submit(i):
        t0 = utc()
        code, body, rtt = ec.http("POST", "/orchestrate", reqs[i])
        return {"i": i, "request": reqs[i], "submit_utc": t0, "response_utc": utc(), "http": code,
                "rtt_ms": round(rtt, 3), "body": body}

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(submit, range(len(reqs))))
    admitted = [r for r in res if r["http"] == 200]
    deadline = time.time() + 1800
    for r in admitted:
        name = r["body"]["data"]["vnf_name"]
        while time.time() < deadline:
            c, st, _ = ec.http("GET", f"/orchestrate/migrations/{name}")
            if c == 200 and st.get("status") in ("success", "error", "warning"):
                break
            time.sleep(2)
        r["actuation_status"] = st
        r["terminal_seen_utc"] = utc()
    blog = subprocess.run(["docker", "logs", "--timestamps", "--since", t_start, "3s-com-backend"],
                          capture_output=True, text=True)
    blines = (blog.stdout + blog.stderr).splitlines()
    clog = subprocess.run(["docker", "logs", "--timestamps", "--since", t_start, "gracious_jackson"],
                          capture_output=True, text=True)
    clines = (clog.stdout + clog.stderr).splitlines()
    (out / "backend_log.txt").write_text("\n".join(blines))
    (out / "controller_log.txt").write_text("\n".join(clines))
    for r in admitted:
        name = r["body"]["data"]["vnf_name"]
        mine = [l for l in blines if name in l]
        r["backend_make_utc"] = ec.first_ts(mine, "PHASE: MAKE")
        r["backend_ready_utc"] = ec.first_ts(mine, "is READY")
        start = ec.first_ts([l for l in clines if f"Installing rules for {name}" in l], "START")
        after = [l for l in clines if start and l.split(" ", 1)[0] >= start]
        r["controller_steer_start_utc"] = start
        r["controller_confirm_utc"] = ec.first_ts(after, "confirm_steer_done = True")
        r["pod"] = ec.pod_info(name)
    (out / "burst.json").write_text(json.dumps({"t_start": t_start, "workers": a.workers, "results": res}, indent=1, default=str))
    print(json.dumps({"offered": len(res), "admitted": len(admitted),
                      "terminal": [(r["body"]["data"]["vnf_name"], (r["actuation_status"].get("data") or {}).get("recovery_state"))
                                   for r in admitted]}, indent=1))


if __name__ == "__main__":
    main()
