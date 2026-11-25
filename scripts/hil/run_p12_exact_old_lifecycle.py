#!/usr/bin/env python3
"""Sequential multi-hour exact-old-VNF migration and continuous-flow campaign."""
import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8000/api"
PROBE = ROOT / "scripts/hil/migration_flow_probe.py"


def utc():
    return datetime.now(timezone.utc).isoformat()


def get(path):
    with urllib.request.urlopen(API + path, timeout=10) as response:
        return json.load(response)


def kubectl(*args):
    return subprocess.run(["kubectl", "-n", "core-router", *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=20)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--initial-old-vnf", required=True)
    ap.add_argument("--duration-hours", type=float, default=3.0)
    ap.add_argument("--max-cycles", type=int, default=1000)
    ap.add_argument("--cycle-deadline-s", type=int, default=180)
    ap.add_argument("--cycle-interval-s", type=int, default=600)
    args = ap.parse_args()
    if not 0.05 <= args.duration_hours <= 3 or args.max_cycles < 1 or args.cycle_interval_s < 60:
        raise SystemExit("duration must be 0.05..3 hours and max-cycles positive")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    baseline = get("/orchestrate/state").get("data", {})
    # The inventory script prints a concise summary; retain its JSON artifact separately.
    subprocess.run(["venv/bin/python", "scripts/hil/live_inventory.py", "--out",
                    str(out / "baseline_inventory.json")], cwd=ROOT, check=True, timeout=30,
                   capture_output=True, text=True)
    inventory = json.loads((out / "baseline_inventory.json").read_text())
    expected_count = inventory["deployments"]["count"]
    if baseline.get("unaccounted_vnfs") or len(baseline.get("active_vnfs", [])) != expected_count:
        raise RuntimeError("baseline API state and live inventory are not reconciled")
    rec = {"run_id": args.run_id, "started_utc": utc(), "requested_hours": args.duration_hours,
           "deadline_s": args.cycle_deadline_s, "cycle_interval_s": args.cycle_interval_s,
           "baseline_vnf_count": expected_count,
           "baseline_state_version": baseline.get("state_version"), "cycles": [],
           "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (Path(__file__).resolve(), PROBE,
                                       ROOT / "scripts/hil/analyze_migration_flow.py")}}
    record = out / "campaign.json"
    record.write_text(json.dumps(rec, indent=2) + "\n")
    end = time.monotonic() + args.duration_hours * 3600
    old = args.initial_old_vnf
    stop_reason = "duration_elapsed"
    while time.monotonic() < end and len(rec["cycles"]) < args.max_cycles:
        cycle = len(rec["cycles"]) + 1
        prefix = "cycle{:04d}".format(cycle)
        status = get("/orchestrate/status")
        state = get("/orchestrate/state").get("data", {})
        if status.get("is_migrating") or state.get("unaccounted_vnfs"):
            stop_reason = "busy_or_unaccounted_preflight"
            break
        if len(state.get("active_vnfs", [])) != expected_count:
            stop_reason = "inventory_count_drift_preflight"
            break
        if kubectl("get", "deployment/" + old).returncode:
            stop_reason = "exact_old_absent_preflight"
            break
        cycle_dir = out / prefix
        command = ["venv/bin/python", str(PROBE), "--out", str(cycle_dir), "--old-vnf", old,
                   "--source-node", "0", "--msd-depth", "2", "--flow-id",
                   "{}-{}".format(args.run_id, prefix), "--max-seconds", str(args.cycle_deadline_s),
                   "--post-delete-seconds", "5"]
        cycle_started = time.monotonic()
        start = utc()
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                             timeout=args.cycle_deadline_s + 240)
        evidence_path = cycle_dir / "migration.json"
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        summary = evidence.get("flow_summary", {})
        checks = {
            "probe_exit_zero": run.returncode == 0,
            "expected_old_name": evidence.get("old_vnf") == old,
            "old_deleted": evidence.get("old_deployment_absent") is True,
            "new_ready": (bool(evidence.get("new_pod_final", {}).get("ready_utc"))
                          and evidence.get("new_pod_final", {}).get("conditions", {}).get("Ready") == "True"),
            "steer_confirmed": evidence.get("events", {}).get("steer_confirmed") is not None,
            "flow_zero_loss": summary.get("zero_loss") is True,
            "flow_received": summary.get("received_unique", 0) > 0,
        }
        cycle_rec = {"cycle": cycle, "start_utc": start, "end_utc": utc(), "old_vnf": old,
                     "new_vnf": evidence.get("new_vnf"), "checks": checks,
                     "flow_summary": summary, "counter_delta": evidence.get("counter_delta"),
                     "returncode": run.returncode, "stdout": run.stdout[-2000:],
                     "stderr": run.stderr[-2000:],
                     "evidence": str(evidence_path.relative_to(out)) if evidence_path.exists() else None}
        rec["cycles"].append(cycle_rec)
        if not all(checks.values()):
            stop_reason = "cycle_acceptance_failed"
            break
        status = get("/orchestrate/status")
        state = get("/orchestrate/state").get("data", {})
        live_names = json.loads(kubectl("get", "deployments", "-o", "json").stdout)
        present = {item["metadata"]["name"] for item in live_names.get("items", [])}
        new = evidence["new_vnf"]
        if (status.get("is_migrating") or state.get("unaccounted_vnfs")
                or len(state.get("active_vnfs", [])) != expected_count or new not in present):
            stop_reason = "inventory_or_lock_drift_postcycle"
            break
        old = new
        rec["last_old_vnf"] = old
        record.write_text(json.dumps(rec, indent=2) + "\n")
        time.sleep(min(max(0, args.cycle_interval_s - (time.monotonic() - cycle_started)),
                       max(0, end - time.monotonic())))
    rec["ended_utc"] = utc()
    rec["stop_reason"] = stop_reason
    rec["elapsed_s"] = round(args.duration_hours * 3600 - max(0, end - time.monotonic()), 3)
    rec["cycle_count"] = len(rec["cycles"])
    record.write_text(json.dumps(rec, indent=2) + "\n")
    (out / "campaign.json.sha256").write_text(
        hashlib.sha256(record.read_bytes()).hexdigest() + "  campaign.json\n")
    print(json.dumps({"run_id": args.run_id, "cycles": rec["cycle_count"],
                      "stop_reason": stop_reason, "elapsed_s": rec["elapsed_s"]}))
    if stop_reason not in ("duration_elapsed",) and time.monotonic() < end:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
