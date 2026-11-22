#!/usr/bin/env python3
"""Release reservations left by a concurrency attempt whose /free calls failed.

Safety rules:
  * only names that the given per_request.csv recorded as admitted by this
    experiment are eligible (never baseline or unknown names);
  * the live state entry must be pending/unactuated: not deployment_ready,
    not accounting_unknown;
  * release uses the documented API (/api/orchestrate/free with vnf_name and
    the full tuple), never /reset; every response is logged.

Usage: /home/CoreRouter/venv/bin/python scripts/release_leftover_reservations.py <attempt_dir> [--apply]
Without --apply it only prints the plan.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/CoreRouter")
from src.analytics.benchmark.benchmark_testbed.http_client import TestbedClient  # noqa: E402


def main() -> int:
    attempt = Path(sys.argv[1]).resolve()
    apply = "--apply" in sys.argv
    ours = {r["vnf_name"] for r in csv.DictReader((attempt / "per_request.csv").open())
            if r["admitted"] == "True" and r["vnf_name"]}
    client = TestbedClient("http://127.0.0.1:8000/api", "http://127.0.0.1:8765")
    code, body, _ = client.state()
    active = (body.get("data") or {}).get("active_vnfs") or []
    plan, skipped = [], []
    for v in active:
        name = v.get("name")
        if name not in ours:
            continue
        if v.get("deployment_ready") or v.get("accounting_unknown"):
            skipped.append({"name": name, "why": "not an unactuated pending reservation", "entry": v})
            continue
        plan.append({"vnf_name": name, "v_place": int(v["v_place"]), "v_route": int(v["v_route"]),
                     "cpu_req": float(v["cpu_req"]), "ram_req": float(v["ram_req"]), "msd_req": int(v["msd_req"])})
    log = {"utc": datetime.now(timezone.utc).isoformat(), "apply": apply, "ours_admitted": len(ours),
           "active_before": len(active), "to_release": len(plan), "skipped": skipped, "responses": []}
    if apply:
        for p in plan:
            c, b, lat = client.free(p)
            log["responses"].append({"payload": p, "http": c, "body": b, "latency_ms": lat})
        code, body, _ = client.state()
        log["active_after"] = len((body.get("data") or {}).get("active_vnfs") or [])
        log["active_after_names"] = sorted(v.get("name") for v in (body.get("data") or {}).get("active_vnfs") or [])
        (attempt / "leftover_release_log.json").write_text(json.dumps(log, indent=2, default=str))
    print(json.dumps({k: v for k, v in log.items() if k not in ("responses",)}, indent=1, default=str)[:3000])
    if apply:
        print("http codes:", sorted({r["http"] for r in log["responses"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
