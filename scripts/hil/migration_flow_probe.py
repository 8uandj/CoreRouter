#!/usr/bin/env python3
"""Run one bounded HIL flow while the API performs make-before-break migration.

The client targets the existing Pod until the controller confirms the admitted
operation, then changes its /32 SRv6 route to the Ready replacement Pod. This
measures application availability across that controlled endpoint handoff; it
does not claim a stable virtual service address.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8000/api"
SDN = "http://127.0.0.1:8765"
MNEXEC = ROOT / "results/hil/e2e_tools/mnexec.sh"
P4CLI = ROOT / "results/hil/e2e_tools/p4cli.sh"
ANALYZER = ROOT / "scripts/hil/analyze_migration_flow.py"


def utc():
    return datetime.now(timezone.utc).isoformat()


def http(base, method, path, payload=None, timeout=15):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as exc:
        raw, code = exc.read(), exc.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, {"raw": raw.decode(errors="replace")}


def command(args, timeout=30, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError("{} failed ({}): {}".format(" ".join(map(str, args)), result.returncode,
                                                        (result.stderr or result.stdout)[-1200:]))
    return result


def kjson(*args):
    return json.loads(command(["kubectl", "-n", "core-router", "get", *args, "-o", "json"]).stdout)


def deployment_exists(name):
    return command(["kubectl", "-n", "core-router", "get", "deployment/" + name], check=False).returncode == 0


def pod_for(name):
    doc = kjson("pods", "-l", "app=" + name)
    for pod in doc.get("items", []):
        if pod.get("metadata", {}).get("deletionTimestamp"):
            continue
        conditions = {c["type"]: c for c in pod.get("status", {}).get("conditions", [])}
        ready = conditions.get("Ready", {})
        if ready.get("status") == "True" and pod.get("status", {}).get("podIP"):
            transition = ready.get("lastTransitionTime")
            return {"name": pod["metadata"]["name"], "ip": pod["status"]["podIP"],
                    "node": pod.get("spec", {}).get("nodeName"), "ready_utc": transition,
                    "conditions": {k: v.get("status") for k, v in conditions.items()}}
    return {}


def counter_snapshot(path):
    import re
    out = {}
    for switch in path:
        result = command([str(P4CLI), "s{}".format(switch),
                          "counter_read srv6_advance_counter 0",
                          "counter_read srv6_terminal_counter 0",
                          "counter_read msd_violation_counter 0"]).stdout
        values = [int(v) for v in re.findall(r"packets=(\d+)", result)]
        if len(values) != 3:
            raise RuntimeError("could not parse P4 counters for s{}".format(switch))
        out["s{}".format(switch)] = dict(zip(("advance", "terminal", "msd_violation"), values))
    return out


def epoch(iso_utc):
    return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).timestamp()


def host_peer_mac(host, iface):
    inside = command([str(MNEXEC), host, "ip -o link show " + iface]).stdout
    match = re.search(r"@if(\d+)", inside)
    if not match:
        raise RuntimeError("cannot identify host-side peer index for " + iface)
    peer_index = match.group(1)
    links = command(["ip", "-o", "link"]).stdout.splitlines()
    peer_line = next((line for line in links if line.split(":", 1)[0] == peer_index), None)
    if not peer_line:
        raise RuntimeError("cannot find host-side peer interface index " + peer_index)
    peer_iface = peer_line.split(": ", 1)[1].split("@", 1)[0]
    details = command(["ip", "link", "show", peer_iface]).stdout
    mac = re.search(r"link/ether ([0-9a-f:]{17})", details)
    if not mac:
        raise RuntimeError("cannot read host-side peer MAC for " + peer_iface)
    return mac.group(1)


def source_setup_script(path, sids, old_ip, target_file, rows_file, stop_file, run_id, count_limit, peer_mac):
    traversal = list(reversed(sids))
    segs = ",".join(traversal)
    first_sid = traversal[0]
    lines = [
        "#!/usr/bin/env bash", "set -u", "H=h1", "IF=h1-eth0",
        "TARGET_FILE={!r}".format(str(target_file)), "ROWS_FILE={!r}".format(str(rows_file)),
        "STOP_FILE={!r}".format(str(stop_file)), "RUN_ID={!r}".format(run_id),
        "OLD_IP={!r}".format(old_ip), "SEGS={!r}".format(segs),
        "cleanup() {{ for ip in \"$OLD_IP\" \"$(cat \"$TARGET_FILE\" 2>/dev/null || true)\"; do [ -z \"$ip\" ] || ip route del \"$ip/32\" 2>/dev/null || true; done; ip -6 neigh del {!r} dev \"$IF\" 2>/dev/null || true; ip -6 route del fc00::/16 dev \"$IF\" 2>/dev/null || true; ip -6 addr del 2001:db8:100::1/64 dev \"$IF\" 2>/dev/null || true; ethtool -K \"$IF\" tx on >/dev/null 2>&1 || true; }}".format(first_sid),
        "trap cleanup EXIT",
        "ethtool -K \"$IF\" tx off >/dev/null 2>&1 || true",
        "ip -6 addr replace 2001:db8:100::1/64 dev \"$IF\" nodad",
        "ip -6 route replace fc00::/16 dev \"$IF\"",
        "PEER_MAC={!r}".format(peer_mac),
        "ip -6 neigh replace {!r} lladdr \"$PEER_MAC\" dev \"$IF\" nud permanent".format(first_sid),
        "LAST_IP=''",
        "for i in $(seq 1 {}); do".format(count_limit),
        "  [ -e \"$STOP_FILE\" ] && break",
        "  TARGET=$(cat \"$TARGET_FILE\" 2>/dev/null || true)",
        "  [ -n \"$TARGET\" ] || { sleep 0.1; continue; }",
        "  if [ \"$TARGET\" != \"$LAST_IP\" ]; then ip route replace \"$TARGET/32\" encap seg6 mode encap segs \"$SEGS\" dev \"$IF\" || { sleep 0.1; continue; }; LAST_IP=\"$TARGET\"; fi",
        "  T0=$(date +%s.%N)",
        "  RESP=$(curl -sS --max-time 1 -o - -w $'\\n%{http_code}\\t%{time_total}' -H \"X-HIL-Marker: $RUN_ID/$i\" \"http://$TARGET:8000/echo\" 2>/dev/null || true)",
        "  T1=$(date +%s.%N)",
        "  BODY=${RESP%$'\\n'*}; META=${RESP##*$'\\n'}; CODE=${META%%$'\\t'*}; RT=${META#*$'\\t'}",
        "  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$i\" \"$T0\" \"$T1\" \"$TARGET\" \"$CODE $RT\" \"$BODY\" >> \"$ROWS_FILE\"",
        "  sleep 0.2",
        "done",
    ]
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--old-vnf", required=True)
    ap.add_argument("--source-node", type=int, default=0)
    ap.add_argument("--msd-depth", type=int, default=2)
    ap.add_argument("--flow-id", required=True)
    ap.add_argument("--rate-hz", type=float, default=5.0)
    ap.add_argument("--max-seconds", type=int, default=180)
    ap.add_argument("--post-delete-seconds", type=int, default=10)
    args = ap.parse_args()
    if args.rate_hz != 5.0:
        raise RuntimeError("the bounded HIL profile is fixed at 5 requests/s")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record_path = out / "migration.json"
    old_pod = pod_for(args.old_vnf)
    state_code, state = http(API, "GET", "/orchestrate/state")
    busy_code, busy = http(API, "GET", "/orchestrate/status")
    topo_code, topo = http(SDN, "GET", "/topology")
    if state_code != 200 or busy_code != 200 or topo_code != 200 or busy.get("is_migrating"):
        raise RuntimeError("migration preflight failed: API/controller unavailable or migration active")
    rows = state.get("data", {}).get("active_vnfs", [])
    old_rec = next((v for v in rows if v.get("name") == args.old_vnf), None)
    if not old_rec or old_rec.get("deployment_ready") is not True or not old_pod.get("ready_utc"):
        raise RuntimeError("old VNF is not a Ready, accounted experiment endpoint")
    if not deployment_exists(args.old_vnf):
        raise RuntimeError("old Deployment is absent")
    old_evidence = json.loads((ROOT / "results/hil/orchestrated_chain_20261124/run03/orchestration.json").read_text())
    old_real = old_evidence["realization"]
    if old_real.get("switch_path") != [1, 2] or old_real.get("p4_topology_hash") != topo.get("p4_topology_hash"):
        raise RuntimeError("old route or P4 topology differs from the recorded safe baseline")
    counters_before = counter_snapshot(old_real["switch_path"])

    target_file, rows_file, stop_file = out / "target_ip", out / "flow.tsv", out / "stop"
    target_file.write_text(old_pod["ip"] + "\n")
    script_path = out / "source_flow.sh"
    source_host = "h{}".format(args.source_node + 1)
    peer_mac = host_peer_mac(source_host, source_host + "-eth0")
    source_setup_script(script_path, old_real["sid_stack"], old_pod["ip"], target_file,
                        rows_file, stop_file, args.flow_id, int(args.max_seconds * args.rate_hz) + 20,
                        peer_mac)
    traffic = subprocess.Popen(["timeout", "--signal=INT", str(args.max_seconds + 15),
                                str(MNEXEC), source_host,
                                "bash " + str(script_path)], cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    rec = {"run_id": args.flow_id, "old_vnf": args.old_vnf, "old_pod": old_pod,
           "source_node": args.source_node, "switch_path": old_real["switch_path"],
           "sid_stack_final_to_first": old_real["sid_stack"],
           "baseline": {"state_version": state["data"].get("state_version"),
                        "active_vnfs": len(rows), "p4_topology_hash": topo.get("p4_topology_hash"),
                        "profile_id": topo.get("profile_id"),
                        "deployments": [d["metadata"]["name"] for d in kjson("deployments").get("items", [])],
                        "p4_counters": counters_before},
           "t": {"flow_started_utc": utc()}}
    record_path.write_text(json.dumps(rec, indent=2) + "\n")
    # Establish successful traffic to the old endpoint before requesting migration.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if rows_file.exists() and sum("\t200 " in line for line in rows_file.read_text().splitlines()) >= 2:
            break
        if traffic.poll() is not None:
            raise RuntimeError("continuous sender stopped before the old-endpoint baseline")
        time.sleep(0.1)
    else:
        stop_file.touch()
        traffic.communicate(timeout=10)
        raise RuntimeError("could not establish baseline requests to old endpoint")

    req = {"flow_id": args.flow_id, "service_type": "voc", "cpu_req": 4.0,
           "ram_req": 2.0, "msd_req": args.msd_depth, "alert_flag": True,
           "source_node": args.source_node, "destination_node": 9,
           "expected_old_vnf": args.old_vnf}
    rec["request"] = req
    rec["t"]["orchestrate_submit_utc"] = utc()
    code, body = http(API, "POST", "/orchestrate", req, timeout=45)
    rec["orchestrate_http"], rec["orchestrate_response"] = code, body
    data = body.get("data", {}) if isinstance(body, dict) else {}
    migration = data.get("migration_result") or {}
    if code != 200 or migration.get("old_vnf") != args.old_vnf:
        rec["failure"] = "request did not start the expected old-to-new migration"
        rec["t"]["probe_stopped_utc"] = utc()
        stop_file.touch()
        try:
            traffic.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            traffic.kill()
        record_path.write_text(json.dumps(rec, indent=2) + "\n")
        raise RuntimeError(rec["failure"])
    new_name = data["vnf_name"]
    real = data["admitted_realization"]
    rec.update({"new_vnf": new_name, "realization": real, "migration_result": migration})
    if real.get("switch_path") != old_real.get("switch_path"):
        rec["failure"] = "replacement path changed; active flow left on old endpoint"
        stop_file.touch()
        traffic.communicate(timeout=15)
        record_path.write_text(json.dumps(rec, indent=2) + "\n")
        raise RuntimeError("replacement route changed; stop before steering/traffic retarget")
    rec["events"] = {}
    rec["t"]["orchestrate_response_utc"] = utc()
    record_path.write_text(json.dumps(rec, indent=2) + "\n")

    deadline = time.monotonic() + args.max_seconds
    deletion_observed = None
    last_pod_check = 0.0
    last_status_check = 0.0
    status, new_pod, controller = {}, {}, {}
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now - last_pod_check >= 1.0:
            new_pod = pod_for(new_name)
            last_pod_check = now
            if new_pod and "ready" not in rec["events"]:
                rec["events"]["ready"] = epoch(new_pod["ready_utc"]) if new_pod.get("ready_utc") else time.time()
                rec["new_pod"] = new_pod
        if now - last_status_check >= 0.5:
            _, status = http(API, "GET", "/orchestrate/migrations/{}".format(new_name))
            _, controller = http(SDN, "GET", "/steer/status")
            last_status_check = now
            if (controller.get("new_deploy") == new_name
                    and controller.get("request_id") == real.get("request_id")
                    and controller.get("operation_id") == real.get("operation_id")
                    and controller.get("confirm_steer_done") is True):
                if "ready" not in rec["events"]:
                    rec["events"]["ready"] = time.time()
                if "steer_confirmed" not in rec["events"]:
                    rec["events"]["steer_confirmed"] = time.time()
                    rec["t"]["steer_confirmed_utc"] = utc()
                    rec["controller_steer_status"] = controller
                    target_file.write_text(new_pod.get("ip", "") + "\n")
                    if not new_pod.get("ip"):
                        _, new_pod = http(API, "GET", "/orchestrate/state")
                        new_pod = pod_for(new_name)
                        target_file.write_text(new_pod.get("ip", "") + "\n")
                    rec["new_pod"] = new_pod
        if rec["events"].get("steer_confirmed") and not deployment_exists(args.old_vnf):
            if "old_deleted" not in rec["events"]:
                rec["events"]["old_deleted"] = time.time()
                rec["t"]["old_deleted_observed_utc"] = utc()
                deletion_observed = time.monotonic()
            elif time.monotonic() - deletion_observed >= args.post_delete_seconds:
                break
        if traffic.poll() is not None:
            rec["sender_exit"] = traffic.returncode
            break
        time.sleep(0.1)

    stop_file.touch()
    try:
        stdout, stderr = traffic.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        traffic.kill()
        stdout, stderr = traffic.communicate()
    rec["sender_stdout"], rec["sender_stderr"] = stdout[-4000:], stderr[-4000:]
    rec["t"]["flow_stopped_utc"] = utc()
    rec["migration_status"], rec["final_controller_status"] = status, controller
    rec["old_deployment_absent"] = not deployment_exists(args.old_vnf)
    rec["new_pod_final"] = pod_for(new_name)
    rec["counters_before"] = counters_before
    rec["counters_after"] = counter_snapshot(real["switch_path"])
    sent, received = [], []
    if rows_file.exists():
        for line in rows_file.read_text().splitlines():
            fields = line.split("\t", 5)
            if len(fields) != 6:
                continue
            seq, t0, t1, target, meta, body_text = fields
            parts = meta.split()
            code = parts[0] if parts else "000"
            sent.append({"id": int(seq), "t": float(t0), "target_ip": target})
            try:
                body_obj = json.loads(body_text)
            except ValueError:
                body_obj = {}
            if code == "200" and body_obj.get("role") == "vvoc":
                received.append({"id": int(seq), "t": float(t1), "target_ip": target})
    rec["sent"], rec["received"] = sent, received
    if all(k in rec["events"] for k in ("ready", "steer_confirmed", "old_deleted")) and received:
        analyze_input = out / "analysis_input.json"
        analyze_input.write_text(json.dumps({"sent": sent, "received": received, "events": rec["events"]}, indent=2) + "\n")
        result = command([str(ROOT / "venv/bin/python"), str(ANALYZER), "--input", str(analyze_input),
                          "--out", str(out / "flow_summary.json")], check=False)
        rec["analysis_exit_code"] = result.returncode
        if (out / "flow_summary.json").exists():
            rec["flow_summary"] = json.loads((out / "flow_summary.json").read_text())
    else:
        rec["analysis_error"] = "missing one or more migration phase events or all receive receipts"
    rec["counter_delta"] = {
        sw: {key: rec["counters_after"][sw][key] - rec["counters_before"][sw][key]
             for key in rec["counters_before"][sw]} for sw in rec["counters_before"]}
    rec["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (Path(__file__).resolve(), ANALYZER, MNEXEC, P4CLI)}
    rec["evidence_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (rows_file, script_path, out / "analysis_input.json", out / "flow_summary.json")
                              if p.exists()}
    record_path.write_text(json.dumps(rec, indent=2) + "\n")
    (out / "migration.json.sha256").write_text(hashlib.sha256(record_path.read_bytes()).hexdigest() + "  migration.json\n")
    print(json.dumps({"old_vnf": args.old_vnf, "new_vnf": new_name,
                      "ready": "ready" in rec["events"], "steer_confirmed": "steer_confirmed" in rec["events"],
                      "old_deleted": rec["old_deployment_absent"], "sent": len(sent), "received": len(received),
                      "loss": len(sent) - len({r["id"] for r in received}),
                      "flow_summary": rec.get("flow_summary"), "counter_delta": rec.get("counter_delta")}))


if __name__ == "__main__":
    main()
